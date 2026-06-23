"""Celery tasks for exporting data from the project."""

import json
import logging
import os
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.serializers import serialize
from django.utils.text import slugify

from twf.models import (
    Export,
    Page,
    PageTag,
    CollectionItem,
    DictionaryEntry,
    Variation,
    DateVariation,
)
from twf.tasks.task_base import BaseTWFTask
from twf.utils.create_export_utils import create_data

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def export_documents_task(self, project_id, user_id, **kwargs):
    """
    Export documents or pages from a project to JSON files.

    Args:
        self: Celery task instance
        project_id: ID of the project to export
        user_id: ID of the user performing the export
        **kwargs: Additional parameters including:
            - export_type: "documents" or "pages"
            - export_single_file: bool, whether to create one file per item or combine all

    Returns:
        None (creates Export object with downloadable file)
    """
    self.validate_task_parameters(kwargs, ["export_type", "export_single_file"])

    docs_to_export = self.project.documents.all()
    self.set_total_items(docs_to_export.count())

    export_type = kwargs.get("export_type")
    export_single_file = kwargs.get("export_single_file")

    # 1st step: Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    try:
        # 2nd step: Export documents
        processed_entries = 0
        export_data_list = []

        for doc in docs_to_export:
            if export_type == "documents":
                export_doc_data = create_data(doc)

                if export_single_file:
                    export_filename = f"document_{doc.document_id}.json"
                    export_filepath = Path(temp_dir) / export_filename
                    with open(export_filepath, "w", encoding="utf8") as sf:
                        json.dump(export_doc_data, sf, indent=4)
                else:
                    export_data_list.append(export_doc_data)

            elif export_type == "pages":
                for page in doc.pages.all():
                    export_page_data = create_data(page)

                    if export_single_file:
                        export_filename = f"page_{page.tk_page_id}.json"
                        export_filepath = os.path.join(temp_dir, export_filename)
                        with open(export_filepath, "w", encoding="utf8") as sf:
                            json.dump(export_page_data, sf, indent=4)
                    else:
                        export_data_list.append(export_page_data)

            self.advance_task()

        # 3rd step: Store the final result
        if export_single_file:
            zip_filename = f"export_{self.project.id}.zip"
            zip_filepath = shutil.make_archive(
                zip_filename.replace(".zip", ""), "zip", temp_dir
            )
            result_filepath = zip_filepath
        else:
            export_filename = f"export_{self.project.id}.json"
            export_filepath = Path(temp_dir) / export_filename
            with open(export_filepath, "w", encoding="utf8") as sf:
                json.dump(export_data_list, sf, indent=4)
            result_filepath = export_filepath

        # Move to a persistent storage location for download
        result_filename = Path(result_filepath).name
        relative_export_path = f"exports/{result_filename}"
        final_result_path = Path(settings.MEDIA_ROOT) / relative_export_path

        # Ensure the directory exists
        final_result_path.parent.mkdir(parents=True, exist_ok=True)

        with open(result_filepath, "rb") as f:
            saved_filename = default_storage.save(relative_export_path, File(f))

    finally:
        # Cleanup temporary files AFTER successful storage
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    export_instance = Export(
        project=self.project,
        export_file=saved_filename,  # Save the path to the file
        export_type=export_type,
    )
    export_instance.save(current_user=self.user)

    # 4th step: End task and return the download URL
    download_url = export_instance.export_file.url
    self.end_task(download_url=download_url)


@shared_task(bind=True, base=BaseTWFTask)
def export_project_task(self, project_id, user_id, **kwargs):
    """
    Export complete project data including all related models to a ZIP file.

    Creates a comprehensive export containing project data, documents, pages, tags,
    collections, prompts, workflows, and optionally dictionaries and media files.

    Args:
        self: Celery task instance
        project_id: ID of the project to export
        user_id: ID of the user performing the export
        **kwargs: Additional parameters including:
            - include_dictionaries: bool, whether to include dictionary data
            - include_media_files: bool, whether to include ZIP and XML files

    Returns:
        None (creates Export object with downloadable ZIP file)
    """
    self.validate_task_parameters(
        kwargs, ["include_dictionaries", "include_media_files"]
    )
    include_dictionaries = kwargs.get("include_dictionaries", True)
    include_media_files = kwargs.get("include_media_files", True)

    project = self.project  # Provided by BaseTWFTask
    export_data = {}

    # Core data export
    export_data["project"] = serialize("json", [project])
    export_data["documents"] = serialize("json", project.documents.all())

    pages = Page.objects.filter(document__project=project).select_related("document")
    export_data["pages"] = serialize("json", pages)

    tags = PageTag.objects.filter(page__document__project=project)
    export_data["tags"] = serialize("json", tags)

    export_data["collections"] = serialize("json", project.collections.all())

    collection_items = CollectionItem.objects.filter(collection__project=project)
    export_data["collection_items"] = serialize("json", collection_items)

    export_data["prompts"] = serialize("json", project.prompts.all())

    export_data["workflows"] = serialize("json", project.workflow_set.all())

    if include_dictionaries:
        dictionaries = project.selected_dictionaries.all()
        entries = DictionaryEntry.objects.filter(dictionary__in=dictionaries)
        variations = Variation.objects.filter(entry__in=entries)
        date_variations = DateVariation.objects.all()

        export_data["dictionaries"] = serialize("json", dictionaries)
        export_data["dictionary_entries"] = serialize("json", entries)
        export_data["variations"] = serialize("json", variations)
        export_data["date_variations"] = serialize("json", date_variations)

    # Create ZIP
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # JSON files
        for name, content in export_data.items():
            zip_file.writestr(f"{name}.json", content)

        # Media files: downloaded ZIP and page XMLs
        if include_media_files:
            if project.downloaded_zip_file:
                zip_file.writestr(
                    f"media/{os.path.basename(project.downloaded_zip_file.name)}",
                    project.downloaded_zip_file.read(),
                )

            for page in pages:
                if page.xml_file and page.xml_file.name:
                    try:
                        zip_file.writestr(
                            f"media/{os.path.basename(page.xml_file.name)}",
                            page.xml_file.read(),
                        )
                    except Exception as e:
                        pass  # Log this if needed

    # Save the file in an Export object
    export_filename = f"{slugify(project.title)}-export.zip"
    export_file = ContentFile(zip_buffer.getvalue(), name=export_filename)
    export = Export(
        project=project,
        export_file=export_file,
        export_type="project",
        created_by=self.user,
        modified_by=self.user,
    )
    export.save(current_user=self.user)

    self.end_task(
        text="Export finished", status="SUCCESS", download_url=export.export_file.url
    )


@shared_task(bind=True, base=BaseTWFTask)
def export_to_zenodo_task(self, project_id, user_id, **kwargs):
    """
    Export project data to Zenodo repository.

    Args:
        self: Celery task instance
        project_id: ID of the project to export
        user_id: ID of the user performing the export
        **kwargs: Additional keyword arguments

    Returns:
        None (ends task immediately - placeholder implementation)
    """
    export_type = "sql"  # Can be 'sql' or 'json'
    self.end_task()

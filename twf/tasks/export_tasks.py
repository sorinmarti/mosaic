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

from twf.clients.zenodo_client import (
    get_deposition,
    update_deposition_metadata,
    upload_file_to_deposition,
    publish_deposition,
    create_temp_readme_from_project,
)
from twf.models import (
    Export,
    Page,
    PageTag,
    CollectionItem,
    DictionaryEntry,
    Variation,
    DateVariation,
    ExportConfiguration,
)
from twf.tasks.task_base import BaseTWFTask
from twf.utils.export_utils import ExportCreator

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def export_task(self, project_id, user_id, **kwargs):
    """
    Export project data using a specific export configuration.

    Args:
        self: Celery task instance
        project_id: ID of the project to export
        user_id: ID of the user performing the export
        **kwargs: Additional parameters including:
            - export_configuration_id: ID of the ExportConfiguration to use

    Returns:
        None (creates Export object with downloadable ZIP file)
    """
    self.validate_task_parameters(kwargs, ["export_configuration_id"])
    export_configuration_id = kwargs.get("export_configuration_id")
    export_configuration = ExportConfiguration.objects.get(id=export_configuration_id)
    download_url = None

    try:
        export_creator = ExportCreator(self.project, export_configuration)
        number_of_items = export_creator.get_number_of_items()
        self.set_total_items(number_of_items)

        # For every export, the "project" part is always the same
        export_data = export_creator.create_item_data(self.project)

        # The export creator provides a list of items to handle
        export_data["items"] = []
        for item in export_creator.get_items():
            item_data = export_creator.create_item_data(item)
            export_data["items"].append(item_data)
            self.advance_task(f"Exporting {item}")

        # Create ZIP
        temp_dir = tempfile.mkdtemp()
        with open(os.path.join(temp_dir, "data.json"), "w", encoding="utf8") as sf:
            json.dump(export_data, sf, indent=4)

        zip_filename = f"export_{self.project.id}"
        zip_filepath = shutil.make_archive(zip_filename, "zip", temp_dir)
        result_filename = Path(zip_filepath).name
        relative_export_path = f"exports/{result_filename}"

        final_result_path = Path(settings.MEDIA_ROOT) / relative_export_path
        final_result_path.parent.mkdir(parents=True, exist_ok=True)

        with open(zip_filepath, "rb") as f:
            saved_filename = default_storage.save(relative_export_path, File(f))

        export = Export(
            export_file=saved_filename, export_configuration=export_configuration
        )
        export.save(current_user=self.user)
        download_url = export.export_file.url
        self.end_task(download_url=download_url)

    except Exception as e:
        self.end_task(text="Export failed", status="ERROR")
        raise e


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
    Upload an existing export to Zenodo repository.

    Args:
        self: Celery task instance
        project_id: ID of the project
        user_id: ID of the user performing the upload
        **kwargs: Additional parameters including:
            - export_id: ID of the Export object to upload to Zenodo

    Returns:
        None (uploads export file to Zenodo deposition)
    """
    self.validate_task_parameters(kwargs, ["export_id"])

    export_id = kwargs.get("export_id")
    export = Export.objects.get(id=export_id)

    try:
        self.update_progress(0, "Starting Zenodo export...")
        depo = get_deposition(self.project)
        self.update_progress(5, "Zenodo deposition fetched.")
        if depo.get("submitted"):
            self.update_progress(
                10, "Existing deposition already published. Creating new version..."
            )
            depo = create_new_version_from_deposition(self.project)
            self.project.zenodo_deposition_id = depo["id"]
            self.project.save(update_fields=["zenodo_deposition_id"])
        else:
            self.update_progress(10, "Creating initial version...")

        # STEP 2: Update metadata
        update_deposition_metadata(self.project, depo["id"])
        self.update_progress(20, "Metadata uploaded.")

        # STEP 3: Upload files
        readme_path = create_temp_readme_from_project(self.project)
        try:
            upload_file_to_deposition(
                self.project, depo["id"], readme_path, "README.md"
            )
        finally:
            os.remove(readme_path)
        upload_file_to_deposition(
            self.project, depo["id"], export.export_file.path, "twf_dataset.zip"
        )
        self.update_progress(80, "Files uploaded.")

        # STEP 4: Publish
        result = publish_deposition(self.project, depo["id"])
        self.project.project_doi = result.get("doi")
        self.project.save(update_fields=["project_doi"])
        self.update_progress(100, f"Published. DOI: {self.project.project_doi}")

    except Exception as e:
        self.end_task(status="FAILURE", error_msg=str(e))
        raise

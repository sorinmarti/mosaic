"""Celery tasks for extracting Transkribus export files."""

import copy
import logging
import os
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

from celery import shared_task
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from simple_alto_parser import PageFileParser

from twf.models import Document, Page, DocumentSyncHistory, PageTag
from twf.utils.page_file_meta_data_reader import extract_transkribus_file_metadata
from twf.tasks.task_base import BaseTWFTask
from twf.utils.file_utils import delete_all_in_folder
from twf.clients.transkribus_api_client import TranskribusAPIClient

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def extract_zip_export_task(
    self,
    project_id,
    user_id,
    force_recreate_tags=False,
    delete_removed_documents=True,
    **kwargs,
):
    """
    Unified smart synchronization from Transkribus export.

    This task extracts the Transkribus export and intelligently syncs:
    1. Documents and pages (add/update/delete)
    2. Tags while preserving user assignments and parked status

    Args:
        project_id: Project ID
        user_id: User performing sync
        force_recreate_tags: If True, delete all tags and recreate (default: False)
        delete_removed_documents: If True, delete documents not in export (default: True)
        **kwargs: Additional options

    Returns:
        dict: Comprehensive statistics about the sync operation
    """
    extracted_files = 0
    doc_changes = {}
    tag_changes = {}

    try:
        # ========================================
        # PHASE 1: DOWNLOAD & EXTRACT (30%)
        # ========================================
        self.twf_task.text += "=" * 60 + "\n"
        self.twf_task.text += "PHASE 1: EXTRACT TRANSKRIBUS EXPORT\n"
        self.twf_task.text += "=" * 60 + "\n\n"
        self.twf_task.save(update_fields=["text"])

        # Validate and prepare zip file
        zip_file, extract_to_path = prepare_zip_file(self.project, self)
        self.twf_task.text += f"✓ Prepared zip file: {zip_file.name}\n"
        self.twf_task.text += f"✓ Extraction path: {extract_to_path}\n\n"
        self.twf_task.save(update_fields=["text"])

        # Extract files from zip
        copied_files = extract_files_from_zip(
            zip_file, extract_to_path, self.project, self
        )
        extracted_files = len(copied_files)
        self.twf_task.text += (
            f"✓ Extracted {extracted_files} files from the zip archive.\n\n"
        )
        self.twf_task.save(update_fields=["text"])

        # ========================================
        # PHASE 2: SYNC DOCUMENTS & PAGES (40%)
        # ========================================
        self.twf_task.text += "=" * 60 + "\n"
        self.twf_task.text += "PHASE 2: SYNC DOCUMENTS & PAGES\n"
        self.twf_task.text += "=" * 60 + "\n\n"
        self.twf_task.save(update_fields=["text"])

        doc_changes = sync_documents_and_pages(
            copied_files,
            self.project,
            self.user,
            self,
            delete_removed=delete_removed_documents,
        )

        self.twf_task.text += "\nDocument Sync Summary:\n"
        self.twf_task.text += f"  • Documents added: {doc_changes['added']}\n"
        self.twf_task.text += f"  • Documents updated: {doc_changes['updated']}\n"
        self.twf_task.text += f"  • Documents deleted: {doc_changes['deleted']}\n"
        self.twf_task.text += f"  • Pages added: {doc_changes['pages_added']}\n"
        self.twf_task.text += f"  • Pages updated: {doc_changes['pages_updated']}\n"
        self.twf_task.text += f"  • Pages deleted: {doc_changes['pages_deleted']}\n\n"
        self.twf_task.save(update_fields=["text"])

        # ========================================
        # PHASE 3: SMART TAG SYNC (30%)
        # ========================================
        if force_recreate_tags:
            self.twf_task.text += "=" * 60 + "\n"
            self.twf_task.text += "PHASE 3: RECREATE ALL TAGS (FORCE MODE)\n"
            self.twf_task.text += "=" * 60 + "\n\n"
            self.twf_task.text += "⚠️  WARNING: Force recreate mode enabled.\n"
            self.twf_task.text += (
                "⚠️  All existing tags will be deleted and recreated.\n"
            )
            self.twf_task.text += (
                "⚠️  Manual assignments and parked status will be lost.\n\n"
            )
            self.twf_task.save(update_fields=["text"])

            # Use the old recreate approach
            from twf.tasks.tags_tasks import create_page_tags

            pages = Page.objects.filter(document__project=self.project)
            self.set_total_items(pages.count())

            assigned_tags = 0
            total_tags = 0

            for page in pages:
                PageTag.objects.filter(page=page).delete()
                parsed_data = page.parsed_data

                for element in parsed_data.get("elements", []):
                    for tag in element.get("element_data", {}).get(
                        "custom_list_structure", []
                    ):
                        if "text" in tag:
                            text = tag["text"].strip()
                            copy_of_tag = copy.deepcopy(tag)
                            copy_of_tag.pop("text")
                            from twf.utils.tags_utils import assign_tag

                            page_tag = PageTag(
                                page=page,
                                variation=text,
                                variation_type=tag["type"],
                                additional_information=copy_of_tag,
                            )
                            is_assigned = assign_tag(page_tag, self.user)
                            if is_assigned:
                                assigned_tags += 1
                            total_tags += 1
                            page_tag.save(current_user=self.user)

                page.num_tags = len(
                    element.get("element_data", {}).get("custom_list_structure", [])
                )
                page.save()
                self.advance_task()

            tag_changes = {
                "added": total_tags,
                "updated": 0,
                "deleted": 0,
                "preserved_assignments": 0,
                "preserved_parked": 0,
                "auto_assigned": assigned_tags,
                "warnings": [],
            }
        else:
            self.twf_task.text += "=" * 60 + "\n"
            self.twf_task.text += "PHASE 3: SMART TAG SYNC\n"
            self.twf_task.text += "=" * 60 + "\n\n"
            self.twf_task.text += (
                "Smart sync mode: Preserving user assignments and parked status.\n\n"
            )
            self.twf_task.save(update_fields=["text"])

            # Import here to avoid circular import
            from twf.tasks.tags_tasks import smart_sync_tags

            tag_changes = smart_sync_tags(self.project, self.user, self)

        self.twf_task.text += "\nTag Sync Summary:\n"
        self.twf_task.text += f"  • Tags added: {tag_changes['added']}\n"
        self.twf_task.text += f"  • Tags updated: {tag_changes['updated']}\n"
        self.twf_task.text += f"  • Tags deleted: {tag_changes['deleted']}\n"
        self.twf_task.text += (
            f"  • Assignments preserved: {tag_changes['preserved_assignments']}\n"
        )
        self.twf_task.text += (
            f"  • Parked status preserved: {tag_changes['preserved_parked']}\n"
        )
        self.twf_task.text += f"  • Auto-assigned: {tag_changes['auto_assigned']}\n"

        if tag_changes.get("warnings"):
            self.twf_task.text += f"\n⚠️  Warnings: {len(tag_changes['warnings'])}\n"
            for warning in tag_changes["warnings"][:5]:  # Show first 5 warnings
                self.twf_task.text += f"  - {warning}\n"
            if len(tag_changes["warnings"]) > 5:
                self.twf_task.text += (
                    f"  ... and {len(tag_changes['warnings']) - 5} more warnings\n"
                )

        self.twf_task.text += "\n"
        self.twf_task.save(update_fields=["text"])

        # ========================================
        # FINALIZE
        # ========================================
        self.twf_task.text += "=" * 60 + "\n"
        self.twf_task.text += "SYNC COMPLETED SUCCESSFULLY\n"
        self.twf_task.text += "=" * 60 + "\n"
        self.twf_task.save(update_fields=["text"])

        self.end_task(
            status="SUCCESS",
            extracted_files=extracted_files,
            documents_added=doc_changes.get("added", 0),
            documents_updated=doc_changes.get("updated", 0),
            documents_deleted=doc_changes.get("deleted", 0),
            pages_added=doc_changes.get("pages_added", 0),
            pages_updated=doc_changes.get("pages_updated", 0),
            pages_deleted=doc_changes.get("pages_deleted", 0),
            tags_added=tag_changes.get("added", 0),
            tags_updated=tag_changes.get("updated", 0),
            tags_deleted=tag_changes.get("deleted", 0),
            tags_preserved=tag_changes.get("preserved_assignments", 0),
            tags_auto_assigned=tag_changes.get("auto_assigned", 0),
            warnings_count=len(tag_changes.get("warnings", [])),
        )

        return {
            "status": "completed",
            "extracted_files": extracted_files,
            "doc_changes": doc_changes,
            "tag_changes": tag_changes,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in extract_zip_export_task: {error_msg}")

        if self.twf_task:
            self.twf_task.text += "\n" + "=" * 60 + "\n"
            self.twf_task.text += "❌ SYNC FAILED\n"
            self.twf_task.text += "=" * 60 + "\n"
            self.twf_task.text += f"Error: {error_msg}\n"
            self.twf_task.save(update_fields=["text"])

        self.end_task(status="FAILURE", error_msg=error_msg)
        raise


def prepare_zip_file(project, celery_task):
    """Check the zip file and prepare the extraction path."""
    zip_file = project.downloaded_zip_file
    if not zip_file or not os.path.exists(zip_file.path):
        error_message = "The zip file does not exist in the file system."
        raise ValueError(error_message)

    fs = FileSystemStorage()
    extract_to_path = fs.path(f"transkribus_exports/{project.collection_id}/")
    if not fs.exists(extract_to_path):
        os.makedirs(extract_to_path)
    delete_all_in_folder(extract_to_path)

    celery_task.update_progress(2)
    return zip_file, extract_to_path


def extract_files_from_zip(zip_file, extract_to_path, project, celery_task):
    """Extract valid files from the zip archive."""
    copied_files = []
    with zipfile.ZipFile(zip_file.path, "r") as zip_ref:
        valid_files = [
            x
            for x in zip_ref.infolist()
            if ("/page/" in x.filename and x.filename.endswith(".xml"))
            or x.filename.endswith("metadata.xml")
            or x.filename.endswith("mets.xml")
        ]
        total_files = len(valid_files)

        for i, file_info in enumerate(valid_files, start=1):
            with zip_ref.open(file_info) as file_data:
                new_filename = generate_new_filename(file_info, project)
                new_filepath = Path(extract_to_path) / new_filename
                with open(new_filepath, "wb") as new_file:
                    new_file.write(file_data.read())
                    copied_files.append(new_filepath)

                # Update progress with detailed description
                progress = (i / total_files) * 30  # Allocate 30% for extraction
                celery_task.update_progress(
                    2 + progress,
                    text=f"Extracting file {i}/{total_files}: {file_info.filename}",
                )
    return copied_files


def generate_new_filename(file_info, project):
    """Generate a new filename for extracted files."""
    if file_info.filename.endswith(("metadata.xml", "mets.xml")):
        return f"{file_info.filename.split('/')[0]}_{file_info.filename.split('/')[-1]}"
    else:
        return f"{project.collection_id}_{uuid.uuid4().hex}.xml"


def process_extracted_files(copied_files, project, extracting_user, celery_task):
    """Process extracted files and create/update Document and Page instances.

    Returns:
        tuple: (document_count, page_count) The number of documents and pages created/updated
    """
    all_existing_documents = set(
        Document.objects.filter(project=project).values_list("document_id", flat=True)
    )
    total_files = len(copied_files)

    # Track document and page creation
    processed_documents = set()
    processed_pages = 0
    failed_files = 0

    # Separate regular XML files from metadata files
    page_xml_files = []
    metadata_files = []

    for file in copied_files:
        file_str = str(file)
        if file_str.endswith(("metadata.xml", "mets.xml")):
            metadata_files.append(file)
        else:
            page_xml_files.append(file)

    # Log metadata files found
    if celery_task.twf_task:
        celery_task.twf_task.text += (f"Found {len(metadata_files)} metadata files "
                                      f"and {len(page_xml_files)} page files.\n")
        celery_task.twf_task.save(update_fields=["text"])

    # Process page XML files
    for i, file in enumerate(page_xml_files, start=1):
        try:
            data = extract_transkribus_file_metadata(file)
            doc_id, is_new_page = handle_document_and_page(
                data,
                file,
                project,
                extracting_user,
                all_existing_documents,
                metadata_files,
            )

            # Track the processed document
            processed_documents.add(doc_id)

            # Count new pages
            if is_new_page:
                processed_pages += 1

            # Add more details about the document and page being processed
            celery_task.advance_task(
                text=f"Processed file {i}/{len(page_xml_files)}: Created/updated document {doc_id} "
                     f"with page {data['pageId']}",
                status="success",
            )
        except Exception as e:
            error_msg = f"Failed to process file {file}: {e}"
            logging.warning(error_msg)
            failed_files += 1
            file_name = os.path.basename(str(file))
            celery_task.advance_task(
                text=f"Error processing file {i}/{len(page_xml_files)}: {file_name} - {str(e)[:100]}",
                status="failure",
            )

        # Update progress with detailed information about the file being processed
        file_name = os.path.basename(str(file))
        progress = (i / total_files) * 30  # Allocate another 30% for processing
        celery_task.update_progress(
            32 + progress, text=f"Processing file {i}/{total_files}: {file_name}"
        )

    # Add summary to task text
    if celery_task.twf_task:
        celery_task.twf_task.text += "\nSummary of document processing:\n"
        celery_task.twf_task.text += (
            f"- Documents processed: {len(processed_documents)}\n"
        )
        celery_task.twf_task.text += f"- Pages created: {processed_pages}\n"
        celery_task.twf_task.text += f"- Failed files: {failed_files}\n"
        celery_task.twf_task.save(update_fields=["text"])

    return len(processed_documents), processed_pages


def parse_metadata_files(files, doc_id):
    """Extract metadata from metadata.xml and mets.xml files for a document.

    Args:
        files: List of file paths
        doc_id: Document ID to find matching metadata files

    Returns:
        dict: Metadata extracted from the files
    """
    metadata = {}

    # Look for matching metadata files
    metadata_file = None
    mets_file = None

    for file in files:
        file_str = str(file)
        file_basename = os.path.basename(file_str)

        # Check if the filename contains the document ID
        if doc_id in file_str:
            if file_str.endswith("metadata.xml"):
                metadata_file = file
            elif file_str.endswith("mets.xml"):
                mets_file = file

    # Extract metadata from metadata.xml
    if metadata_file:
        try:
            tree = ET.parse(metadata_file)
            root = tree.getroot()

            # Extract basic metadata
            title_elem = root.find(".//title")
            if title_elem is not None and title_elem.text:
                metadata["title"] = title_elem.text.strip()

            author_elem = root.find(".//author")
            if author_elem is not None and author_elem.text:
                metadata["author"] = author_elem.text.strip()

            # Try to extract more fields
            for field in [
                "writer",
                "description",
                "language",
                "authority",
                "external_id",
            ]:
                elem = root.find(f".//{field}")
                if elem is not None and elem.text:
                    metadata[field] = elem.text.strip()

            # Add all other available fields
            for elem in root.findall(".//*"):
                if elem.text and elem.text.strip() and elem.tag not in metadata:
                    metadata[elem.tag] = elem.text.strip()
        except Exception as e:
            logging.warning(f"Error parsing metadata file for document {doc_id}: {e}")

    # Extract additional metadata from mets.xml
    if mets_file:
        try:
            tree = ET.parse(mets_file)
            root = tree.getroot()

            # Extract metadata from mets file (often has more detailed info)
            for elem in root.findall(".//*"):
                if elem.text and elem.text.strip() and elem.tag not in metadata:
                    # Convert namespace prefixed tags to plain tag names
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    metadata[tag] = elem.text.strip()
        except Exception as e:
            logging.warning(f"Error parsing mets file for document {doc_id}: {e}")

    return metadata


def handle_document_and_page(
    data, file, project, extracting_user, existing_documents, metadata_files=None
):
    """Handle creation/updating of Document and Page instances.

    Args:
        data: Page metadata
        file: XML file path
        project: Project instance
        extracting_user: User performing the extraction
        existing_documents: Set of existing document IDs
        metadata_files: List of all XML files (for metadata extraction)

    Returns:
        tuple: (document_id, is_new_page) The document ID and whether a new page was created
    """
    doc_instance, doc_created = Document.objects.get_or_create(
        project=project,
        document_id=data["docId"],
        defaults={"created_by": extracting_user, "modified_by": extracting_user},
    )
    existing_documents.discard(doc_instance.document_id)

    # Extract and update document metadata if we have metadata files
    if metadata_files:
        document_metadata = parse_metadata_files(metadata_files, data["docId"])

        # Update document metadata
        if document_metadata:
            # Set document title if available
            if "title" in document_metadata and not doc_instance.title:
                doc_instance.title = document_metadata["title"]

            # Update document metadata field if it exists
            if hasattr(doc_instance, "metadata"):
                # Merge with existing metadata but wrap in "transkribus" key
                existing_metadata = doc_instance.metadata or {}

                # Create or update the "transkribus" key
                if "transkribus" not in existing_metadata:
                    existing_metadata["transkribus"] = {}

                # Add all extracted metadata to the transkribus key
                existing_metadata["transkribus"].update(document_metadata)
                doc_instance.metadata = existing_metadata

            # Save document with updated metadata
            doc_instance.save(current_user=extracting_user)

    page_instance, page_created = Page.objects.get_or_create(
        document=doc_instance,
        tk_page_id=data["pageId"],
        tk_page_number=data["pageNr"],
        defaults={"created_by": extracting_user, "modified_by": extracting_user},
    )
    # Properly assign the file to the FileField by opening and saving the file
    with open(file, "rb") as f:
        file_name = os.path.basename(str(file))
        page_instance.xml_file.save(file_name, f, save=False)

    # Store TranskribusMetadata in page.metadata under 'transkribus' key
    if hasattr(page_instance, "metadata"):
        existing_metadata = page_instance.metadata or {}

        # Create or update the "transkribus" key
        if "transkribus" not in existing_metadata:
            existing_metadata["transkribus"] = {}

        # Store all extracted TranskribusMetadata attributes
        existing_metadata["transkribus"].update(data)
        page_instance.metadata = existing_metadata

    page_instance.save(current_user=extracting_user)

    return doc_instance.document_id, page_created


def parse_pages(project, extracting_user, celery_task):
    """Parse pages and extract data."""
    all_pages = Page.objects.filter(document__project=project).order_by(
        "document__document_id", "tk_page_number"
    )
    total_pages = all_pages.count()

    # Set total items for progress tracking
    celery_task.set_total_items(total_pages)

    successfully_parsed = 0
    failed_parsing = 0

    for i, page in enumerate(all_pages, start=1):
        try:
            page_parser = PageFileParser(
                parser_config={
                    "line_type": "TextRegion",
                    "logging": {"level": logging.WARN},
                    "export": {
                        "json": {
                            "print_files": True,
                            "print_filename": True,
                            "print_file_meta_data": True,
                        }
                    },
                }
            )
            page_parser.add_file(page.xml_file.path)
            page_parser.parse()
            page.parsed_data = page_parser.get_alto_files()[
                0
            ].get_standalone_json_object()
            page.last_parsed_at = timezone.now()
            page.save(current_user=extracting_user)

            successfully_parsed += 1
            celery_task.advance_task(
                text=f"Parsed page {i}/{total_pages}: Page {page.tk_page_id} "
                     f"(#{page.tk_page_number}) from document {page.document.document_id}",
                status="success",
            )
        except Exception as e:
            failed_parsing += 1
            error_msg = (f"Failed to parse page {page.tk_page_id} from "
                         f"document {page.document.document_id}: {str(e)}")
            logger.error(error_msg)
            celery_task.advance_task(
                text=f"Error parsing page {i}/{total_pages}: Page {page.tk_page_id} "
                     f"(#{page.tk_page_number}) from document {page.document.document_id} - {str(e)[:100]}",
                status="failure",
            )

    # Add summary to task text
    if celery_task.twf_task:
        celery_task.twf_task.text += "\nParsing summary:\n"
        celery_task.twf_task.text += (
            f"- Successfully parsed: {successfully_parsed} pages\n"
        )
        if failed_parsing > 0:
            celery_task.twf_task.text += f"- Failed to parse: {failed_parsing} pages\n"
        celery_task.twf_task.save(update_fields=["text"])


def enrich_documents_with_api_metadata(project, documents_to_enrich, user, celery_task):
    """
    Enrich documents with metadata from Transkribus API.

    Fetches additional metadata (labels, tags, excluded status) from the Transkribus API
    that is not available in the PageXML export.

    Args:
        project: Project object
        documents_to_enrich: Set of document IDs to enrich
        user: User performing the sync
        celery_task: BaseTWFTask instance for progress tracking

    Returns:
        int: Number of documents successfully enriched
    """
    if not documents_to_enrich:
        return 0

    # Get Transkribus credentials
    try:
        transkribus_credentials = project.get_credentials("transkribus")
        username = transkribus_credentials.get("username")
        password = transkribus_credentials.get("password")
        collection_id = project.collection_id

        if not username or not password or not collection_id:
            logger.warning(
                "Missing Transkribus credentials or collection ID, skipping API enrichment"
            )
            return 0

    except Exception as e:
        logger.warning(f"Could not retrieve Transkribus credentials: {e}")
        return 0

    # Initialize API client
    api_client = TranskribusAPIClient(username, password)

    if not api_client.authenticate():
        logger.error("Failed to authenticate with Transkribus API, skipping enrichment")
        if celery_task.twf_task:
            celery_task.twf_task.text += ("  ⚠ Failed to authenticate with Transkribus API, "
                                          "skipping metadata enrichment\n")
        return 0

    if celery_task.twf_task:
        celery_task.twf_task.text += (f"\n📡 Enriching {len(documents_to_enrich)} documents "
                                      f"with Transkribus API metadata...\n")
        celery_task.twf_task.save(update_fields=["text"])

    enriched_count = 0
    total_docs = len(documents_to_enrich)

    for idx, doc_id in enumerate(documents_to_enrich, start=1):
        try:
            # Get the document instance
            doc_instance = Document.objects.get(project=project, document_id=doc_id)

            # Fetch enriched metadata from API
            enriched_data = api_client.enrich_document_metadata(
                collection_id, int(doc_id)
            )

            if enriched_data:
                # Update document metadata
                existing_metadata = doc_instance.metadata or {}
                if "transkribus_api" not in existing_metadata:
                    existing_metadata["transkribus_api"] = {}

                doc_labels = enriched_data.get("labels", [])
                existing_metadata["transkribus_api"]["labels"] = doc_labels
                existing_metadata["transkribus_api"]["page_labels_available"] = (
                    enriched_data.get("page_labels_available", [])
                )

                # Check for "Exclude" label (same logic as pages)
                is_excluded = any(
                    label.get("name", "").lower() == "exclude" for label in doc_labels
                )
                existing_metadata["transkribus_api"]["is_excluded"] = is_excluded

                doc_instance.metadata = existing_metadata

                # Update is_ignored field based on "Exclude" label
                if is_excluded:
                    doc_instance.is_ignored = True
                    if celery_task.twf_task:
                        celery_task.twf_task.text += f"  ⊘ Document {doc_id} marked as excluded (has 'Exclude' label)\n"
                        celery_task.twf_task.save(update_fields=["text"])

                doc_instance.save(current_user=user)

                # Update page metadata with labels and exclusion status
                page_data = enriched_data.get("pages", {})
                for page_id, page_info in page_data.items():
                    try:
                        page_instance = Page.objects.get(
                            document=doc_instance, tk_page_id=page_id
                        )
                        page_metadata = page_instance.metadata or {}

                        if "transkribus_api" not in page_metadata:
                            page_metadata["transkribus_api"] = {}

                        page_metadata["transkribus_api"]["labels"] = page_info.get(
                            "labels", []
                        )
                        page_metadata["transkribus_api"]["is_excluded"] = page_info.get(
                            "is_excluded", False
                        )

                        page_instance.metadata = page_metadata

                        # Update is_ignored field based on "Exclude" label
                        if page_info.get("is_excluded", False):
                            page_instance.is_ignored = True

                        page_instance.save(current_user=user)

                    except Page.DoesNotExist:
                        logger.warning(
                            f"Page {page_id} not found for document {doc_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to update page {page_id} metadata: {e}")

                enriched_count += 1

                if celery_task.twf_task and idx % 10 == 0:
                    celery_task.twf_task.text += (
                        f"  ✓ Enriched {idx}/{total_docs} documents\n"
                    )
                    celery_task.twf_task.save(update_fields=["text"])

        except Document.DoesNotExist:
            logger.warning(f"Document {doc_id} not found during enrichment")
        except Exception as e:
            logger.error(f"Failed to enrich document {doc_id}: {e}")
            if celery_task.twf_task:
                celery_task.twf_task.text += (
                    f"  ✗ Failed to enrich document {doc_id}: {e}\n"
                )

    if celery_task.twf_task:
        celery_task.twf_task.text += (f"✓ Successfully enriched {enriched_count}/{total_docs} "
                                      f"documents with API metadata\n\n")
        celery_task.twf_task.save(update_fields=["text"])

    return enriched_count


def sync_documents_and_pages(
    copied_files, project, user, celery_task, delete_removed=True
):
    """
    Synchronize documents and pages with Transkribus export.

    This function handles the smart synchronization of documents and pages:
    - Adds new documents and pages
    - Updates existing documents and pages
    - Optionally deletes documents removed from Transkribus
    - Enriches documents with metadata from Transkribus API

    Args:
        copied_files: List of extracted file paths
        project: Project object
        user: User performing the sync
        celery_task: BaseTWFTask instance for progress tracking
        delete_removed: If True, delete documents not in the export

    Returns:
        dict: Statistics about the sync operation:
        {
            'added': int,           # New documents created
            'updated': int,         # Existing documents updated
            'deleted': int,         # Documents removed
            'pages_added': int,     # New pages created
            'pages_updated': int,   # Existing pages updated
            'pages_deleted': int    # Pages removed
        }
    """
    # Track all documents and pages in the export
    documents_in_export = set()
    pages_in_export = defaultdict(set)  # doc_instance.id -> set of tk_page_id

    # Separate page XML files from metadata files
    page_xml_files = []
    metadata_files = []

    for file in copied_files:
        file_str = str(file)
        if file_str.endswith(("metadata.xml", "mets.xml")):
            metadata_files.append(file)
        else:
            page_xml_files.append(file)

    if celery_task.twf_task:
        celery_task.twf_task.text += (f"Found {len(metadata_files)} "
                                      f"metadata files and {len(page_xml_files)} page files.\n")
        celery_task.twf_task.save(update_fields=["text"])

    stats = {
        "added": 0,
        "updated": 0,
        "deleted": 0,
        "pages_added": 0,
        "pages_updated": 0,
        "pages_deleted": 0,
    }

    # Track document changes for sync history
    doc_changes = defaultdict(
        lambda: {
            "pages": {"added": [], "updated": [], "deleted": []},
            "metadata_updated": False,
        }
    )

    # Process page XML files
    total_files = len(page_xml_files)
    for i, file in enumerate(page_xml_files, start=1):
        try:
            data = extract_transkribus_file_metadata(file)
            doc_id = data["docId"]
            page_id = data["pageId"]
            page_nr = data["pageNr"]

            # Track this document
            documents_in_export.add(doc_id)

            # Get or create document
            doc_instance, doc_created = Document.objects.get_or_create(
                project=project,
                document_id=doc_id,
                defaults={"created_by": user, "modified_by": user},
            )

            if doc_created:
                stats["added"] += 1
                if celery_task.twf_task:
                    celery_task.twf_task.text += f"  + Created new document {doc_id}\n"
            else:
                stats["updated"] += 1

            # Extract and update document metadata if available
            if metadata_files:
                document_metadata = parse_metadata_files(metadata_files, doc_id)
                if document_metadata:
                    # Set document title if available and not already set
                    if "title" in document_metadata and not doc_instance.title:
                        doc_instance.title = document_metadata["title"]

                    # Update metadata field
                    if hasattr(doc_instance, "metadata"):
                        existing_metadata = doc_instance.metadata or {}
                        if "transkribus" not in existing_metadata:
                            existing_metadata["transkribus"] = {}
                        existing_metadata["transkribus"].update(document_metadata)
                        doc_instance.metadata = existing_metadata
                        doc_changes[doc_instance.id]["metadata_updated"] = True

                    doc_instance.save(current_user=user)

            # Get or create page
            page_instance, page_created = Page.objects.get_or_create(
                document=doc_instance,
                tk_page_id=page_id,
                tk_page_number=page_nr,
                defaults={"created_by": user, "modified_by": user},
            )
            pages_in_export[doc_instance.id].add(page_id)

            # Update the page XML file
            with open(file, "rb") as f:
                file_name = os.path.basename(str(file))
                page_instance.xml_file.save(file_name, f, save=False)

            # Store TranskribusMetadata in page.metadata under 'transkribus' key
            if hasattr(page_instance, "metadata"):
                existing_metadata = page_instance.metadata or {}

                # Create or update the "transkribus" key
                if "transkribus" not in existing_metadata:
                    existing_metadata["transkribus"] = {}

                # Store all extracted TranskribusMetadata attributes
                existing_metadata["transkribus"].update(data)
                page_instance.metadata = existing_metadata

            page_instance.save(current_user=user)

            if page_created:
                stats["pages_added"] += 1
                doc_changes[doc_instance.id]["pages"]["added"].append(page_instance.id)
            else:
                stats["pages_updated"] += 1
                doc_changes[doc_instance.id]["pages"]["updated"].append(
                    page_instance.id
                )

            # Advance progress
            progress = (i / total_files) * 30  # Allocate 30% for document/page sync
            celery_task.update_progress(
                32 + progress,
                text=f"Processing file {i}/{total_files}: document {doc_id}",
            )

        except Exception as e:
            error_msg = f"Failed to process file {file}: {e}"
            logger.warning(error_msg)
            if celery_task.twf_task:
                celery_task.twf_task.text += f"  ✗ Error: {error_msg}\n"

    # Enrich documents with API metadata (labels, tags, excluded status)
    enrich_documents_with_api_metadata(project, documents_in_export, user, celery_task)

    # Parse all pages
    parse_pages(project, user, celery_task)

    # Handle deleted pages within existing documents (if enabled)
    if delete_removed:
        for doc_internal_id, seen_page_ids in pages_in_export.items():
            try:
                doc = Document.objects.get(id=doc_internal_id)
                pages_to_delete = Page.objects.filter(document=doc).exclude(
                    tk_page_id__in=seen_page_ids
                )
                deleted_count = pages_to_delete.count()
                if deleted_count > 0:
                    for page in pages_to_delete:
                        doc_changes[doc_internal_id]["pages"]["deleted"].append(page.id)
                    stats["pages_deleted"] += deleted_count
                    pages_to_delete.delete()
                    if celery_task.twf_task:
                        celery_task.twf_task.text += (
                            f"  - Deleted {deleted_count} removed page(s) "
                            f"from document {doc.document_id}\n"
                        )
            except Document.DoesNotExist:
                pass

    # Handle deleted documents (if enabled)
    if delete_removed:
        all_project_docs = Document.objects.filter(project=project)
        for doc in all_project_docs:
            if doc.document_id not in documents_in_export:
                # Document was removed from Transkribus
                stats["deleted"] += 1

                # Count deleted pages
                deleted_page_count = doc.pages.count()
                stats["pages_deleted"] += deleted_page_count

                # Create sync history before deletion
                DocumentSyncHistory.objects.create(
                    document=doc,
                    task=celery_task.twf_task,
                    project=project,
                    user=user,
                    sync_type="deleted",
                    changes={
                        "pages": {
                            "deleted": list(doc.pages.values_list("id", flat=True))
                        },
                        "reason": "Document not present in Transkribus export",
                    },
                    created_by=user,
                    modified_by=user,
                )

                if celery_task.twf_task:
                    celery_task.twf_task.text += (
                        f"  - Deleted document {doc.document_id} (not in export)\n"
                    )

                doc.delete()

    # Create sync history for processed documents
    for doc_id, changes in doc_changes.items():
        try:
            document = Document.objects.get(id=doc_id)

            # Determine if this is a new document or updated
            sync_type = (
                "created"
                if document.id
                not in [d.id for d in Document.objects.filter(project=project)]
                else "updated"
            )

            # Only create history if there were actual changes
            if (
                changes["pages"]["added"]
                or changes["pages"]["updated"]
                or changes["metadata_updated"]
            ):
                DocumentSyncHistory.objects.create(
                    document=document,
                    task=celery_task.twf_task,
                    project=project,
                    user=user,
                    sync_type=sync_type,
                    changes=changes,
                    created_by=user,
                    modified_by=user,
                )
        except Document.DoesNotExist:
            logger.warning(f"Document {doc_id} not found when creating sync history")

    return stats

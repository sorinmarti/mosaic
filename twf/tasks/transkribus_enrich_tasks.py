"""Celery tasks for enriching documents with Transkribus API metadata."""

import logging

from celery import shared_task

from twf.clients.transkribus_api_client import TranskribusAPIClient
from twf.models import Document, Page
from twf.tasks.task_base import BaseTWFTask

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def enrich_transkribus_metadata_task(self, project_id, user_id, **kwargs):
    """
    Celery task to enrich documents with Transkribus API metadata.

    Fetches additional metadata (labels, tags, excluded status) from the Transkribus API
    and stores it in the document and page metadata fields.

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Optional parameters:
            - force: Boolean, re-enrich even if metadata exists (default: False)
            - document_ids: List of specific document IDs to enrich (default: all)

    Returns:
        dict: Statistics about the enrichment operation
    """
    force = kwargs.get("force", False)
    document_ids = kwargs.get("document_ids", None)

    self.update_progress(5, text="Starting Transkribus API enrichment...")

    # Get Transkribus credentials
    try:
        transkribus_credentials = self.project.get_credentials("transkribus")
        username = transkribus_credentials.get("username")
        password = transkribus_credentials.get("password")
        collection_id = self.project.collection_id

        if not username or not password or not collection_id:
            error_msg = "Missing Transkribus credentials or collection ID"
            logger.error(error_msg)
            self.update_progress(100, text=f"✗ Error: {error_msg}")
            self.end_task(status="FAILURE")
            return

    except Exception as e:
        error_msg = f"Could not retrieve Transkribus credentials: {e}"
        logger.error(error_msg)
        self.update_progress(100, text=f"✗ Error: {error_msg}")
        self.end_task(status="FAILURE")
        return

    self.update_progress(10, text="Retrieved Transkribus credentials")

    # Determine which documents to enrich
    if document_ids:
        documents = Document.objects.filter(
            project=self.project, document_id__in=document_ids
        )
    else:
        documents = Document.objects.filter(project=self.project)

    total_documents = documents.count()

    if total_documents == 0:
        self.update_progress(100, text="No documents found to enrich")
        self.end_task(status="SUCCESS")
        return

    self.update_progress(15, text=f"Found {total_documents} document(s) to process")

    # Initialize API client
    api_client = TranskribusAPIClient(username, password)

    self.update_progress(20, text="Authenticating with Transkribus API...")

    if not api_client.authenticate():
        error_msg = "Failed to authenticate with Transkribus API"
        logger.error(error_msg)
        self.update_progress(100, text=f"✗ Error: {error_msg}")
        self.end_task(status="FAILURE")
        return

    self.update_progress(25, text="✓ Authentication successful\n")

    # Enrich documents
    enriched_count = 0
    skipped_count = 0
    error_count = 0
    pages_updated = 0
    pages_excluded = 0

    for idx, doc_instance in enumerate(documents, start=1):
        doc_id = doc_instance.document_id

        # Calculate progress (25% to 95%)
        progress = 25 + ((idx / total_documents) * 70)

        # Check if already enriched (unless force is enabled)
        if not force and doc_instance.metadata.get("transkribus_api"):
            self.update_progress(
                progress,
                text=f"[{idx}/{total_documents}] Document {doc_id}: Skipped (already enriched)",
            )
            skipped_count += 1
            continue

        try:
            # Fetch enriched metadata from API
            self.update_progress(
                progress,
                text=f"[{idx}/{total_documents}] Document {doc_id}: Fetching metadata...",
            )

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

                doc_instance.save(current_user=self.user)

                # Update page metadata with labels and exclusion status
                page_data = enriched_data.get("pages", {})
                doc_pages_updated = 0
                doc_pages_excluded = 0

                for page_id, page_info in page_data.items():
                    try:
                        page_instance = doc_instance.pages.get(tk_page_id=page_id)
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
                            doc_pages_excluded += 1

                        page_instance.save(current_user=self.user)
                        doc_pages_updated += 1

                    except Page.DoesNotExist:
                        logger.warning(
                            f"Page {page_id} not found for document {doc_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to update page {page_id} metadata: {e}")

                pages_updated += doc_pages_updated
                pages_excluded += doc_pages_excluded
                enriched_count += 1

                self.update_progress(
                    progress,
                    text=f"[{idx}/{total_documents}] Document {doc_id}: "
                    f"✓ Enriched ({doc_pages_updated} pages, {doc_pages_excluded} excluded)",
                )

            else:
                error_count += 1
                self.update_progress(
                    progress,
                    text=f"[{idx}/{total_documents}] Document {doc_id}: Failed to fetch metadata",
                )

        except Exception as e:
            error_count += 1
            logger.error(f"Failed to enrich document {doc_id}: {e}")
            self.update_progress(
                progress,
                text=f"[{idx}/{total_documents}] Document {doc_id}: Error - {e}",
            )

    # Final summary
    summary_text = f"\n{'='*60}\n"
    summary_text += "ENRICHMENT COMPLETE\n"
    summary_text += f"{'='*60}\n"
    summary_text += f"Total documents: {total_documents}\n"
    summary_text += f"✓ Enriched: {enriched_count}\n"
    summary_text += f"  - Pages updated: {pages_updated}\n"
    summary_text += f"  - Pages excluded: {pages_excluded}\n"

    if skipped_count > 0:
        summary_text += f"○ Skipped: {skipped_count} (already had metadata)\n"

    if error_count > 0:
        summary_text += f"✗ Errors: {error_count}\n"

    self.update_progress(100, text=summary_text)

    # Return statistics
    result = {
        "total": total_documents,
        "enriched": enriched_count,
        "skipped": skipped_count,
        "errors": error_count,
        "pages_updated": pages_updated,
        "pages_excluded": pages_excluded,
    }

    self.end_task(status="SUCCESS" if error_count == 0 else "PARTIAL", result=result)

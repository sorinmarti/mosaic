"""Celery tasks for processing documents in a project."""

import logging
from django.utils import timezone
from celery import shared_task
from twf.tasks.task_base import BaseTWFTask
from twf.models import PageTag

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def search_ai_for_docs(self, project_id, user_id, **kwargs):
    """
    Unified task for AI batch processing of documents.

    Uses AIConfiguration which contains all AI settings (provider, model, prompt, etc.).

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Must include:
            - ai_configuration_id: ID of the AIConfiguration to use
            - prompt_mode (optional): Prompt mode for multimodal
            - request_level (optional): Request level
    """
    from twf.models import AIConfiguration

    self.validate_task_parameters(kwargs, ["ai_configuration_id"])

    # Load the AI configuration
    ai_config_id = kwargs.get("ai_configuration_id")
    try:
        ai_config = AIConfiguration.objects.get(id=ai_config_id, project=self.project)
    except AIConfiguration.DoesNotExist:
        raise ValueError(f"AIConfiguration with id {ai_config_id} not found for this project")

    prompt_mode = kwargs.get("prompt_mode", "text_only")

    # Get document count and filter active documents if needed
    documents = self.project.documents.all()
    doc_count = documents.count()

    # Update task with document count information
    if self.twf_task:
        self.twf_task.text += (
            f"Found {doc_count} documents to process with {ai_config.provider} ({ai_config.name}).\n"
        )
        self.twf_task.save(update_fields=["text"])

    # Process all documents using the AI configuration settings
    self.process_ai_request(
        documents,
        ai_config.provider,
        ai_config.prompt_template,
        ai_config.system_role,
        ai_config.provider,
        prompt_mode=prompt_mode,
        model=ai_config.model,
        api_key=ai_config.api_key,
    )

    return {"status": "completed", "documents_processed": doc_count}


@shared_task(bind=True, base=BaseTWFTask)
def build_cross_references(self, project_id, user_id, **kwargs):
    """
    Build document cross-references from tag additional_information keys.

    For each document, finds all tags whose additional_information contains the
    given reference_key, groups them by target document ID, and writes a
    structured connection block to document.metadata[storage_key].

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Must include:
            - reference_key: Key in additional_information (e.g. 'transkribus_doc_id')
            - storage_key (optional): Metadata key to store results (default: 'corpus_connections')
    """
    self.validate_task_parameters(kwargs, ["reference_key"])

    reference_key = kwargs["reference_key"]
    storage_key = kwargs.get("storage_key", "corpus_connections")

    documents = list(self.project.documents.all())
    self.set_total_items(len(documents))

    if self.twf_task:
        self.twf_task.text += (
            f"Building cross-references using key '{reference_key}' "
            f"for {len(documents)} documents.\n"
        )
        self.twf_task.save(update_fields=["text"])

    # Pre-fetch all documents in the project keyed by document_id for fast in-corpus lookup
    corpus_map = {doc.document_id: doc for doc in documents}

    for document in documents:
        tags = (
            PageTag.objects.filter(
                page__document=document,
                additional_information__has_key=reference_key,
            )
            .select_related("page")
        )

        if not tags.exists():
            document.metadata[storage_key] = {
                "source_key": reference_key,
                "built_at": timezone.now().isoformat(),
                "total_connections": 0,
                "total_mentions": 0,
                "connections": [],
            }
            document.save(current_user=self.user)
            self.advance_task(status="skipped")
            continue

        # Group mentions by target document id
        connections_map = {}
        for tag in tags:
            target_id = str(tag.additional_information.get(reference_key, "")).strip()
            if not target_id:
                continue
            if target_id not in connections_map:
                connections_map[target_id] = []
            connections_map[target_id].append({
                "tag_pk": tag.pk,
                "variation": tag.variation,
                "variation_type": tag.variation_type,
                "page_pk": tag.page.pk,
                "page_number": tag.page.tk_page_number,
                "line_text": tag.line_text,
            })

        connections = []
        for target_id, mentions in connections_map.items():
            target_doc = corpus_map.get(target_id)
            connections.append({
                "target_doc_id": target_id,
                "target_doc_pk": target_doc.pk if target_doc else None,
                "target_doc_title": target_doc.title if target_doc else None,
                "in_corpus": target_doc is not None,
                "weight": len(mentions),
                "mentions": mentions,
            })

        connections.sort(key=lambda c: c["weight"], reverse=True)
        total_mentions = sum(c["weight"] for c in connections)

        document.metadata[storage_key] = {
            "source_key": reference_key,
            "built_at": timezone.now().isoformat(),
            "total_connections": len(connections),
            "total_mentions": total_mentions,
            "connections": connections,
        }
        document.save(current_user=self.user)
        self.advance_task(status="success")

    return {"status": "completed", "documents_processed": len(documents)}

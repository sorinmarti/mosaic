"""Celery tasks for processing documents in a project."""

import logging
from celery import shared_task
from twf.tasks.task_base import BaseTWFTask

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

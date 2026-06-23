""" Celery tasks for creating collections """

import logging

from celery import shared_task

from twf.models import CollectionItem
from twf.tasks.task_base import BaseTWFTask

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def create_collection(self, project_id, user_id, **kwargs):
    """Create a collection for a project"""
    self.validate_task_parameters(kwargs, ["collection_name", "collection_description"])

    self.end_task()


@shared_task(bind=True, base=BaseTWFTask)
def search_ai_for_collection(self, project_id, user_id, **kwargs):
    """
    Unified task for AI batch processing of collection items.

    Uses AIConfiguration which contains all AI settings (provider, model, prompt, etc.).

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Must include:
            - collection_id: ID of the collection to process
            - ai_configuration_id: ID of the AIConfiguration to use
    """
    from twf.models import AIConfiguration

    self.validate_task_parameters(kwargs, ["collection_id", "ai_configuration_id"])

    # Load the AI configuration
    ai_config_id = kwargs.get("ai_configuration_id")
    try:
        ai_config = AIConfiguration.objects.get(id=ai_config_id, project=self.project)
    except AIConfiguration.DoesNotExist:
        raise ValueError(f"AIConfiguration with id {ai_config_id} not found for this project")

    collection = self.project.collections.get(id=kwargs.get("collection_id"))

    # Process collection items using the AI configuration settings
    self.process_ai_request(
        collection.items.all(),
        ai_config.provider,
        ai_config.prompt_template,
        ai_config.system_role,
        ai_config.provider,
        model=ai_config.model,
        api_key=ai_config.api_key,
    )


@shared_task(bind=True, base=BaseTWFTask)
def search_ai_for_collection_item(self, project_id, user_id, **kwargs):
    """
    Unified task for AI request (supervised) processing of a single collection item.

    Uses AIConfiguration which contains all AI settings (provider, model, prompt, etc.).

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Must include:
            - item_id: ID of the collection item to process
            - ai_configuration_id: ID of the AIConfiguration to use
    """
    from twf.models import AIConfiguration

    self.validate_task_parameters(kwargs, ["item_id", "ai_configuration_id"])

    # Load the AI configuration
    ai_config_id = kwargs.get("ai_configuration_id")
    try:
        ai_config = AIConfiguration.objects.get(id=ai_config_id, project=self.project)
    except AIConfiguration.DoesNotExist:
        raise ValueError(f"AIConfiguration with id {ai_config_id} not found for this project")

    item = CollectionItem.objects.get(id=kwargs.get("item_id"))

    # Process single collection item using the AI configuration settings
    self.process_ai_request(
        [item],
        ai_config.provider,
        ai_config.prompt_template,
        ai_config.system_role,
        ai_config.provider,
        model=ai_config.model,
        api_key=ai_config.api_key,
    )

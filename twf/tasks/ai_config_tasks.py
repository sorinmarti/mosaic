"""Tasks for AI Configuration testing and execution."""

import json
import logging

from celery import shared_task

from twf.tasks.task_base import BaseTWFTask

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def test_ai_config_task(self, project_id, user_id, ai_config_id, test_context):
    """
    Test an AI configuration with provided context.

    Parameters
    ----------
    project_id : int
        The project ID
    user_id : int
        The user ID
    ai_config_id : int
        The AI configuration ID to test
    test_context : dict or str
        Context variables for the prompt template (as dict or JSON string)
    """
    from twf.models import AIConfiguration

    try:
        # Get the AI configuration
        ai_config = AIConfiguration.objects.get(id=ai_config_id, project_id=project_id)

        # Log task start
        logger.info(f"Testing AI config: {ai_config.name}")
        logger.info(f"Provider: {ai_config.provider}, Model: {ai_config.model}")

        if self.twf_task:
            self.twf_task.text += f"Testing AI Configuration: {ai_config.name}\n"
            self.twf_task.text += f"Provider: {ai_config.provider}, Model: {ai_config.model}\n"
            self.twf_task.save(update_fields=["text"])

        # Parse context if it's a string
        if isinstance(test_context, str):
            test_context = json.loads(test_context)

        logger.info(f"Test context: {json.dumps(test_context, indent=2)}")
        if self.twf_task:
            self.twf_task.text += f"Test context: {json.dumps(test_context, indent=2)}\n"
            self.twf_task.save(update_fields=["text"])

        # Set progress
        self.set_total_items(1)
        self.update_progress(50, f"Executing AI request to {ai_config.provider}...")

        # Execute the configuration
        response_text, duration = ai_config.execute(test_context)

        # Log results
        logger.info(f"Response received in {duration:.2f} seconds")
        logger.info(f"Response length: {len(response_text)} characters")

        if self.twf_task:
            self.twf_task.text += f"\nResponse received in {duration:.2f} seconds\n"
            self.twf_task.text += f"Response length: {len(response_text)} characters\n"
            self.twf_task.text += f"\n{'='*60}\n"
            self.twf_task.text += f"RESPONSE:\n"
            self.twf_task.text += f"{'='*60}\n"
            self.twf_task.text += f"{response_text}\n"
            self.twf_task.text += f"{'='*60}\n"
            self.twf_task.save(update_fields=["text"])

        # Store result in task metadata
        result_data = {
            "success": True,
            "ai_config_id": ai_config_id,
            "ai_config_name": ai_config.name,
            "provider": ai_config.provider,
            "model": ai_config.model,
            "test_context": test_context,
            "response": response_text,
            "duration": duration,
        }

        # Complete task successfully
        self.end_task(status="SUCCESS", **result_data)

        return result_data

    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in test context: {str(e)}"
        logger.error(error_msg)
        if self.twf_task:
            self.twf_task.text += f"\nERROR: {error_msg}\n"
            self.twf_task.save(update_fields=["text"])
        self.end_task(status="FAILURE", error_msg=error_msg)
        raise

    except Exception as e:
        error_msg = f"Test failed: {str(e)}"
        logger.error(error_msg)
        if self.twf_task:
            self.twf_task.text += f"\nERROR: {error_msg}\n"
            self.twf_task.save(update_fields=["text"])
        self.end_task(status="FAILURE", error_msg=error_msg)
        raise

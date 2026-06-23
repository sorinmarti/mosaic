""" This module contains the views for checking the status of a task and canceling a task. """

import logging

from celery.result import AsyncResult
from django.http import JsonResponse
from twf.models import Task

logger = logging.getLogger(__name__)


def task_status_view(request, task_id):
    """View to check the status of a task by its task_id and return the progress or result."""
    try:
        # Get the task result by its task_id
        task_result = AsyncResult(task_id)

        if task_result.state == "PENDING":
            # Task is not yet started
            response_data = {
                "status": "PENDING",
                "progress": 0,
                "text": "Task is pending...",
            }
        # If the task is in progress, return the progress meta information
        if task_result.state == "PROGRESS":
            # Get the task from the database to retrieve the full log
            try:
                # Try all possible ways to find the task
                db_task = Task.objects.filter(celery_task_id=task_id).first()

                if not db_task:
                    # Try using task_id directly (it might be the DB task ID, not celery ID)
                    db_task = Task.objects.filter(pk=task_id).first()

                if not db_task:
                    # Try looking for a task with this ID in meta field
                    db_task = Task.objects.filter(meta__contains=task_id).first()

                full_text = (
                    db_task.text if db_task else task_result.info.get("text", "")
                )
                logger.info(
                    f"Task status - Found task in DB: {bool(db_task)}, task_id: {task_id}, "
                    f"text length: {len(full_text) if full_text else 0}"
                )
            except Exception as e:
                logger.error(f"Error retrieving full task text: {e}")
                full_text = task_result.info.get("text", "")

            # Include db_task_id if we found it in the database
            db_task_id = db_task.pk if db_task else None

            response_data = {
                "status": "PROGRESS",
                "current": task_result.info.get("current", 0),  # Current progress step
                "total": task_result.info.get("total", 1),  # Total steps
                "progress": (
                    task_result.info.get("current", 0)
                    / task_result.info.get("total", 1)
                )
                * 100,
                "text": task_result.info.get("text", ""),  # Latest progress update
                "full_text": full_text,  # Complete task log
                "db_task_id": db_task_id,  # Database ID for the task
            }

        # If the task is completed, return the result
        elif task_result.state == "SUCCESS":
            # Try to get the database task ID
            try:
                db_task = Task.objects.filter(celery_task_id=task_id).first()
                if not db_task:
                    db_task = Task.objects.filter(meta__contains=task_id).first()
                db_task_id = db_task.pk if db_task else None
            except Exception:
                db_task_id = None

            response_data = {
                "status": "SUCCESS",
                "result": task_result.result,
                "db_task_id": db_task_id,  # Include the database task ID
            }

        # If the task has failed, return the error message
        elif task_result.state == "FAILURE":
            # Try to get the database task ID
            try:
                db_task = Task.objects.filter(celery_task_id=task_id).first()
                if not db_task:
                    db_task = Task.objects.filter(meta__contains=task_id).first()
                db_task_id = db_task.pk if db_task else None
            except Exception:
                db_task_id = None

            response_data = {
                "status": "FAILURE",
                "error": (
                    str(task_result.info)
                    if isinstance(task_result.info, Exception)
                    else task_result.info
                ),
                "db_task_id": db_task_id,  # Include the database task ID
            }

        # Handle other states (PENDING, REVOKED, etc.)
        else:
            response_data = {"status": task_result.state}

        # Return the response as JSON
        return JsonResponse(response_data)

    except Exception as e:
        # Catch any other unexpected exceptions and return as error
        logger.error("Error in task_status_view: %s", str(e))
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

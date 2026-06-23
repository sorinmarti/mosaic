"""Views for creating, reading, updating, and deleting projects."""

import os
import shutil
from django.conf import settings
from django.db import transaction
from celery.result import AsyncResult
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

from twf.models import Project, PageTag, Task, Export, UserProfile
from twf.permissions import check_permission
from twf.tasks.instant_tasks import (
    save_instant_task_delete_all_documents,
    save_instant_task_delete_all_tags,
    save_instant_task_delete_all_collections,
    save_instant_task_unpark_all_tags,
    save_instant_task_remove_all_prompts,
    save_instant_task_remove_all_tasks,
    save_instant_task_remove_completed_tasks,
    save_instant_task_remove_active_tasks,
    save_instant_task_remove_all_dictionaries,
    save_instant_task_delete_note,
)
from twf.views.views_base import TWFView, get_referrer_or_default


def delete_all_documents(request):
    """Delete all documents.
    This will also delete all pages, page tags, and annotations."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "project.manage", project):
        messages.error(request, "You do not have permission to delete all documents.")
        return redirect("twf:project_reset")

    project.documents.all().delete()

    save_instant_task_delete_all_documents(project, request.user)

    messages.success(request, "All documents deleted.")
    return redirect("twf:project_reset")


def delete_all_tags(request):
    """Delete all tags.
    This will also delete all page tags."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "project.manage", project):
        messages.error(request, "You do not have permission to delete all tags.")
        return redirect("twf:tags_manage")

    PageTag.objects.filter(page__document__project=project).select_related(
        "page", "page__document"
    ).delete()

    save_instant_task_delete_all_tags(project, request.user)
    messages.success(request, "All tags deleted.")

    return redirect("twf:tags_manage")


def delete_all_collections(request):
    """Delete all collections.
    This will also delete all collection items and annotations."""

    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "project.manage", project):
        messages.error(request, "You do not have permission to delete all collections.")
        return redirect("twf:project_reset")

    project.collections.all().delete()

    save_instant_task_delete_all_collections(project, request.user)
    messages.success(request, "All collections deleted.")

    return redirect("twf:project_reset")


def select_project(request, pk):
    """Select a project."""
    request.session["project_id"] = pk
    return redirect("twf:project_overview")


def delete_project(request, pk):
    """
    Delete a project and all its associated media files.
    This includes downloaded exports, extracted files, and any other files related to the project.
    """

    try:
        project = Project.objects.get(pk=pk)
        if check_permission(request.user, "project.manage", project):
            # First, collect paths of all associated files that need to be deleted
            files_to_delete = []

            # 1. Project's downloaded export ZIP file
            if project.downloaded_zip_file:
                files_to_delete.append(project.downloaded_zip_file.path)

            # 2. Find all exports related to this project
            exports = Export.objects.filter(export_configuration__project=project)
            for export in exports:
                if export.export_file:
                    files_to_delete.append(export.export_file.path)

            # 3. Find all pages' XML files
            page_files = []
            for document in project.documents.all():
                for page in document.pages.all():
                    if page.xml_file:
                        page_files.append(page.xml_file.path)

            # Delete all related media files
            for file_path in files_to_delete + page_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except (OSError, PermissionError) as e:
                    # Log error but continue deleting
                    print(f"Error deleting file {file_path}: {e}")

            # Try to delete the project's directory in transkribus_exports
            collection_id = project.collection_id
            if collection_id:
                export_dir = os.path.join(
                    settings.MEDIA_ROOT, "transkribus_exports", collection_id
                )
                if os.path.exists(export_dir):
                    try:
                        shutil.rmtree(export_dir)
                    except (OSError, PermissionError) as e:
                        # Log error but continue with project deletion
                        print(f"Error deleting directory {export_dir}: {e}")

            # Now delete the project and all database relations
            with transaction.atomic():
                project.delete()

            messages.success(
                request, "Project and all associated files have been deleted."
            )
        else:
            messages.error(
                request,
                "You do not have the required permissions to delete this project.",
            )
    except Project.DoesNotExist:
        messages.error(request, "Project does not exist.")
    except Exception as e:
        messages.error(request, f"An error occurred during project deletion: {str(e)}")

    return get_referrer_or_default(request, default="twf:project_management")


def close_project(request, pk):
    """Close a project."""
    try:
        project = Project.objects.get(pk=pk)

        if check_permission(request.user, "project.manage", project):
            project.status = "closed"
            project.save(current_user=request.user)
            messages.success(request, "Project has been closed.")
        else:
            messages.error(
                request,
                "You do not have the required permissions to close this project.",
            )

    except Project.DoesNotExist:
        messages.error(request, "Project does not exist.")

    return get_referrer_or_default(request, default="twf:project_management")


def reopen_project(request, pk):
    """Reopen a closed project."""
    try:
        project = Project.objects.get(pk=pk)

        if check_permission(request.user, "project.manage", project):
            project.status = "open"
            project.save(current_user=request.user)
            messages.success(request, "Project has been reopened.")
        else:
            messages.error(
                request,
                "You do not have the required permissions to reopen this project.",
            )

    except Project.DoesNotExist:
        messages.error(request, "Project does not exist.")

    return get_referrer_or_default(request, default="twf:project_management")


def delete_prompt(request, pk):
    """Delete a prompt."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "prompt.manage", project):
        messages.error(request, "You do not have permission to delete a prompt.")
        return get_referrer_or_default(request, default="twf:project_prompts")

    try:
        prompt = project.prompts.get(pk=pk)
        prompt.delete()
        messages.success(request, "Prompt deleted.")
    except project.prompts.model.DoesNotExist:
        messages.error(request, "Prompt does not exist.")

    return get_referrer_or_default(request, default="twf:project_prompts")


def delete_note(request, pk):
    """Delete a note."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "note.manage", project):
        messages.error(request, "You do not have permission to delete a note.")
        return get_referrer_or_default(request, default="twf:project_notes")

    try:
        note = project.notes.get(pk=pk)

        # Capture info before deletion
        note_title = note.title
        note_id = note.id

        # Save instant task before deletion
        save_instant_task_delete_note(project, request.user, note_title, note_id)

        note.delete()
        messages.success(request, "Note deleted.")
    except project.notes.model.DoesNotExist:
        messages.error(request, "Note does not exist.")

    return get_referrer_or_default(request, default="twf:project_notes")


def task_cancel_view(request, task_id):
    """Cancel a task by its task_id."""
    try:
        task = Task.objects.get(pk=task_id)
        AsyncResult(task.celery_task_id).revoke(terminate=True)
        task.status = "CANCELED"
        task.end_time = timezone.now()
        task.save()

        # If this task has an associated workflow, cancel it and release reserved items
        if hasattr(task, "workflow") and task.workflow:
            task.workflow.cancel()

        messages.success(request, "Task cancelled successfully.")
        return get_referrer_or_default(request, default="twf:project_task_monitor")
    except Task.DoesNotExist:
        messages.error(request, "Task not found.")
        return get_referrer_or_default(request, default="twf:project_task_monitor")


def task_remove_view(request, task_id):
    """Remove a task from the database."""
    try:
        task = Task.objects.get(pk=task_id)

        # Prevent deletion of running tasks
        if task.status in ["STARTED", "PENDING", "PROGRESS"]:
            messages.error(
                request, "Cannot delete a running task. Please cancel it first."
            )
            return get_referrer_or_default(request, default="twf:project_task_monitor")

        task.delete()
        messages.success(request, "Task removed successfully.")
        # return to the task list page
        return get_referrer_or_default(request, default="twf:project_task_monitor")
    except Task.DoesNotExist:
        messages.error(request, "Task not found.")
        return get_referrer_or_default(request, default="twf:project_task_monitor")


def unpark_all_tags(request):
    """Unpark all tags."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "tag.edit", project):
        messages.error(request, "You do not have permission to unpark tags.")
        return redirect("twf:tags_manage")

    # Get all parked tags in the project and unpark them
    tags = PageTag.objects.filter(page__document__project=project, is_parked=True)
    count = tags.count()
    tags.update(is_parked=False)

    save_instant_task_unpark_all_tags(project, request.user)
    messages.success(request, f"{count} tags were unparked.")

    return redirect("twf:tags_manage")

    return redirect("twf:project_reset")


def remove_all_prompts(request):
    """Remove all prompts."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "prompt.manage", project):
        messages.error(request, "You do not have permission to remove prompts.")
        return redirect("twf:project_reset")

    # Count prompts before deletion
    count = project.prompts.count()

    # Remove all prompts from the project
    project.prompts.all().delete()

    save_instant_task_remove_all_prompts(project, request.user)
    messages.success(request, f"{count} prompts were removed.")

    return redirect("twf:project_reset")


def remove_all_tasks(request):
    """Remove all tasks."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "task.manage", project):
        messages.error(request, "You do not have permission to remove tasks.")
        return redirect("twf:project_reset")

    # Do not remove active tasks
    active_tasks = project.tasks.filter(status__in=["STARTED", "PENDING", "PROGRESS"])
    if active_tasks.exists():
        active_count = active_tasks.count()
        messages.warning(
            request,
            f"{active_count} active tasks could not be removed. Cancel them first.",
        )

    # Count and remove completed tasks
    completed_tasks = project.tasks.exclude(
        status__in=["STARTED", "PENDING", "PROGRESS"]
    )
    count = completed_tasks.count()
    completed_tasks.delete()

    save_instant_task_remove_all_tasks(project, request.user)
    messages.success(request, f"{count} completed tasks were removed.")

    return redirect("twf:project_reset")


def remove_completed_tasks(request):
    """Remove all completed (non-active) tasks from the project."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "task.manage", project):
        messages.error(request, "You do not have permission to remove tasks.")
        return redirect("twf:project_reset")

    completed = project.tasks.filter(status__in=["SUCCESS", "FAILURE", "CANCELED"])
    count = completed.count()
    completed.delete()

    save_instant_task_remove_completed_tasks(project, request.user, count)
    messages.success(request, f"{count} completed tasks were removed.")

    return redirect("twf:project_reset")


def remove_active_tasks(request):
    """Remove all active (running/pending) tasks from the project."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "task.manage", project):
        messages.error(request, "You do not have permission to remove tasks.")
        return redirect("twf:project_reset")

    active = project.tasks.filter(status__in=["STARTED", "PENDING", "PROGRESS"])
    count = active.count()
    active.delete()

    save_instant_task_remove_active_tasks(project, request.user, count)
    messages.success(request, f"{count} active tasks were removed.")

    return redirect("twf:project_reset")


def remove_all_dictionaries(request):
    """Remove all dictionaries from the project."""
    project = TWFView.s_get_project(request)

    if not check_permission(request.user, "dictionary.manage", project):
        messages.error(request, "You do not have permission to remove dictionaries.")
        return redirect("twf:project_reset")

    # Count dictionaries before removal
    count = project.selected_dictionaries.count()

    # Remove all dictionaries from the project (don't delete them)
    project.selected_dictionaries.clear()

    save_instant_task_remove_all_dictionaries(project, request.user)
    messages.success(request, f"{count} dictionaries were removed from the project.")

    return redirect("twf:project_reset")


def update_user_permissions(request, project_id, user_id):
    """Update a user's permissions."""
    if request.method != "POST":
        return redirect("twf:project_overview")

    # Get project
    project = get_object_or_404(Project, pk=project_id)

    # Check permission
    if not check_permission(request.user, "project.manage", project):
        messages.error(
            request, "You do not have permission to manage project permissions."
        )
        return redirect("twf:project_overview")

    # Process the form
    from twf.forms.project.project_forms import UserPermissionForm

    form = UserPermissionForm(request.POST)

    if form.is_valid():
        # Get the user_id from the form data
        form_user_id = form.cleaned_data.get("user_id")
        user_profile = get_object_or_404(UserProfile, pk=form_user_id)

        # Check if user is a special user (owner or superuser)
        is_special_user = (
            project.owner == user_profile
        ) or user_profile.user.is_superuser

        # Pass the user_profile and project to the form
        form = UserPermissionForm(
            request.POST, user_profile=user_profile, project=project
        )

        if form.is_valid():
            # Save the form data to the user profile
            form.save()

            # Show different message based on user type
            if is_special_user:
                messages.success(
                    request,
                    f"Function description updated for {user_profile.user.username}.",
                )
            else:
                messages.success(
                    request, f"Permissions updated for {user_profile.user.username}."
                )
        else:
            # If there are errors in the form, show them to the user
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error in {field}: {error}")
    else:
        # If there are errors in the form, show them to the user
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Error in {field}: {error}")

    return get_referrer_or_default(request, default="twf:user_management")

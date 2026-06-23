import uuid
from django.utils import timezone
from twf.models import Task


def generated_task_id():
    """Generate a task ID."""
    security_break = 0

    while True:
        random_id = str(uuid.uuid4())  # Generate a UUID
        if not Task.objects.filter(celery_task_id=random_id).exists():
            return random_id
        security_break += 1
        if security_break > 100:
            return None


def save_instant_task(project, user, title, description, text, category=None, **metadata):
    """Save an instant task to the database.

    Args:
        project: The project this task belongs to
        user: The user who performed the operation
        title: Short title for the task
        description: Longer description of what was done
        text: Detailed log text
        category: Task category (create, update, delete, etc.)
        **metadata: Additional metadata to store in the task's meta field

    Returns:
        Task: The created task object
    """
    task = Task(
        project=project,
        user=user,
        status="SUCCESS",
        task_type="instant",
        category=category,
        title=title,
        text=text,
        description=description,
        end_time=timezone.now(),
        celery_task_id=generated_task_id(),
        progress=100,
        meta=metadata or {},
    )
    task.save()
    return task


def save_instant_task_add_dictionary(project, user, text):
    """Save an instant task to the database."""
    title = "Add Dictionary"
    description = "Add a new dictionary to the project."
    save_instant_task(project, user, title, description, text, category="create")


def save_instant_task_create_project(project, user):
    """Save an instant task to the database."""
    title = "Create Project"
    description = "Create a project"
    save_instant_task(project, user, title, description, "The project was created.", category="create")


def save_instant_task_request_transkribus_export(project, user, text):
    """Save an instant task to the database."""
    title = "Request Transkribus Export"
    description = "Request an export of the project data from Transkribus."
    save_instant_task(project, user, title, description, text, category="export")


def save_instant_task_transkribus_export_download(project, user, text):
    """Save an instant task to the database."""
    title = "Download Transkribus Export"
    description = "Download the exported data from Transkribus."
    save_instant_task(project, user, title, description, text, category="import")


def save_instant_task_delete_all_documents(project, user):
    """Save an instant task to the database."""
    title = "Delete All Documents"
    description = "Delete all documents in the project."
    save_instant_task(project, user, title, description, "All documents were deleted.", category="bulk_delete")


def save_instant_task_delete_all_tags(project, user):
    """Save an instant task to the database."""
    title = "Delete All Tags"
    description = "Delete all tags in the project."
    save_instant_task(project, user, title, description, "All tags were deleted.", category="bulk_delete")


def save_instant_task_delete_all_collections(project, user):
    """Save an instant task to the database."""
    title = "Delete All Collections"
    description = "Delete all collections in the project."
    save_instant_task(
        project, user, title, description, "All collections were deleted.", category="bulk_delete"
    )


def save_instant_task_unpark_all_tags(project, user):
    """Save an instant task to the database."""
    title = "Unpark All Tags"
    description = "Unpark all tags in the project."
    save_instant_task(project, user, title, description, "All tags were unparked.", category="update")


def save_instant_task_remove_all_prompts(project, user):
    """Save an instant task to the database."""
    title = "Remove All Prompts"
    description = "Remove all prompts in the project."
    save_instant_task(project, user, title, description, "All prompts were removed.", category="bulk_delete")


def save_instant_task_remove_all_tasks(project, user):
    """Save an instant task to the database."""
    title = "Remove All Tasks"
    description = "Remove all tasks in the project."
    save_instant_task(project, user, title, description, "All tasks were removed.", category="bulk_delete")


def save_instant_task_remove_completed_tasks(project, user, count):
    """Save an instant task recording deletion of completed tasks."""
    title = "Remove Completed Tasks"
    description = "Remove all completed tasks in the project."
    save_instant_task(
        project, user, title, description,
        f"{count} completed tasks were removed.",
        category="bulk_delete"
    )


def save_instant_task_remove_active_tasks(project, user, count):
    """Save an instant task recording deletion of active tasks."""
    title = "Remove Active Tasks"
    description = "Remove all active tasks in the project."
    save_instant_task(
        project, user, title, description,
        f"{count} active tasks were removed.",
        category="bulk_delete"
    )


def save_instant_task_remove_all_dictionaries(project, user):
    """Save an instant task to the database."""
    title = "Remove All Dictionaries"
    description = "Remove all dictionaries from the project."
    save_instant_task(
        project,
        user,
        title,
        description,
        "All dictionaries were removed from the project.",
        category="bulk_delete"
    )


def save_instant_task_merge_entries(project, user, remaining_entry_label, merge_entry_label):
    """Save an instant task for merging dictionary entries."""
    title = "Merge Dictionary Entries"
    description = "Merge two dictionary entries into one."
    text = f"Merged entry '{merge_entry_label}' into '{remaining_entry_label}'."
    save_instant_task(project, user, title, description, text, category="update")


def start_related_task(project, user, title, description, text):
    """Start a task for tracking a workflow.

    Args:
        project: The project this task belongs to
        user: The user who started the workflow
        title: Short title for the task
        description: Longer description of the workflow
        text: Initial log text

    Returns:
        Task: The created task object (status=STARTED, task_type=workflow)
    """
    task = Task(
        project=project,
        user=user,
        status="STARTED",
        task_type="workflow",
        category="workflow",
        title=title,
        text=text,
        description=description,
        celery_task_id=generated_task_id(),
    )
    task.save()
    return task


# ========================================
# Individual Item CRUD Operations
# ========================================

# Document operations
def save_instant_task_delete_document(project, user, document_title, document_id):
    """Record deletion of a single document."""
    title = f"Delete Document: {document_title}"
    description = "Deleted a document from the project."
    text = f"Document '{document_title}' (ID: {document_id}) was deleted."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="Document",
        object_id=document_id,
        object_label=document_title
    )


def save_instant_task_update_document(project, user, document_title, document_id, changes):
    """Record update of a document."""
    title = f"Update Document: {document_title}"
    description = "Updated document properties."
    text = f"Document '{document_title}' was updated. Changes: {changes}"
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="Document",
        object_id=document_id,
        changes=changes
    )


# Collection operations
def save_instant_task_create_collection(project, user, collection_title, collection_id):
    """Record creation of a collection."""
    title = f"Create Collection: {collection_title}"
    description = "Created a new collection."
    text = f"Collection '{collection_title}' (ID: {collection_id}) was created."
    return save_instant_task(
        project, user, title, description, text,
        category="create",
        object_type="Collection",
        object_id=collection_id,
        object_label=collection_title
    )


def save_instant_task_delete_collection(project, user, collection_title, collection_id):
    """Record deletion of a collection."""
    title = f"Delete Collection: {collection_title}"
    description = "Deleted a collection from the project."
    text = f"Collection '{collection_title}' (ID: {collection_id}) was deleted."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="Collection",
        object_id=collection_id,
        object_label=collection_title
    )


def save_instant_task_update_collection(project, user, collection_title, collection_id, changes):
    """Record update of a collection."""
    title = f"Update Collection: {collection_title}"
    description = "Updated collection properties."
    text = f"Collection '{collection_title}' was updated. Changes: {changes}"
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="Collection",
        object_id=collection_id,
        changes=changes
    )


# Collection Item operations
def save_instant_task_delete_collection_item(project, user, item_title, item_id, collection_title):
    """Record deletion of a collection item."""
    title = f"Delete Item: {item_title}"
    description = f"Deleted an item from collection '{collection_title}'."
    text = f"Collection item '{item_title}' (ID: {item_id}) was deleted from '{collection_title}'."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="CollectionItem",
        object_id=item_id,
        object_label=item_title
    )


def save_instant_task_update_collection_item(project, user, item_title, item_id, changes):
    """Record update of a collection item."""
    title = f"Update Item: {item_title}"
    description = "Updated collection item properties."
    text = f"Collection item '{item_title}' was updated. Changes: {changes}"
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="CollectionItem",
        object_id=item_id,
        changes=changes
    )


# Dictionary operations
def save_instant_task_create_dictionary(project, user, dictionary_label, dictionary_id):
    """Record creation of a dictionary."""
    title = f"Create Dictionary: {dictionary_label}"
    description = "Created a new dictionary."
    text = f"Dictionary '{dictionary_label}' (ID: {dictionary_id}) was created."
    return save_instant_task(
        project, user, title, description, text,
        category="create",
        object_type="Dictionary",
        object_id=dictionary_id,
        object_label=dictionary_label
    )


def save_instant_task_delete_dictionary(project, user, dictionary_label, dictionary_id):
    """Record deletion of a dictionary."""
    title = f"Delete Dictionary: {dictionary_label}"
    description = "Deleted a dictionary from the project."
    text = f"Dictionary '{dictionary_label}' (ID: {dictionary_id}) was deleted."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="Dictionary",
        object_id=dictionary_id,
        object_label=dictionary_label
    )


def save_instant_task_remove_dictionary_from_project(project, user, dictionary_label, dictionary_id):
    """Record removal of a dictionary from project."""
    title = f"Remove Dictionary: {dictionary_label}"
    description = "Removed a dictionary from the project."
    text = f"Dictionary '{dictionary_label}' (ID: {dictionary_id}) was removed from the project."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="Dictionary",
        object_id=dictionary_id,
        object_label=dictionary_label
    )


# Dictionary Entry operations
def save_instant_task_create_dictionary_entry(project, user, entry_label, entry_id, dictionary_label):
    """Record creation of a dictionary entry."""
    title = f"Create Entry: {entry_label}"
    description = f"Created a new entry in dictionary '{dictionary_label}'."
    text = f"Dictionary entry '{entry_label}' (ID: {entry_id}) was created in '{dictionary_label}'."
    return save_instant_task(
        project, user, title, description, text,
        category="create",
        object_type="DictionaryEntry",
        object_id=entry_id,
        object_label=entry_label
    )


def save_instant_task_delete_dictionary_entry(project, user, entry_label, entry_id, dictionary_label):
    """Record deletion of a dictionary entry."""
    title = f"Delete Entry: {entry_label}"
    description = f"Deleted an entry from dictionary '{dictionary_label}'."
    text = f"Dictionary entry '{entry_label}' (ID: {entry_id}) was deleted from '{dictionary_label}'."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="DictionaryEntry",
        object_id=entry_id,
        object_label=entry_label
    )


def save_instant_task_update_dictionary_entry(project, user, entry_label, entry_id, changes):
    """Record update of a dictionary entry."""
    title = f"Update Entry: {entry_label}"
    description = "Updated dictionary entry properties."
    text = f"Dictionary entry '{entry_label}' was updated. Changes: {changes}"
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="DictionaryEntry",
        object_id=entry_id,
        changes=changes
    )


# Variation operations
def save_instant_task_delete_variation(project, user, variation_text, variation_id, entry_label):
    """Record deletion of a variation."""
    title = f"Delete Variation: {variation_text}"
    description = f"Deleted a variation from dictionary entry '{entry_label}'."
    text = f"Variation '{variation_text}' (ID: {variation_id}) was deleted from entry '{entry_label}'."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="Variation",
        object_id=variation_id,
        object_label=variation_text
    )


# Tag operations
def save_instant_task_delete_tag(project, user, tag_variation, tag_id):
    """Record deletion of a tag."""
    title = f"Delete Tag: {tag_variation}"
    description = "Deleted a tag from the project."
    text = f"Tag '{tag_variation}' (ID: {tag_id}) was deleted."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="PageTag",
        object_id=tag_id,
        object_label=tag_variation
    )


def save_instant_task_update_tag(project, user, tag_variation, tag_id, changes):
    """Record update of a tag."""
    title = f"Update Tag: {tag_variation}"
    description = "Updated tag properties."
    text = f"Tag '{tag_variation}' was updated. Changes: {changes}"
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="PageTag",
        object_id=tag_id,
        changes=changes
    )


def save_instant_task_park_tag(project, user, tag_variation, tag_id):
    """Record parking of a tag."""
    title = f"Park Tag: {tag_variation}"
    description = "Parked a tag."
    text = f"Tag '{tag_variation}' (ID: {tag_id}) was parked."
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="PageTag",
        object_id=tag_id,
        action="park"
    )


def save_instant_task_unpark_tag(project, user, tag_variation, tag_id):
    """Record unparking of a tag."""
    title = f"Unpark Tag: {tag_variation}"
    description = "Unparked a tag."
    text = f"Tag '{tag_variation}' (ID: {tag_id}) was unparked."
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="PageTag",
        object_id=tag_id,
        action="unpark"
    )


# Dictionary entry operations
def save_instant_task_park_dictionary_entry(project, user, entry_label, entry_id):
    """Record parking of a dictionary entry."""
    title = f"Park Dictionary Entry: {entry_label}"
    description = "Parked a dictionary entry."
    text = f"Dictionary entry '{entry_label}' (ID: {entry_id}) was parked."
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="DictionaryEntry",
        object_id=entry_id,
        action="park"
    )


def save_instant_task_unpark_dictionary_entry(project, user, entry_label, entry_id):
    """Record unparking of a dictionary entry."""
    title = f"Unpark Dictionary Entry: {entry_label}"
    description = "Unparked a dictionary entry."
    text = f"Dictionary entry '{entry_label}' (ID: {entry_id}) was unparked."
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="DictionaryEntry",
        object_id=entry_id,
        action="unpark"
    )


# AI Configuration operations
def save_instant_task_create_ai_config(project, user, config_name, config_id):
    """Record creation of an AI configuration."""
    title = f"Create AI Config: {config_name}"
    description = "Created a new AI configuration."
    text = f"AI configuration '{config_name}' (ID: {config_id}) was created."
    return save_instant_task(
        project, user, title, description, text,
        category="create",
        object_type="AIConfiguration",
        object_id=config_id,
        object_label=config_name
    )


def save_instant_task_delete_ai_config(project, user, config_name, config_id):
    """Record deletion of an AI configuration."""
    title = f"Delete AI Config: {config_name}"
    description = "Deleted an AI configuration."
    text = f"AI configuration '{config_name}' (ID: {config_id}) was deleted."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="AIConfiguration",
        object_id=config_id,
        object_label=config_name
    )


def save_instant_task_update_ai_config(project, user, config_name, config_id, changes):
    """Record update of an AI configuration."""
    title = f"Update AI Config: {config_name}"
    description = "Updated AI configuration properties."
    text = f"AI configuration '{config_name}' was updated. Changes: {changes}"
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="AIConfiguration",
        object_id=config_id,
        changes=changes
    )


# Export Configuration operations
def save_instant_task_create_export_config(project, user, config_name, config_id):
    """Record creation of an export configuration."""
    title = f"Create Export Config: {config_name}"
    description = "Created a new export configuration."
    text = f"Export configuration '{config_name}' (ID: {config_id}) was created."
    return save_instant_task(
        project, user, title, description, text,
        category="create",
        object_type="ExportConfiguration",
        object_id=config_id,
        object_label=config_name
    )


def save_instant_task_delete_export_config(project, user, config_name, config_id):
    """Record deletion of an export configuration."""
    title = f"Delete Export Config: {config_name}"
    description = "Deleted an export configuration."
    text = f"Export configuration '{config_name}' (ID: {config_id}) was deleted."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="ExportConfiguration",
        object_id=config_id,
        object_label=config_name
    )


# Note operations
def save_instant_task_create_note(project, user, note_title, note_id):
    """Record creation of a note."""
    title = f"Create Note: {note_title}"
    description = "Created a new project note."
    text = f"Note '{note_title}' (ID: {note_id}) was created."
    return save_instant_task(
        project, user, title, description, text,
        category="create",
        object_type="Note",
        object_id=note_id,
        object_label=note_title
    )


def save_instant_task_update_note(project, user, note_title, note_id):
    """Record update of a note."""
    title = f"Update Note: {note_title}"
    description = "Updated a project note."
    text = f"Note '{note_title}' (ID: {note_id}) was updated."
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="Note",
        object_id=note_id,
        object_label=note_title
    )


def save_instant_task_delete_note(project, user, note_title, note_id):
    """Record deletion of a note."""
    title = f"Delete Note: {note_title}"
    description = "Deleted a project note."
    text = f"Note '{note_title}' (ID: {note_id}) was deleted."
    return save_instant_task(
        project, user, title, description, text,
        category="delete",
        object_type="Note",
        object_id=note_id,
        object_label=note_title
    )


# Project Settings operations
def save_instant_task_update_project_settings(project, user, settings_type, changes_summary):
    """Record update of project settings.

    Args:
        project: The project being updated
        user: The user making the update
        settings_type: Type of settings (e.g., "General", "Display", "Date Normalization", "Workflow")
        changes_summary: Brief description of what was changed
    """
    title = f"Update Settings: {settings_type}"
    description = f"Updated {settings_type} settings for the project."
    text = f"{settings_type} settings were updated. {changes_summary}"
    return save_instant_task(
        project, user, title, description, text,
        category="update",
        object_type="ProjectSettings",
        settings_type=settings_type,
        changes_summary=changes_summary
    )

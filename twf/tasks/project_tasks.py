""" Celery tasks for duplicating a project and its related objects. """

import logging
import traceback

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from twf.models import Project, Note, Workflow, AIConfiguration
from twf.tasks.task_base import BaseTWFTask

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, base=BaseTWFTask, serializer="pickle")
def copy_project(self, project_id, user_id, **kwargs):
    """
    Create a copy of a project with all its essential components.

    This task creates a new project by copying the source project's structure and data:
    - Project basic data (title, description, configurations)
    - Selected dictionaries (references to same dictionaries)
    - Project members and their permissions
    - Collections and collection items
    - Documents, pages, and tags
    - Prompts with their context references
    - Workflows (in ended state)

    Some elements are not copied by design:
    - Tasks (to avoid duplicate task IDs and unnecessary history)
    - Active workflow states (all copied workflows are set to 'ended')
    - Reservation statuses (all items have is_reserved=False)

    Returns:
        Project: The newly created project object
    """
    self.validate_task_parameters(kwargs, ["new_project_name"])
    new_title = kwargs.get("new_project_name")

    try:
        with transaction.atomic():
            self.update_progress(5)
            # Generate a new title if not provided
            new_title = new_title or f"Copy of {self.project.title}"
            self.twf_task.text += f"Creating new project: {new_title}\n"

            # Create the new project with only essential attributes
            new_project = Project(
                title=new_title,
                status="open",
                created_by=self.user,
                modified_by=self.user,
                owner=self.project.owner,
                # Copy essential fields
                collection_id=self.project.collection_id,
                description=self.project.description,
                conf_credentials=self.project.conf_credentials,
                conf_tasks=self.project.conf_tasks,
                conf_ai_settings=self.project.conf_ai_settings,
                conf_display=self.project.conf_display,
                keywords=self.project.keywords,
                license=self.project.license,
                version=self.project.version,
                workflow_description=self.project.workflow_description,
                project_doi=self.project.project_doi,
            )
            new_project.save()

            # Copy AIConfiguration objects
            ai_config_count = 0
            for ai_config in self.project.ai_configs.all():
                AIConfiguration.objects.create(
                    project=new_project,
                    name=ai_config.name,
                    description=ai_config.description,
                    provider=ai_config.provider,
                    model=ai_config.model,
                    api_key=ai_config.api_key,
                    system_role=ai_config.system_role,
                    prompt_template=ai_config.prompt_template,
                    temperature=ai_config.temperature,
                    max_tokens=ai_config.max_tokens,
                    top_p=ai_config.top_p,
                    frequency_penalty=ai_config.frequency_penalty,
                    presence_penalty=ai_config.presence_penalty,
                    seed=ai_config.seed,
                    is_active=ai_config.is_active,
                    created_by=self.user,
                    modified_by=self.user,
                )
                ai_config_count += 1
            self.twf_task.text += f"Copied {ai_config_count} AI configurations\n"

            # Copy existing Notes (excluding the copy-info note which is added at the end)
            note_count = 0
            for note in self.project.notes.all():
                Note.objects.create(
                    project=new_project,
                    title=note.title,
                    note=note.note,
                    created_by=self.user,
                    modified_by=self.user,
                )
                note_count += 1
            if note_count:
                self.twf_task.text += f"Copied {note_count} notes\n"
            self.twf_task.text += f"Created new project with ID: {new_project.id}\n"

            # Copy selected dictionaries (referencing the same ones)
            self.update_progress(10)
            self.twf_task.text += "Copying dictionary references...\n"
            if self.project.selected_dictionaries.exists():
                new_project.selected_dictionaries.set(
                    self.project.selected_dictionaries.all()
                )

            # Copy members and their permissions
            self.update_progress(15)
            self.twf_task.text += "Copying project members...\n"
            if self.project.members.exists():
                new_project.members.set(self.project.members.all())

            # Copy user permissions
            self.update_progress(20)
            self.twf_task.text += "Copying user permissions...\n"
            # Get a fresh queryset of users to ensure we have the latest data
            # Get all users who are members of the new project
            user_ids = new_project.members.values_list("user_id", flat=True)
            users = User.objects.filter(id__in=user_ids)

            for user in users:
                if hasattr(user, "profile"):
                    profile = user.profile
                    if str(self.project.id) in profile.permissions:
                        profile.permissions[str(new_project.id)] = profile.permissions[
                            str(self.project.id)
                        ]
                        profile.save()

            # Create mappings to track relationships between original and copied objects
            collection_mapping = {}  # old_id -> new_collection
            collection_item_mapping = {}  # old_id -> new_collection_item
            document_mapping = {}  # old_id -> new_document
            page_mapping = {}  # old_id -> new_page

            # Copy collections and their items
            self.update_progress(30)
            self.twf_task.text += "Copying collections...\n"
            collection_count = 0
            collection_item_count = 0

            for collection in self.project.collections.all():
                new_collection = collection.__class__(
                    project=new_project,
                    title=collection.title,
                    description=collection.description,
                    created_by=self.user,
                    modified_by=self.user,
                )
                new_collection.save()
                collection_mapping[collection.id] = new_collection
                collection_count += 1

                for item in collection.items.all():
                    new_item = item.__class__(
                        collection=new_collection,
                        title=item.title,
                        status=item.status,
                        document=item.document,  # Same document reference
                        document_configuration=item.document_configuration,
                        metadata=item.metadata,
                        review_notes=item.review_notes,
                        is_reserved=False,  # Reset reservation status
                        created_by=self.user,
                        modified_by=self.user,
                    )
                    new_item.save()
                    collection_item_mapping[item.id] = new_item
                    collection_item_count += 1

            self.twf_task.text += f"Copied {collection_count} collections with {collection_item_count} items\n"

            # Copy documents and their pages/tags
            self.update_progress(50)
            self.twf_task.text += "Copying documents and pages...\n"
            document_count = 0
            page_count = 0
            tag_count = 0

            for document in self.project.documents.all():
                new_document = document.__class__(
                    project=new_project,
                    title=document.title,
                    document_id=document.document_id,
                    metadata=document.metadata,
                    last_parsed_at=document.last_parsed_at,
                    is_parked=document.is_parked,
                    workflow_remarks=document.workflow_remarks,
                    is_reserved=False,  # Reset reservation
                    status=document.status,
                    created_by=self.user,
                    modified_by=self.user,
                )
                new_document.save()
                document_mapping[document.id] = new_document
                document_count += 1

                for page in document.pages.all():
                    new_page = page.__class__(
                        document=new_document,
                        metadata=page.metadata,
                        xml_file=page.xml_file,
                        tk_page_id=page.tk_page_id,
                        tk_page_number=page.tk_page_number,
                        parsed_data=page.parsed_data,
                        num_tags=page.num_tags,
                        is_ignored=page.is_ignored,
                        created_by=self.user,
                        modified_by=self.user,
                    )
                    new_page.save()
                    page_mapping[page.id] = new_page
                    page_count += 1

                    for page_tag in page.tags.all():
                        new_page_tag = page_tag.__class__(
                            page=new_page,
                            variation=page_tag.variation,
                            variation_type=page_tag.variation_type,
                            dictionary_entry=page_tag.dictionary_entry,
                            additional_information=page_tag.additional_information,
                            date_variation_entry=page_tag.date_variation_entry,
                            is_parked=page_tag.is_parked,
                            created_by=self.user,
                            modified_by=self.user,
                        )
                        new_page_tag.save()
                        tag_count += 1

            self.twf_task.text += f"Copied {document_count} documents with {page_count} pages and {tag_count} tags\n"

            # Copy prompts
            self.update_progress(80)
            self.twf_task.text += "Copying prompts...\n"
            prompt_count = 0

            for prompt in self.project.prompts.all():
                new_prompt = prompt.__class__(
                    project=new_project,
                    system_role=prompt.system_role,
                    prompt=prompt.prompt,
                    created_by=self.user,
                    modified_by=self.user,
                )
                new_prompt.save()
                prompt_count += 1

                # Handle many-to-many relationships with proper mappings
                # Document context
                if prompt.document_context.exists():
                    docs_to_add = []
                    for doc in prompt.document_context.all():
                        if doc.id in document_mapping:
                            docs_to_add.append(document_mapping[doc.id])
                    if docs_to_add:
                        new_prompt.document_context.set(docs_to_add)

                # Page context
                if prompt.page_context.exists():
                    pages_to_add = []
                    for page in prompt.page_context.all():
                        if page.id in page_mapping:
                            pages_to_add.append(page_mapping[page.id])
                    if pages_to_add:
                        new_prompt.page_context.set(pages_to_add)

                # Collection item context
                if prompt.collection_context.exists():
                    items_to_add = []
                    for item in prompt.collection_context.all():
                        if item.id in collection_item_mapping:
                            items_to_add.append(collection_item_mapping[item.id])
                    if items_to_add:
                        new_prompt.collection_context.set(items_to_add)

            self.twf_task.text += f"Copied {prompt_count} prompts\n"

            # Copy workflows
            self.update_progress(90)
            self.twf_task.text += "Copying workflows...\n"
            workflow_count = 0

            # Use the Workflow class to properly access its fields

            for workflow in self.project.workflow_set.all():
                # Create a new workflow with basic attributes
                new_workflow = Workflow(
                    project=new_project,
                    user=workflow.user,
                    workflow_type=workflow.workflow_type,
                    status="ended",  # Set as ended to avoid issues
                    item_count=workflow.item_count,
                    current_item_index=0,  # Reset index
                    created_at=workflow.created_at,
                    updated_at=workflow.updated_at,
                )

                # Set foreign key relationships if they exist and were copied
                if workflow.dictionary:
                    new_workflow.dictionary = (
                        workflow.dictionary
                    )  # Reference the same dictionary

                if workflow.collection and workflow.collection.id in collection_mapping:
                    new_workflow.collection = collection_mapping[workflow.collection.id]

                # Do not copy the related_task to avoid task duplication issues
                new_workflow.related_task = None

                new_workflow.save()
                workflow_count += 1

                # Handle many-to-many relationships with proper error handling
                # Document items
                if (
                    hasattr(workflow, "assigned_document_items")
                    and workflow.assigned_document_items.exists()
                ):
                    try:
                        docs_to_assign = []
                        for doc in workflow.assigned_document_items.all():
                            if doc.id in document_mapping:
                                docs_to_assign.append(document_mapping[doc.id])
                        if docs_to_assign:
                            new_workflow.assigned_document_items.set(docs_to_assign)
                    except Exception as e:
                        self.twf_task.text += (
                            f"Warning: Could not copy document items relation: {e}\n"
                        )

                # Dictionary entries
                if (
                    hasattr(workflow, "assigned_dictionary_entries")
                    and workflow.assigned_dictionary_entries.exists()
                ):
                    try:
                        # Dictionary entries are referenced, not copied
                        new_workflow.assigned_dictionary_entries.set(
                            workflow.assigned_dictionary_entries.all()
                        )
                    except Exception as e:
                        self.twf_task.text += f"Warning: Could not copy dictionary entries relation: {e}\n"

                # Collection items
                if (
                    hasattr(workflow, "assigned_collection_items")
                    and workflow.assigned_collection_items.exists()
                ):
                    try:
                        items_to_assign = []
                        for item in workflow.assigned_collection_items.all():
                            if item.id in collection_item_mapping:
                                items_to_assign.append(collection_item_mapping[item.id])
                        if items_to_assign:
                            new_workflow.assigned_collection_items.set(items_to_assign)
                    except Exception as e:
                        self.twf_task.text += (
                            f"Warning: Could not copy collection items relation: {e}\n"
                        )

            self.twf_task.text += f"Copied {workflow_count} workflows\n"

            # Create a note about the copy
            Note.objects.create(
                project=new_project,
                title="Project Copy Information",
                note=f"This project was copied from '{self.project.title}' on "
                     f"{timezone.now().strftime('%Y-%m-%d at %H:%M')}.\n\n"
                f"Copy includes:\n"
                f"- {document_count} documents\n"
                f"- {page_count} pages\n"
                f"- {tag_count} tags\n"
                f"- {collection_count} collections\n"
                f"- {collection_item_count} collection items\n"
                f"- {prompt_count} prompts\n"
                f"- {workflow_count} workflows\n\n"
                f"Copied by: {self.user.username}",
                created_by=self.user,
                modified_by=self.user,
            )

        # Record completion in the database task
        if self.twf_task:
            self.twf_task.text += "Project copy completed successfully!\n"
            self.twf_task.status = "SUCCESS"
            self.twf_task.end_time = timezone.now()
            duration = (self.twf_task.end_time - self.start_datetime).total_seconds()

            # Create summary
            summary = "\n---- TASK SUMMARY ----\n"
            summary += "Status: SUCCESS\n"
            summary += f"Duration: {duration:.2f} seconds"

            if duration > 60:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                summary += f" ({minutes}m {seconds}s)"
            summary += "\n"

            summary += f"Project copied: {self.project.title} → {new_project.title}\n"
            summary += f"Collections: {collection_count}\n"
            summary += f"Collection items: {collection_item_count}\n"
            summary += f"Documents: {document_count}\n"
            summary += f"Pages: {page_count}\n"
            summary += f"Tags: {tag_count}\n"
            summary += f"Prompts: {prompt_count}\n"
            summary += f"Workflows: {workflow_count}\n"
            summary += "----------------------\n"

            self.twf_task.text += summary

            # Set meta information in the database task
            self.twf_task.meta = {
                "status": "SUCCESS",
                "duration": duration,
                "collections": collection_count,
                "collection_items": collection_item_count,
                "documents": document_count,
                "pages": page_count,
                "tags": tag_count,
                "prompts": prompt_count,
                "workflows": workflow_count,
                "new_project_id": new_project.id,
                "celery_task_id": self.task_id,  # Store the Celery task ID for status lookup
            }

            self.twf_task.save()

        # Return the result in the format expected by task_status_view and celery_task_monitor.js
        result = {
            "new_project_id": new_project.id,
            "collections": collection_count,
            "collection_items": collection_item_count,
            "documents": document_count,
            "pages": page_count,
            "tags": tag_count,
            "prompts": prompt_count,
            "workflows": workflow_count,
            "task_id": self.task_id,
            "db_task_id": self.twf_task.id if self.twf_task else None,
        }

        return result

    except Exception as e:
        # Log the error with detailed information
        error_msg = f"{type(e).__name__}: {str(e)}"
        stack_trace = traceback.format_exc()

        # Record failure in the database task
        if self.twf_task:
            self.twf_task.text += f"Error during project copy: {error_msg}\n"
            self.twf_task.text += f"Stack trace:\n{stack_trace}\n"
            self.twf_task.status = "FAILURE"
            self.twf_task.end_time = timezone.now()
            self.twf_task.title = (
                f"Failed: {error_msg[:50]}..."
                if len(error_msg) > 50
                else f"Failed: {error_msg}"
            )

            # Add summary to task text
            duration = (self.twf_task.end_time - self.start_datetime).total_seconds()
            summary = "\n---- TASK SUMMARY ----\n"
            summary += "Status: FAILURE\n"
            summary += f"Duration: {duration:.2f} seconds\n"
            summary += f"Error: {error_msg}\n"
            summary += "----------------------\n"
            self.twf_task.text += summary

            self.twf_task.save()

        # Re-raise the exception to let Celery handle it
        raise


def query_project_unified(self, project_id, user_id, **kwargs):
    """
    Unified task for AI query processing with project documents.

    Uses AIConfiguration which contains all AI settings (provider, model, prompt, etc.).

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Must include:
            - ai_configuration_id: ID of the AIConfiguration to use
            - documents: List of document IDs
            - prompt_mode (optional): One of "text_only", "images_only", or "text_and_images"
    """
    from twf.models import AIConfiguration

    self.validate_task_parameters(kwargs, ["ai_configuration_id", "documents"])

    # Load the AI configuration
    ai_config_id = kwargs.get("ai_configuration_id")
    try:
        ai_config = AIConfiguration.objects.get(id=ai_config_id, project=self.project)
    except AIConfiguration.DoesNotExist:
        raise ValueError(f"AIConfiguration with id {ai_config_id} not found for this project")

    doc_ids = kwargs.pop("documents")
    documents = self.project.documents.filter(pk__in=doc_ids)

    # Get the prompt mode (defaults to text_only if not provided)
    prompt_mode = kwargs.pop("prompt_mode", "text_only")

    # Note about image support for non-supporting providers
    if prompt_mode in ["images_only", "text_and_images"]:
        if ai_config.provider in ["mistral"]:  # Update as needed based on provider capabilities
            self.twf_task.text += f"Note: {ai_config.provider} does not currently support image inputs. Using text-only mode.\n"
            prompt_mode = "text_only"

    # Process query using the AI configuration settings
    return self.process_single_ai_request(
        documents,
        ai_config.provider,
        ai_config.prompt_template,
        ai_config.system_role,
        ai_config.provider,
        prompt_mode=prompt_mode,
        model=ai_config.model,
        api_key=ai_config.api_key,
    )

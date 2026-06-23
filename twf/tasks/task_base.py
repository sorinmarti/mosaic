"""
Task base functions and classes for the TWF application.

This module provides the foundational infrastructure for task management in the TWF application,
including task lifecycle management (start, update, progress tracking, and completion),
error handling, and specialized support for AI processing tasks including multimodal 
(text + images) capabilities.

The primary class, BaseTWFTask, extends Celery's Task class with TWF-specific tracking,
reporting, and AI interaction capabilities.
"""

import time
import logging

from django.utils import timezone
from celery import Task as CeleryTask

from twf.clients.ai_client_adapter import create_ai_client
from twf.models import Task, Project, User, Document, Page, CollectionItem

logger = logging.getLogger(__name__)


class BaseTWFTask(CeleryTask):
    """
    Base task class for all TWF Celery tasks.

    This class extends Celery's Task class with TWF-specific functionality for managing
    the task lifecycle, tracking progress, handling errors, and interacting with AI providers.
    It provides specialized methods for AI processing, including multimodal content
    (text + images) where supported by the provider.

    Key features:
    - Task progress tracking and reporting through the database
    - Standardized task creation and completion handling
    - AI provider integration with consistent interface
    - Support for text-only and multimodal (text + images) AI requests
    - Automatic image selection and scaling for multimodal prompts

    Each task instance creates and updates a Task object in the database to track its
    status, progress, and results. This enables real-time monitoring of long-running
    background tasks through the web interface.
    """

    # Standard descriptions for common task types
    TASK_DESCRIPTIONS = {
        # Document and structure tasks
        "extract_zip_export_task": "Unified synchronization of documents, pages, and tags from "
                                   "Transkribus export. Intelligently preserves user assignments "
                                   "and parked status.",
        "create_collection": "Creation of a new collection in the project.",
        # AI collection processing tasks
        "search_openai_for_collection": "OpenAI processing of collection items "
                                        "for content extraction or enhancement.",
        "search_gemini_for_collection": "Gemini AI processing of collection items "
                                        "for content extraction or enhancement.",
        "search_claude_for_collection": "Claude AI processing of collection items "
                                        "for content extraction or enhancement.",
        "search_mistral_for_collection": "Mistral AI processing of collection items "
                                         "for content extraction or enhancement.",
        # AI document processing tasks
        "search_openai_for_docs": "OpenAI processing of documents "
                                  "for content extraction or enhancement.",
        "search_gemini_for_docs": "Gemini AI processing of documents "
                                  "for content extraction or enhancement.",
        "search_claude_for_docs": "Claude AI processing of documents "
                                  "for content extraction or enhancement.",
        "search_mistral_for_docs": "Mistral AI processing of documents "
                                   "for content extraction or enhancement.",
        "search_deepseek_for_docs": "DeepSeek AI processing of documents "
                                    "for content extraction or enhancement.",
        "search_qwen_for_docs": "Qwen AI processing of documents for content extraction or enhancement.",
        # AI project query tasks (including multimodal)
        "query_project_openai": "OpenAI query with selected documents and optional image content.",
        "query_project_gemini": "Google Gemini query with selected documents and optional image content.",
        "query_project_claude": "Claude query with selected documents and optional image content.",
        "query_project_mistral": "Mistral query with selected documents (text-only).",
        "query_project_deepseek": "DeepSeek query with selected documents and optional image content.",
        "query_project_qwen": "Qwen query with selected documents and optional image content.",
        # Export tasks
        "export_data_task": "Export of project data to various formats.",
        "export_to_zenodo_task": "Export of project data to Zenodo repository.",
        # Miscellaneous tasks
        "copy_project": "Copying of a project to create a new instance.",
    }

    def before_start(self, task_id, args, kwargs):
        """Initialize project and user before the task starts."""
        self.task_id = task_id
        self.get_project_and_user(args[0], args[1])
        self.task_params = kwargs
        self.task_start_time = time.time()
        self.start_datetime = timezone.now()

        # Task tracking
        self.total_items = None
        self.processed_items = 0
        self.successful_items = 0
        self.failed_items = 0
        self.skipped_items = 0

        # Get standard description for this task type
        task_description = self.TASK_DESCRIPTIONS.get(self.name, "")

        # Determine category based on task name
        category = self._get_task_category()

        # Create a new task object in the database
        self.twf_task = Task.objects.create(
            celery_task_id=task_id,
            project=self.project,
            user=self.user,
            status="STARTED",
            task_type="celery",
            category=category,
            title=f"Started: {self.name}",
            description=task_description,
            text=f"Task initiated at {self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')}.\n",
        )

        logger.info(
            f"Starting task {self.name} (ID: {task_id}) for project {self.project.title}"
        )
        self.update_state(
            state="STARTED", meta={"current": 0, "total": 100, "text": "Task started"}
        )

    def _get_task_category(self):
        """Determine the category of a task based on its name."""
        task_name = self.name.lower()

        # AI processing tasks
        if any(x in task_name for x in ['openai', 'gemini', 'claude', 'mistral', 'deepseek', 'qwen', 'query_project']):
            return 'ai_processing'

        # Dictionary enrichment tasks
        if any(x in task_name for x in ['gnd', 'geonames', 'wikidata', 'search_ai_entries', 'search_ai_entry']):
            return 'enrichment'

        # Import/extraction tasks
        if any(x in task_name for x in ['extract', 'import', 'load']):
            return 'import'

        # Export tasks
        if 'export' in task_name:
            return 'export'

        # Enrichment tasks
        if 'enrich' in task_name:
            return 'enrichment'

        # Copy/system tasks
        if 'copy' in task_name:
            return 'system'

        # Default
        return None

    @staticmethod
    def validate_task_parameters(kwargs, required_params):
        """
        Ensure all required parameters are present in kwargs.

        This method checks that all parameters in the required_params list are
        present in the kwargs dictionary. If any are missing, it raises a ValueError
        with a message indicating which parameters are missing.

        Args:
            kwargs (dict): Dictionary of keyword arguments to check
            required_params (list): List of parameter names that must be present

        Raises:
            ValueError: If any required parameters are missing from kwargs
        """
        missing_params = [param for param in required_params if param not in kwargs]
        if missing_params:
            raise ValueError(
                f"Missing required parameters: {', '.join(missing_params)}"
            )

    def get_project_and_user(self, project_id, user_id):
        """
        Fetch project and user from the database and store them as instance attributes.

        This method is typically called during task initialization to retrieve the
        Project and User objects associated with the task. The objects are stored as
        instance attributes for use by other methods.

        Args:
            project_id (int): ID of the project to retrieve
            user_id (int): ID of the user to retrieve

        Raises:
            ValueError: If either project_id or user_id is missing, or if the
                       corresponding Project or User object does not exist

        Note:
            After successful execution, self.project and self.user will be set
            to the retrieved objects.
        """
        if not project_id or not user_id:
            raise ValueError("Project ID and User ID are required")

        try:
            self.project = Project.objects.get(pk=project_id)
            self.user = User.objects.get(pk=user_id)
        except Project.DoesNotExist:
            raise ValueError(f"Project with ID {project_id} not found")
        except User.DoesNotExist:
            raise ValueError(f"User with ID {user_id} not found")

    def set_total_items(self, total):
        """Set the total number of items for progress calculation."""
        self.total_items = total
        self.processed_items = 0  # Reset counter

        # Update task title to reflect the total
        if self.twf_task and total > 0:
            item_type = self.get_item_type_name()
            self.twf_task.title = f"Processing {total} {item_type}"
            self.twf_task.text += f"Found {total} {item_type} to process.\n"
            self.twf_task.total_items = total
            self.twf_task.processed_items = 0
            self.twf_task.save(update_fields=["title", "text", "total_items", "processed_items"])
            logger.info(f"Task {self.task_id}: set to process {total} {item_type}")

    def get_item_type_name(self):
        """Return a descriptive name for the type of items being processed.
        Subclasses can override this if needed."""
        if "collection" in self.name.lower():
            return "Collection Items"
        elif "document" in self.name.lower() or "doc" in self.name.lower():
            return "Documents"
        elif "page" in self.name.lower():
            return "Pages"
        elif "dict" in self.name.lower():
            return "Dictionary Entries"
        elif "export" in self.name.lower():
            return "Items"
        else:
            return "Items"

    def advance_task(self, text="In progress", status="success"):
        """Increment the progress counter and update task progress.
        status can be 'success', 'failure', or 'skipped'
        """
        if self.total_items is not None and self.total_items > 0:
            self.processed_items += 1  # Increment processed count

            # Track detailed status
            if status.lower() == "success":
                self.successful_items += 1
            elif status.lower() == "failure":
                self.failed_items += 1
            elif status.lower() == "skipped":
                self.skipped_items += 1

            progress = int((self.processed_items / self.total_items) * 100)

            # Add detailed progress info to text
            detailed_text = f"{text} ({self.processed_items}/{self.total_items})"
            self.update_progress(progress, detailed_text)

            # Update text in database with more detail if appropriate
            if (
                self.processed_items % 10 == 0
                or self.processed_items == self.total_items
            ):
                if self.twf_task:
                    elapsed = time.time() - self.task_start_time
                    avg_time = (
                        elapsed / self.processed_items
                        if self.processed_items > 0
                        else 0
                    )
                    self.twf_task.text += f"Progress: {self.processed_items}/{self.total_items} items processed "
                    self.twf_task.text += (
                        f"({elapsed:.1f}s elapsed, {avg_time:.2f}s per item).\n"
                    )
                    # Update database item counters
                    self.twf_task.processed_items = self.processed_items
                    self.twf_task.successful_items = self.successful_items
                    self.twf_task.failed_items = self.failed_items
                    self.twf_task.save(update_fields=[
                        "text",
                        "processed_items",
                        "successful_items",
                        "failed_items"
                    ])

    def update_progress(self, progress, text="In progress"):
        """Update task progress in the database."""
        if self.twf_task:
            self.update_state(
                state="PROGRESS", meta={"current": progress, "total": 100, "text": text}
            )
            self.twf_task.progress = progress

            # Update the title to reflect progress
            if progress < 100:
                item_type = self.get_item_type_name()
                if self.total_items:
                    self.twf_task.title = (f"Processing {self.processed_items}/{self.total_items} "
                                           f"{item_type} ({progress}%)")

            self.twf_task.save(update_fields=["progress", "title"])

    def process_ai_request(
        self,
        items,
        client_name,
        prompt,
        role_description,
        metadata_field,
        prompt_mode="text_only",
        model=None,
        api_key=None,
    ):
        """
        Generalized function to process AI requests for multiple items.

        This method handles sending requests to AI providers for a batch of items.
        It tracks progress, manages the AI client, and stores results in each item's metadata.

        Args:
            items (QuerySet): Collection of items to process (documents, collection items, etc.)
            client_name (str): The name of the AI provider to use ('openai', 'genai', etc.)
            prompt (str): The text prompt to send to the model
            role_description (str): System role description for the AI model
            metadata_field (str): Field name for storing results in each item's metadata
            prompt_mode (str): One of "text_only", "images_only", or "text_and_images".
            model (str): Optional model name to use. If not provided, uses default_model from credentials.
            api_key (str): Optional API key override. If provided, overrides project credentials.
        """
        # Set up the task with detailed tracking information
        total_items = len(items)
        self.set_total_items(total_items)
        self.create_configured_client(client_name, role_description, api_key=api_key)

        # Use provided model or fall back to default from credentials
        self.model = model if model else self.credentials.get("default_model", "")

        self._generate_task_init_description(prompt, role_description, prompt_mode)
        is_image_prompt_mode = self._clean_prompt_mode(prompt_mode)

        # Track success, failure, and timing stats
        successful_items = 0
        failed_items = 0
        total_time = 0

        # Process each item.
        for item in items:
            try:
                image_count = 0
                if is_image_prompt_mode:
                    if isinstance(item, Document):
                        image_count = self._prepare_page_images(item.pages.all())
                    elif isinstance(item, Page):
                        image_count = self._prepare_page_images([item])
                    elif isinstance(item, CollectionItem):
                        # Handle collection items with images
                        # TODO: Implement image handling for collection items
                        pass
                    else:
                        # Handle item types without images
                        pass

                response_dict, elapsed_time = self.prompt_client(item, prompt)
                self.client.clear_image_resources()

                # Save the AI response to the item's metadata
                item.metadata[metadata_field] = response_dict
                item.save(current_user=self.user)

                # Update task statistics
                successful_items += 1
                total_time += elapsed_time

                # Detailed progress message including timing information
                progress_msg = (
                    f"Processed item {self.processed_items+1}/{total_items} "
                    f"in {elapsed_time:.2f}s"
                )

                self.advance_task(text=progress_msg, status="success")

            except Exception as e:
                failed_items += 1
                error_msg = str(e)
                # Log the error with more detail
                logger.error(f"Error processing item with {client_name}: {error_msg}")

                # Add error details to the task text
                self.twf_task.text += (
                    f"Error processing item {self.processed_items+1}: {error_msg}\n"
                )

                # Track the failure in the progress indicators
                self.advance_task(
                    text=f"Error processing item {self.processed_items+1}/{total_items}",
                    status="failure",
                )

        avg_time = total_time / successful_items if successful_items else 0

        self._handle_task_success(
            processed_items=self.processed_items,
            successful_items=successful_items,
            failed_items=failed_items,
            client_name=client_name,
            model=self.model,
            total_time=total_time,
            average_time=avg_time,
        )

        # For Celery, if there were failures, raise an exception
        if failed_items > 0:
            # We raise a standard Exception that Celery can serialize properly
            raise Exception(f"{failed_items} items failed to process")

    def process_single_ai_request(
        self,
        items,
        client_name,
        prompt,
        role_description,
        metadata_field,
        prompt_mode="text_only",
        model=None,
        api_key=None,
    ):
        """
        Process an AI request with possible multimodal content (text + images).

        This method handles sending requests to various AI providers (OpenAI, Google Gemini,
        Anthropic Claude, Mistral) with optional multimodal content. It supports three modes:

        1. Text Only: Only sends the text prompt and context
        2. Images Only: Sends only images with a minimal text prompt
        3. Text + Images: Sends both text and images

        For image-based modes, the method automatically selects up to 5 images per document
        from the provided items. Images are retrieved directly from the Transkribus server
        using their URLs rather than downloading them locally first. The images are scaled
        to 50% of their original size to reduce bandwidth usage and improve processing time.

        The method handles provider capability detection and automatic fallback to text-only
        mode when needed, ensuring graceful degradation when an unsupported feature is requested.

        Args:
            items (QuerySet): The document items to process. These should have a get_text() method
                             and, for documents, should have associated pages with images.
            client_name (str): The name of the AI client to use: 'openai', 'genai', 'anthropic', or 'mistral'.
                              Note that only 'openai' and 'genai' currently support multimodal content.
            prompt (str): The prompt text from the user
            role_description (str): System role description for the AI model
            metadata_field (str): Field name for storing results in metadata
            prompt_mode (str): One of "text_only", "images_only", or "text_and_images".
                              Defaults to "text_only".
            model (str): Optional model name to use. If not provided, uses default_model from credentials.

        Technical Details:
            - Image resources are added to the AI client via the add_image_resource() method
            - For OpenAI and Gemini, images are sent as URLs in the prompt content
            - The document's pages are accessed via the pages relation (item.pages.all())
            - Images are retrieved via the Page model's get_image_url() method with scale_percent=50
            - For images-only mode with no text, a default prompt is used if none is provided
            - Images are cleared from the client after use with clear_image_resources()

        Note:
            If a client doesn't support images but an image mode is requested, the method
            will automatically fall back to text-only mode with an appropriate warning in
            the task log. Similarly, if images-only mode is selected but no images are found,
            it will fall back to text-only mode.
        """
        self.set_total_items(1)
        self.create_configured_client(client_name, role_description, api_key=api_key)

        # Use provided model or fall back to default from credentials
        self.model = model if model else self.credentials.get("default_model", "")

        self._generate_task_init_description(prompt, role_description, prompt_mode)

        is_image_prompt_mode = self._clean_prompt_mode(prompt_mode)

        # Process images if needed based on mode
        if is_image_prompt_mode:
            # Collect up to 5 images from each document
            image_count = 0
            for item in items:
                # Get up to 5 pages from this document, ordered by page number
                pages = item.pages.all().order_by("tk_page_number")[:5]
                image_count += self._prepare_page_images(pages)

            if image_count > 0:
                self.twf_task.text += f"Included {image_count} images in the prompt.\n"
            else:
                self.twf_task.text += (
                    "No valid images found in the selected documents.\n"
                )

                # If we're in images-only mode but found no images, warn user and fall back to text
                if is_image_prompt_mode:
                    self.twf_task.text += ("Warning: No images found but 'Images only' mode selected. "
                                           "Including text context instead.\n")
                    prompt_mode = "text_only"

        # Prepare the prompt text based on mode
        full_prompt = prompt

        # Add text context if mode includes text or if we're fallback from images-only with no images
        if prompt_mode in ["text_only", "text_and_images"]:
            context_text = ""
            for item in items:
                context_text += item.get_text() + "\n"

            # Only add context if it's not empty
            if context_text.strip():
                full_prompt += "\n\n" + "Context:\n" + context_text

        # For images-only mode with no text prompt, use a minimal prompt
        if prompt_mode == "images_only":
            # If user provided a prompt, use it; otherwise use a default
            if not prompt.strip():
                full_prompt = "Please describe what you see in these images."

            # Images-only should NOT include text context
            self.twf_task.text += (
                "Images-only mode: Using only images without text context.\n"
            )

        # Call the API with proper error handling
        try:
            # Use self.model if available, otherwise fall back to default_model from credentials
            model_to_use = getattr(self, "model", None) or self.credentials.get(
                "default_model", ""
            )
            response, elapsed_time = self.client.prompt(
                model=model_to_use, prompt=full_prompt
            )
            self.client.clear_image_resources()
            self._handle_task_success(ai_result=response)

            # Return the result for display on the page
            return {"ai_result": response}

        except Exception as e:
            # Handle any exceptions that occur during API call
            error_msg = str(e)
            self._generate_task_failure_description(error_msg)
            self.client.clear_image_resources()

            # Let Celery handle the task failure by re-raising the exception
            raise

    def end_task(self, status="SUCCESS", error_msg=None, **kwargs):
        """Mark the task as completed or failed with detailed documentation."""
        if self.twf_task:
            # Calculate task duration
            end_time = timezone.now()
            duration = (end_time - self.start_datetime).total_seconds()

            # Format summary for the task text
            summary = self._generate_task_summary(status, duration, error_msg)
            self.twf_task.text += summary

            # Update the final task title with a concise summary
            item_type = self.get_item_type_name()
            if status == "SUCCESS":
                if self.total_items:
                    self.twf_task.title = (
                        f"Processed {self.processed_items} {item_type}"
                    )
                    if self.successful_items < self.processed_items:
                        self.twf_task.title += f" ({self.successful_items} successful)"
                else:
                    self.twf_task.title = f"Successfully completed {self.name}"
            else:
                if error_msg:
                    self.twf_task.title = (
                        f"Failed: {error_msg[:50]}..."
                        if len(error_msg) > 50
                        else f"Failed: {error_msg}"
                    )
                else:
                    self.twf_task.title = f"Failed to process {item_type}"

            # Update metadata
            meta = {"current": 100, "total": 100, "text": "Task finished"}
            meta["duration"] = duration
            meta["processed_items"] = self.processed_items
            meta["successful_items"] = self.successful_items
            meta["failed_items"] = self.failed_items
            meta["skipped_items"] = self.skipped_items

            if kwargs:
                meta.update(kwargs)

            # Update task state (skip for FAILURE as Celery will handle it when exception is raised)
            if status != "FAILURE":
                self.update_state(state=status, meta=meta)

            # Update database record
            self.twf_task.end_time = end_time
            self.twf_task.status = status
            self.twf_task.meta = meta
            self.twf_task.processed_items = self.processed_items
            self.twf_task.successful_items = self.successful_items
            self.twf_task.failed_items = self.failed_items
            self.twf_task.save(
                update_fields=[
                    "title",
                    "text",
                    "end_time",
                    "status",
                    "meta",
                    "processed_items",
                    "successful_items",
                    "failed_items"
                ]
            )

            # Log completion
            log_msg = (
                f"Task {self.name} (ID: {self.task_id}) completed with status {status}"
            )
            if status == "SUCCESS":
                logger.info(log_msg)
            else:
                logger.error(f"{log_msg}: {error_msg}")

    def _clean_prompt_mode(self, prompt_mode):
        """Check if the client supports images and adjust prompt mode accordingly."""
        img_support = self.client.has_multimodal_support()

        if prompt_mode in ["images_only", "text_and_images"] and not img_support:
            fallback_message = f"Warning: {self.client} does not support images. Falling back to text-only mode.\n"
            self.twf_task.text += fallback_message
            return False

        if prompt_mode in ["images_only", "text_and_images"] and img_support:
            return True

        return False

    def _prepare_page_images(self, pages):
        image_count = 0
        for page in pages:
            # Use our new method to get image URL with 50% scaling
            img_url = page.get_image_url(scale_percent=50)
            if img_url:
                self.client.add_image_resource(img_url)
                self.twf_task.text += f"Added image from page {page.tk_page_number} of document {page.document.title}\n"
                image_count += 1
        return image_count

    def _generate_task_init_description(self, prompt, role_description, prompt_mode):
        if self.twf_task:
            self.twf_task.text += f"AI Client: {self.client}\n"
            self.twf_task.text += f"Model: {self.credentials['default_model']}\n"
            self.twf_task.text += (
                f"Role: {role_description[:100]}...\n"
                if len(role_description) > 100
                else f"Role: {role_description}\n"
            )
            self.twf_task.text += (
                f"Prompt: {prompt[:100]}...\n"
                if len(prompt) > 100
                else f"Prompt: {prompt}\n"
            )
            self.twf_task.text += f"Prompt mode: {prompt_mode}\n"
            self.twf_task.save(update_fields=["text"])

    def _handle_task_success(self, **kwargs):
        if self.twf_task:
            self.twf_task.status = "SUCCESS"
            self.twf_task.end_time = timezone.now()

            self.twf_task.meta = {}
            for key, value in kwargs.items():
                self.twf_task.meta[key] = value

            self.twf_task.text += "\n---- TASK SUMMARY ----\n"
            self.twf_task.text += "Status: SUCCESS\n"
            self.twf_task.text += f"Duration: {(timezone.now() - self.start_datetime).total_seconds():.2f} seconds\n"
            self.twf_task.text += "----------------------\n"
            self.twf_task.save()

    def _generate_task_failure_description(self, error_msg):
        logger.error(f"Error in AI request: {error_msg}")

        # Record the error in the database task
        if self.twf_task:
            self.twf_task.text += f"Error: {error_msg}\n"
            self.twf_task.status = "FAILURE"
            self.twf_task.end_time = timezone.now()
            self.twf_task.title = (
                f"Failed: {error_msg[:50]}..."
                if len(error_msg) > 50
                else f"Failed: {error_msg}"
            )
            self.twf_task.text += "\n---- TASK SUMMARY ----\n"
            self.twf_task.text += "Status: FAILURE\n"
            self.twf_task.text += f"Duration: {(timezone.now() - self.start_datetime).total_seconds():.2f} seconds\n"
            self.twf_task.text += f"Error: {error_msg}\n"
            self.twf_task.text += "----------------------\n"
            self.twf_task.save()

    def _generate_task_summary(self, status, duration, error_msg=None):
        """Generate a detailed summary of the task for documentation purposes."""
        summary = "\n---- TASK SUMMARY ----\n"
        summary += f"Status: {status}\n"
        summary += f"Duration: {duration:.2f} seconds"

        if duration > 60:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            summary += f" ({minutes}m {seconds}s)"
        summary += "\n"

        if self.total_items:
            summary += f"Total items: {self.total_items}\n"
            summary += f"Processed items: {self.processed_items}\n"

            if self.successful_items > 0:
                summary += f"Successfully processed: {self.successful_items}\n"
            if self.failed_items > 0:
                summary += f"Failed to process: {self.failed_items}\n"
            if self.skipped_items > 0:
                summary += f"Skipped items: {self.skipped_items}\n"

            if self.processed_items > 0:
                avg_time = duration / self.processed_items
                summary += f"Average processing time per item: {avg_time:.2f} seconds\n"

        if error_msg:
            summary += f"\nError: {error_msg}\n"

        summary += "----------------------\n"
        return summary

    def create_configured_client(self, client_name, role_description, api_key=None):
        """
        Create and configure an AI client for the specified provider.

        This method handles the initialization of an AI client by retrieving the
        appropriate credentials from the project configuration and creating a new
        instance of AiApiClient. The client is configured with the specified
        provider, API key, and role description.

        For multimodal functionality, the client initialization sets up the foundation,
        but additional configuration happens in process_single_ai_request based on
        the prompt_mode parameter:
        - For text_only mode: No additional configuration needed
        - For images_only or text_and_images modes: Image resources are added using
          the add_image_resource method if the provider supports images


        Args:
            client_name (str): The name of the AI provider to use
                              ('openai', 'genai', 'anthropic', or 'mistral')
            role_description (str): System role description for the AI model
            api_key (str): Optional API key override. If provided, overrides the key
                          from project credentials (used by AIConfiguration-based tasks).

        Provider-Specific Details:
            - OpenAI: Configured for multimodal support with vision models
            - Google Gemini: Configured for multimodal support with vision models
            - Claude & Mistral: Currently configured for text-only support,
              with automatic fallback for multimodal requests

        Note:
            The created client is stored in self.client and can be used by other
            methods to interact with the AI provider.
        """
        self.client_name = client_name
        self.credentials = self.project.get_credentials(client_name)

        # Override API key from AIConfiguration if provided
        if api_key:
            self.credentials = dict(self.credentials)
            self.credentials["api_key"] = api_key

        # Get generic AI settings from project configuration
        ai_settings = self.project.conf_ai_settings.get("generic", {})

        # Create client with settings
        self.client = create_ai_client(
            client_name,
            self.credentials["api_key"],
            system_prompt=role_description,
            **ai_settings,
        )

    def prompt_client(self, item, prompt):
        """
        Send a text-only prompt to the AI model with context from a specific item.

        This is a helper method that constructs a prompt with context from a single
        item (like a document or collection item) and sends it to the currently
        configured AI client. The item's text content is appended to the prompt
        as context.

        This method is specifically for text-only prompts and does not handle images.
        For multimodal prompts that include images, use process_single_ai_request with
        an appropriate prompt_mode instead.

        Args:
            item: An item with a get_text() method (Document, CollectionItem, etc.)
            prompt (str): The text prompt to send to the model

        Returns:
            tuple: (response_dict, elapsed_time) containing the parsed response
                  from the AI model and the time taken to receive it

        Raises:
            Exception: If there's an error communicating with the AI provider or
                      processing the response

        Related Methods:
            - For multimodal processing, see process_single_ai_request instead
            - For batch processing, see process_ai_request

        Technical Details:
            - Uses the AI client configured in create_configured_client
            - Adds text context from the item using its get_text() method
            - Does not support images or other media types
            - Returns the response in a standardized dictionary format
        """
        try:
            context = item.get_text()
            prompt = prompt + "\n\n" + "Context:\n" + context
            # Use self.model if available, otherwise fall back to default_model from credentials
            model_to_use = getattr(self, "model", None) or self.credentials.get(
                "default_model", ""
            )
            response, elapsed_time = self.client.prompt(
                model=model_to_use, prompt=prompt
            )
            return response, elapsed_time
        except Exception as e:
            # Reraise the exception to be handled by the calling function
            logger.error(f"Error in prompt_client: {str(e)}")
            raise

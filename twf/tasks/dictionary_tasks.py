"""Celery tasks for searching entities in dictionaries"""

import logging
import traceback

from celery import shared_task

from twf.clients.geonames_client import search_location
from twf.clients.gnd_client import search_gnd
from twf.clients.wikidata_client import search_wikidata_entities
from twf.models import Dictionary, DictionaryEntry
from twf.tasks.task_base import BaseTWFTask

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTWFTask)
def search_gnd_entries(self, project_id, user_id, **kwargs):
    """
    Search GND (German National Library) for all entries in a dictionary.

    Args:
        self: Celery task instance
        project_id: ID of the project
        user_id: ID of the user performing the search
        **kwargs: Additional parameters including:
            - dictionary_id: ID of the dictionary to process
            - earliest_birth_year: Filter results by birth year range
            - latest_birth_year: Filter results by birth year range
            - show_empty: Whether to show results with no birth year

    Returns:
        None (updates dictionary entry metadata with GND data)
    """
    self.validate_task_parameters(
        kwargs,
        ["dictionary_id", "earliest_birth_year", "latest_birth_year", "show_empty"],
    )

    dictionary = Dictionary.objects.get(id=kwargs.get("dictionary_id"))
    self.set_total_items(dictionary.entries.count())

    earliest_birth_year = kwargs.get("earliest_birth_year")
    latest_birth_year = kwargs.get("latest_birth_year")
    show_empty = kwargs.get("show_empty")

    found_entries = 0
    for entry in dictionary.entries.all():
        try:
            # Perform the GND search
            results = search_gnd(
                entry.label,
                earliest_birth_year=earliest_birth_year,
                latest_birth_year=latest_birth_year,
                show_empty=show_empty,
            )

            if results:
                data = results[0]
                # Convert GND data to standard enrichment format
                gnd_id = data["gnd_id"][0] if data["gnd_id"] else None
                preferred_name = data["preferred_name"][0] if data["preferred_name"] else entry.label

                if gnd_id:
                    # Use set_enrichment method to write in standard format
                    entry.set_enrichment(
                        enrichment_type="authority_id",
                        normalized_value=preferred_name,
                        enrichment_data={
                            "id_type": "gnd",
                            "id_value": gnd_id,
                            "resource_url": f"https://d-nb.info/gnd/{gnd_id}",
                            "preferred_name": preferred_name,
                            "variant_names": data.get("variant_names", []),
                            "birth_date": data["birth_date"][0] if data.get("birth_date") else None,
                            "death_date": data["death_date"][0] if data.get("death_date") else None,
                            "roles": data.get("roles", []),
                        },
                        user=self.user
                    )
                    found_entries += 1

                # Also keep raw GND data in metadata for backward compatibility
                entry.metadata["gnd"] = data
                entry.save(current_user=self.user)

            # Update progress
            self.advance_task(status="success")
        except Exception as e:
            # Log the exception details
            error_message = f"Error processing entry '{entry.label}': {e}"
            error_traceback = traceback.format_exc()
            logger.error(error_message)
            logger.debug(error_traceback)

            # Add error to task text for user visibility
            if self.twf_task:
                self.twf_task.text += f"  ✗ {error_message}\n"
                self.twf_task.save(update_fields=["text"])

            # Continue processing other entries instead of ending task
            self.advance_task(status="failure")
            continue

    # Finalize the task
    self.end_task()


@shared_task(bind=True, base=BaseTWFTask)
def search_wikidata_entries(self, project_id, user_id, **kwargs):
    """Search for entities using the Wikidata API for all entries in a dictionary"""
    self.validate_task_parameters(kwargs, ["dictionary_id", "entity_type", "language"])

    dictionary = Dictionary.objects.get(id=kwargs.get("dictionary_id"))
    self.set_total_items(dictionary.entries.count())
    entity_type = kwargs.get("entity_type")
    language = kwargs.get("language")

    found_entries = 0
    failed_entries = 0

    for entry in dictionary.entries.all():
        try:
            # Perform Wikidata search for each entry
            results = search_wikidata_entities(
                query=entry.label, entity_type=entity_type, language=language, limit=5
            )

            if results:
                data = results[0]
                # Convert Wikidata data to standard enrichment format
                wikidata_id = data.get("id")
                label = data.get("label", entry.label)

                if wikidata_id:
                    enrichment_data = {
                        "id_type": "wikidata",
                        "id_value": wikidata_id,
                        "resource_url": f"https://www.wikidata.org/wiki/{wikidata_id}",
                        "description": data.get("description", ""),
                    }

                    # Add coordinates if available
                    if data.get("coordinates"):
                        coords = data["coordinates"]
                        enrichment_data["latitude"] = coords.get("latitude")
                        enrichment_data["longitude"] = coords.get("longitude")

                    # Use set_enrichment method to write in standard format
                    entry.set_enrichment(
                        enrichment_type="authority_id",
                        normalized_value=label,
                        enrichment_data=enrichment_data,
                        user=self.user
                    )
                    found_entries += 1

                # Also keep raw Wikidata data in metadata for backward compatibility
                entry.metadata["wikidata"] = data
                entry.save(current_user=self.user)

            # Update the progress
            self.advance_task(status="success")

        except Exception as e:
            failed_entries += 1
            error_message = f"Error processing entry '{entry.label}': {e}"
            logger.error(error_message)

            # Add error to task text for user visibility
            if self.twf_task:
                self.twf_task.text += f"  ✗ {error_message}\n"
                self.twf_task.save(update_fields=["text"])

            # Continue processing other entries
            self.advance_task(status="failure")

    # Add summary to task text
    if self.twf_task:
        self.twf_task.text += f"\nWikidata Search Summary:\n"
        self.twf_task.text += f"  • Entries enriched: {found_entries}\n"
        self.twf_task.text += f"  • Entries failed: {failed_entries}\n"
        self.twf_task.save(update_fields=["text"])

    self.end_task()


@shared_task(bind=True, base=BaseTWFTask)
def search_geonames_entries(self, project_id, user_id, **kwargs):
    """
    Search Geonames for all entries in a dictionary.

    Args:
        self: Celery task instance
        project_id: ID of the project
        user_id: ID of the user performing the search
        **kwargs: Additional parameters including:
            - dictionary_id: ID of the dictionary to process
            - similarity_threshold: Minimum similarity score for matches
            - country_restriction: Optional country code to restrict results

    Returns:
        None (updates dictionary entry metadata with Geonames data)
    """
    self.validate_task_parameters(
        kwargs, ["dictionary_id", "similarity_threshold", "country_restriction"]
    )

    dictionary = Dictionary.objects.get(id=kwargs.get("dictionary_id"))
    self.set_total_items(dictionary.entries.count())

    geonames_username = self.project.get_credentials("geonames").get("username")
    similarity_threshold = kwargs.get("similarity_threshold")
    country_restriction = kwargs.get("country_restriction")

    if geonames_username == "" or not geonames_username:
        error_message = "Geonames username is required"
        self.end_task(status="FAILURE", error_msg=error_message)
        raise ValueError(error_message)

    if country_restriction == "":
        country_restriction = None

    found_entries = 0
    for entry in dictionary.entries.all():
        # Perform Geonames search for each entry
        try:
            location_info_list = search_location(
                entry.label,
                geonames_username,
                False,
                country_restriction,
                similarity_threshold,
            )

            if location_info_list:
                data, similarity = location_info_list[0]
                # Convert GeoNames data to standard enrichment format
                geonames_id = data.get("id")
                name = data.get("name", entry.label)

                if geonames_id:
                    # Use set_enrichment method to write in standard format
                    entry.set_enrichment(
                        enrichment_type="authority_id",
                        normalized_value=name,
                        enrichment_data={
                            "id_type": "geonames",
                            "id_value": str(geonames_id),
                            "resource_url": f"https://www.geonames.org/{geonames_id}/",
                            "country": data.get("country", ""),
                            "latitude": data.get("lat"),
                            "longitude": data.get("lng"),
                            "similarity_score": similarity,
                        },
                        user=self.user
                    )
                    found_entries += 1

                # Also keep raw GeoNames data in metadata for backward compatibility
                entry.metadata["geonames"] = data
                entry.save(current_user=self.user)

            # Update the progress
            self.advance_task()
        except Exception as e:
            self.end_task(status="FAILURE")

    self.end_task()


@shared_task(bind=True, base=BaseTWFTask)
def search_gnd_entry(self, project_id, user_id, **kwargs):
    """
    Search GND (German National Library) for a single dictionary entry.

    Args:
        self: Celery task instance
        project_id: ID of the project
        user_id: ID of the user performing the search
        **kwargs: Additional parameters including:
            - entry_id: ID of the dictionary entry to search
            - earliest_birth_year: Filter results by birth year range
            - latest_birth_year: Filter results by birth year range
            - show_empty: Whether to show results with no birth year

    Returns:
        None (updates dictionary entry metadata with GND data)
    """
    self.validate_task_parameters(
        kwargs, ["entry_id", "earliest_birth_year", "latest_birth_year", "show_empty"]
    )

    dictionary_entry = DictionaryEntry.objects.get(id=kwargs.get("entry_id"))
    self.set_total_items(1)

    try:
        results = search_gnd(
            dictionary_entry.label,
            earliest_birth_year=kwargs.get("earliest_birth_year"),
            latest_birth_year=kwargs.get("latest_birth_year"),
            show_empty=kwargs.get("show_empty"),
        )
        if results:
            data = results[0]
            dictionary_entry.metadata["gnd"] = data
            dictionary_entry.save(current_user=self.user)
    except Exception as e:
        self.end_task(status="FAILURE")

    self.end_task()


@shared_task(bind=True, base=BaseTWFTask)
def search_geonames_entry(self, project_id, user_id, **kwargs):
    """
    Search Geonames for a single dictionary entry.

    Args:
        self: Celery task instance
        project_id: ID of the project
        user_id: ID of the user performing the search
        **kwargs: Additional parameters including:
            - entry_id: ID of the dictionary entry to search
            - similarity_threshold: Minimum similarity score for matches
            - country_restriction: Optional country code to restrict results

    Returns:
        None (updates dictionary entry metadata with Geonames data)
    """
    self.validate_task_parameters(
        kwargs, ["entry_id", "similarity_threshold", "country_restriction"]
    )

    dictionary_entry = DictionaryEntry.objects.get(id=kwargs.get("entry_id"))
    self.set_total_items(1)

    geonames_username = self.project.get_credentials("geonames").get("username")
    similarity_threshold = kwargs.get("similarity_threshold")
    country_restriction = kwargs.get("country_restriction")

    if country_restriction == "":
        country_restriction = None

    try:
        location_info_list = search_location(
            dictionary_entry.label,
            geonames_username,
            False,
            country_restriction,
            similarity_threshold,
        )
        if location_info_list:
            data, similarity = location_info_list[0]
            dictionary_entry.metadata["geonames"] = data
            dictionary_entry.save(current_user=self.user)
    except Exception as e:
        self.end_task(status="FAILURE")

    self.end_task()


@shared_task(bind=True, base=BaseTWFTask)
def search_wikidata_entry(self, project_id, user_id, **kwargs):
    """
    Search Wikidata for a single dictionary entry.

    Args:
        self: Celery task instance
        project_id: ID of the project
        user_id: ID of the user performing the search
        **kwargs: Additional parameters including:
            - entry_id: ID of the dictionary entry to search
            - entity_type: Type of Wikidata entity to search for
            - language: Language code for search results

    Returns:
        None (updates dictionary entry metadata with Wikidata data)
    """
    self.validate_task_parameters(kwargs, ["entry_id", "entity_type", "language"])

    dictionary_entry = DictionaryEntry.objects.get(id=kwargs.get("entry_id"))
    self.set_total_items(1)

    try:
        results = search_wikidata_entities(
            query=dictionary_entry.label,
            entity_type=kwargs.get("entity_type"),
            language=kwargs.get("language"),
            limit=5,
        )
        if results:
            data = results[0]
            dictionary_entry.metadata["wikidata"] = data
            dictionary_entry.save(current_user=self.user)
    except Exception as e:
        self.end_task(status="FAILURE")

    self.end_task()


@shared_task(bind=True, base=BaseTWFTask)
def search_ai_entries(self, project_id, user_id, **kwargs):
    """
    Unified task for AI batch processing of dictionary entries.

    Uses AIConfiguration which contains all AI settings (provider, model, prompt, etc.).

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Must include:
            - dictionary_id: ID of the dictionary to process
            - ai_configuration_id: ID of the AIConfiguration to use
    """
    from twf.models import AIConfiguration

    self.validate_task_parameters(kwargs, ["dictionary_id", "ai_configuration_id"])

    # Load the AI configuration
    ai_config_id = kwargs.get("ai_configuration_id")
    try:
        ai_config = AIConfiguration.objects.get(id=ai_config_id, project=self.project)
    except AIConfiguration.DoesNotExist:
        raise ValueError(f"AIConfiguration with id {ai_config_id} not found for this project")

    dictionary = Dictionary.objects.get(id=kwargs.get("dictionary_id"))

    # Process dictionary entries using the AI configuration settings
    self.process_ai_request(
        dictionary.entries.all(),
        ai_config.provider,
        ai_config.prompt_template,
        ai_config.system_role,
        ai_config.provider,
        model=ai_config.model,
        api_key=ai_config.api_key,
    )


@shared_task(bind=True, base=BaseTWFTask)
def search_ai_entry(self, project_id, user_id, **kwargs):
    """
    Unified task for AI request (supervised) processing of a single dictionary entry.

    Uses AIConfiguration which contains all AI settings (provider, model, prompt, etc.).

    Args:
        project_id: Project ID
        user_id: User ID
        **kwargs: Must include:
            - entry_id: ID of the dictionary entry to process
            - ai_configuration_id: ID of the AIConfiguration to use
    """
    from twf.models import AIConfiguration

    self.validate_task_parameters(kwargs, ["entry_id", "ai_configuration_id"])

    # Load the AI configuration
    ai_config_id = kwargs.get("ai_configuration_id")
    try:
        ai_config = AIConfiguration.objects.get(id=ai_config_id, project=self.project)
    except AIConfiguration.DoesNotExist:
        raise ValueError(f"AIConfiguration with id {ai_config_id} not found for this project")

    dictionary_entry = DictionaryEntry.objects.get(id=kwargs.get("entry_id"))

    # Process single dictionary entry using the AI configuration settings
    self.process_ai_request(
        [dictionary_entry],
        ai_config.provider,
        ai_config.prompt_template,
        ai_config.system_role,
        ai_config.provider,
        model=ai_config.model,
        api_key=ai_config.api_key,
    )

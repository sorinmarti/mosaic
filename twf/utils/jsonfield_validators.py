"""
JSONField validation utilities for TWF application.

This module provides validation functions for all JSONFields used in the TWF models.
Validation ensures data integrity and prevents corrupt JSON structures.

Usage:
    from twf.utils.jsonfield_validators import validate_permissions, validate_credentials

    # Validate before saving
    errors = validate_permissions(user_profile.permissions)
    if errors:
        raise ValidationError(errors)
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Valid permission strings
VALID_PERMISSIONS = [
    "document.view",
    "document.edit",
    "tag.view",
    "tag.edit",
    "metadata.view",
    "metadata.edit",
    "metadata.manage",
    "dictionary.view",
    "dictionary.edit",
    "dictionary.manage",
    "collection.view",
    "collection.edit",
    "collection.manage",
    "ai.edit",
    "ai.manage",
    "task.view",
    "task.manage",
    "import_export.view",
    "import_export.edit",
    "import_export.manage",
    "project.manage",
    "prompt.view",
    "note.view",
]

# Valid field types for metadata review
VALID_FIELD_TYPES = ["text", "textarea", "select", "date", "number", "checkbox"]

# Valid AI providers (for legacy support)
VALID_AI_PROVIDERS = ["openai", "claude", "gemini", "mistral", "deepseek", "qwen"]


def validate_permissions(permissions: Dict) -> List[str]:
    """
    Validate UserProfile.permissions JSONField structure.

    Expected structure:
    {
        "<project_id>": {
            "permission.string": true/false,
            ...
        }
    }

    Args:
        permissions: The permissions dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not isinstance(permissions, dict):
        errors.append("Permissions must be a dictionary")
        return errors

    for project_id, perms in permissions.items():
        # Check project_id is string (JSON keys are always strings)
        if not isinstance(project_id, str):
            errors.append(f"Project ID must be string, got {type(project_id)}")
            continue

        # Check permissions dict
        if not isinstance(perms, dict):
            errors.append(f"Permissions for project {project_id} must be a dictionary")
            continue

        # Check each permission
        for perm_string, perm_value in perms.items():
            if not isinstance(perm_value, bool):
                errors.append(
                    f"Permission value for '{perm_string}' in project {project_id} "
                    f"must be boolean, got {type(perm_value)}"
                )

            # Warn about non-standard permissions (don't error, for flexibility)
            if perm_string not in VALID_PERMISSIONS:
                logger.warning(f"Non-standard permission: '{perm_string}' in project {project_id}")

    return errors


def validate_credentials(credentials: Dict) -> List[str]:
    """
    Validate Project.conf_credentials JSONField structure.

    Expected structure:
    {
        "service_name": {
            "credential_key": "value",
            ...
        }
    }

    Args:
        credentials: The credentials dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not isinstance(credentials, dict):
        errors.append("Credentials must be a dictionary")
        return errors

    # Define required fields per service
    required_fields = {
        "transkribus": ["username", "password"],
        "geonames": ["username"],
        "zenodo": ["access_token"],
    }

    for service, creds in credentials.items():
        if not isinstance(creds, dict):
            errors.append(f"Credentials for service '{service}' must be a dictionary")
            continue

        # Check required fields if we know the service
        if service in required_fields:
            for field in required_fields[service]:
                if field not in creds:
                    errors.append(
                        f"Service '{service}' missing required field: '{field}'"
                    )
                elif not creds[field]:
                    errors.append(
                        f"Service '{service}' field '{field}' cannot be empty"
                    )

    return errors


def validate_task_configuration(conf_tasks: Dict) -> List[str]:
    """
    Validate Project.conf_tasks JSONField structure.

    Args:
        conf_tasks: The task configuration dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not isinstance(conf_tasks, dict):
        errors.append("Task configuration must be a dictionary")
        return errors

    # Validate google_sheet config if present
    if "google_sheet" in conf_tasks:
        gs_config = conf_tasks["google_sheet"]
        if not isinstance(gs_config, dict):
            errors.append("google_sheet config must be a dictionary")
        else:
            required_gs_fields = ["sheet_id", "range", "document_id_column"]
            for field in required_gs_fields:
                if field not in gs_config:
                    errors.append(f"google_sheet config missing required field: '{field}'")

    # Validate metadata_review config if present
    if "metadata_review" in conf_tasks:
        mr_config = conf_tasks["metadata_review"]
        if not isinstance(mr_config, dict):
            errors.append("metadata_review config must be a dictionary")
        else:
            # Validate field definitions
            for section in ["page_metadata_review", "document_metadata_review"]:
                if section in mr_config:
                    section_config = mr_config[section]
                    if not isinstance(section_config, dict):
                        errors.append(f"{section} must be a dictionary")
                        continue

                    for field_name, field_def in section_config.items():
                        if not isinstance(field_def, dict):
                            errors.append(
                                f"{section}.{field_name} must be a dictionary"
                            )
                            continue

                        if "field_type" not in field_def:
                            errors.append(
                                f"{section}.{field_name} missing 'field_type'"
                            )
                        elif field_def["field_type"] not in VALID_FIELD_TYPES:
                            errors.append(
                                f"{section}.{field_name} has invalid field_type: "
                                f"'{field_def['field_type']}'"
                            )

    # Validate workflow_definitions if present
    if "workflow_definitions" in conf_tasks:
        wf_defs = conf_tasks["workflow_definitions"]
        if not isinstance(wf_defs, dict):
            errors.append("workflow_definitions must be a dictionary")
        else:
            for wf_type, wf_config in wf_defs.items():
                if not isinstance(wf_config, dict):
                    errors.append(
                        f"Workflow definition for '{wf_type}' must be a dictionary"
                    )
                    continue

                if "batch_size" in wf_config:
                    batch_size = wf_config["batch_size"]
                    if not isinstance(batch_size, int) or batch_size <= 0:
                        errors.append(
                            f"Workflow '{wf_type}' batch_size must be positive integer"
                        )

    return errors


def validate_display_configuration(conf_display: Dict) -> List[str]:
    """
    Validate Project.conf_display JSONField structure.

    Args:
        conf_display: The display configuration dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not isinstance(conf_display, dict):
        errors.append("Display configuration must be a dictionary")
        return errors

    # Validate table config if present
    if "table" in conf_display:
        table_config = conf_display["table"]
        if not isinstance(table_config, dict):
            errors.append("table config must be a dictionary")
        else:
            if "rows_per_page" in table_config:
                rows = table_config["rows_per_page"]
                if not isinstance(rows, int) or rows <= 0:
                    errors.append("table.rows_per_page must be positive integer")

            if "columns_visible" in table_config:
                cols = table_config["columns_visible"]
                if not isinstance(cols, list):
                    errors.append("table.columns_visible must be a list")

    return errors


def validate_document_metadata(metadata: Dict) -> List[str]:
    """
    Validate Document.metadata JSONField structure.

    Note: This is permissive as document metadata is flexible by design.
    Only validates that it's a dictionary and logs warnings for common issues.

    Args:
        metadata: The document metadata dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not isinstance(metadata, dict):
        errors.append("Document metadata must be a dictionary")
        return errors

    # Warn about non-namespaced top-level keys (not an error, just a warning)
    common_namespaces = [
        "transkribus",
        "transkribus_api",
        "google_sheets",
        "json_import",
        "workflow_review",
    ] + VALID_AI_PROVIDERS

    for key in metadata.keys():
        if key not in common_namespaces and not key.startswith("custom_"):
            logger.info(
                f"Document metadata has non-standard key: '{key}'. "
                f"Consider using a namespace."
            )

    return errors


def validate_page_parsed_data(parsed_data: Dict) -> List[str]:
    """
    Validate Page.parsed_data JSONField structure.

    This data comes from simple-alto-parser and should have a specific structure.

    Args:
        parsed_data: The parsed data dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not isinstance(parsed_data, dict):
        errors.append("Parsed data must be a dictionary")
        return errors

    # Check for required top-level keys
    if "file" not in parsed_data:
        errors.append("Parsed data missing 'file' key")
    elif not isinstance(parsed_data["file"], dict):
        errors.append("parsed_data.file must be a dictionary")

    if "elements" not in parsed_data:
        errors.append("Parsed data missing 'elements' key")
    elif not isinstance(parsed_data["elements"], list):
        errors.append("parsed_data.elements must be a list")

    return errors


def validate_tag_enrichment(enrichment: Dict) -> List[str]:
    """
    Validate PageTag.enrichment JSONField structure.

    Args:
        enrichment: The enrichment dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not isinstance(enrichment, dict):
        errors.append("Tag enrichment must be a dictionary")
        return errors

    # If enrichment is empty, it's valid (not enriched yet)
    if not enrichment:
        return errors

    # Check required fields
    required_fields = ["enrichment_type", "normalized_value", "enrichment_data"]
    for field in required_fields:
        if field not in enrichment:
            errors.append(f"Tag enrichment missing required field: '{field}'")

    # Validate enrichment_data structure
    if "enrichment_data" in enrichment:
        enrich_data = enrichment["enrichment_data"]
        if not isinstance(enrich_data, dict):
            errors.append("enrichment_data must be a dictionary")
        else:
            if "id_type" not in enrich_data:
                errors.append("enrichment_data missing 'id_type'")
            if "id_value" not in enrich_data:
                errors.append("enrichment_data missing 'id_value'")

    return errors


def validate_all_jsonfields(model_instance) -> Dict[str, List[str]]:
    """
    Validate all JSONFields for a model instance.

    This is a convenience function that calls the appropriate validator
    for each JSONField in the model.

    Args:
        model_instance: The model instance to validate

    Returns:
        Dictionary mapping field names to lists of errors
        Empty dict if all valid
    """
    from twf.models import (
        Project,
        UserProfile,
        Document,
        Page,
        PageTag,
        DictionaryEntry,
        CollectionItem,
    )

    all_errors = {}

    # UserProfile
    if isinstance(model_instance, UserProfile):
        errors = validate_permissions(model_instance.permissions)
        if errors:
            all_errors["permissions"] = errors

    # Project
    elif isinstance(model_instance, Project):
        errors = validate_credentials(model_instance.conf_credentials)
        if errors:
            all_errors["conf_credentials"] = errors

        errors = validate_task_configuration(model_instance.conf_tasks)
        if errors:
            all_errors["conf_tasks"] = errors

        errors = validate_display_configuration(model_instance.conf_display)
        if errors:
            all_errors["conf_display"] = errors

    # Document
    elif isinstance(model_instance, Document):
        errors = validate_document_metadata(model_instance.metadata)
        if errors:
            all_errors["metadata"] = errors

    # Page
    elif isinstance(model_instance, Page):
        errors = validate_document_metadata(model_instance.metadata)
        if errors:
            all_errors["metadata"] = errors

        if model_instance.parsed_data:
            errors = validate_page_parsed_data(model_instance.parsed_data)
            if errors:
                all_errors["parsed_data"] = errors

    # PageTag
    elif isinstance(model_instance, PageTag):
        if model_instance.enrichment:
            errors = validate_tag_enrichment(model_instance.enrichment)
            if errors:
                all_errors["enrichment"] = errors

    return all_errors


# Management command helper
def validate_all_projects():
    """
    Validate all projects in the database.

    Returns:
        Dictionary with validation results
    """
    from twf.models import Project

    results = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "errors": []
    }

    for project in Project.objects.all():
        results["total"] += 1
        errors = validate_all_jsonfields(project)

        if errors:
            results["invalid"] += 1
            results["errors"].append({
                "project_id": project.id,
                "project_title": project.title,
                "errors": errors
            })
        else:
            results["valid"] += 1

    return results
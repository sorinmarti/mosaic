""" Utility functions for exporting data from the TWF database. """

import json
from datetime import datetime

from twf.models import Document, Page, Project

SPECIAL_KEYS = ["tag_list", "used_dicts", "data_curators", "date.today", "date.now"]
SPECIAL_KEY_CONFIG = {
    "tag_list": {
        "style": "nested",  # 'nested' or 'flat'
        "used_for": ["document"],  # 'document', 'page', 'project'
    },
    "data_curators": {
        "style": "nested",  # 'nested' or 'flat'
        "used_for": ["document"],  # 'document', 'page', 'project'
        "properties": ["name", "orcid"],
    },  # List of values to include: 'name',
    # 'orcid', 'affiliation', 'username', 'email', 'role'
}


def get_nested_value(data, key, default=None):
    """
    Retrieve a value from a nested dictionary or list using dot notation.

    Example:
    - "my.list.0.nested.item" will access data['my']['list'][0]['nested']['item']

    :param data: The dictionary, list, or object from which to extract the value.
    :param key: A dot-notated string representing the nested keys.
    :param default: The default value to return if the key is not found.
    :return: The retrieved value or the default value if key is not found.
    """
    keys = key.split(".")
    val = data
    try:
        for k in keys:
            # Check if the current level is a list and if the key is an index
            if isinstance(val, list):
                k = int(k)  # Convert key to integer to access list index
                val = val[k]
            elif isinstance(val, dict):
                val = val[k]
            else:
                val = getattr(val, k, default)
        return val
    except (KeyError, AttributeError, IndexError, ValueError, TypeError):
        return default


def get_special_value(special_key, metadata, db_object, mapping):
    """Get a special value for a document or page object."""
    object_type = None
    if isinstance(db_object, Project):
        object_type = "project"
    elif isinstance(db_object, Document):
        object_type = "document"
    elif isinstance(db_object, Page):
        object_type = "page"

    if not object_type:
        return "Special Value Not Found: invalid object type"

    print(special_key)
    print(mapping)
    if special_key == "tag_list":
        return get_tag_list(object_type, db_object, mapping)
    elif special_key == "used_dicts":
        return get_used_dicts(object_type, db_object, mapping)
    elif special_key == "data_curators":
        return get_data_curators(object_type, db_object, mapping)
    elif special_key == "date.today":
        return datetime.now().strftime("%Y-%m-%d")
    elif special_key == "date.now":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        return "Special Value Not Found"


def get_data_curators(object_type, db_object, mapping):
    """Get data curators for a document or page object."""
    config = SPECIAL_KEY_CONFIG.get("data_curators", {})
    data_curators = []
    if object_type == "document":
        data_curators = [db_object.modified_by, db_object.created_by]
        for page in db_object.pages.all():
            data_curators.extend([page.modified_by, page.created_by])
    elif object_type == "page":
        data_curators = [db_object.modified_by, db_object.created_by]
    elif object_type == "project":
        data_curators = [db_object.owner]
        for document in db_object.documents.all():
            data_curators.extend([document.modified_by, document.created_by])
            for page in document.pages.all():
                data_curators.extend([page.modified_by, page.created_by])

    data_curators = list(set(data_curators))
    data_curator_data = []
    for data_curator in data_curators:
        data = {}
        for key in config["properties"]:
            value = get_nested_value(data_curator, key, "")
            if key == "name":
                value = f"{data_curator.first_name} {data_curator.last_name}"
            elif key == "orcid":
                value = data_curator.profile.orc_id
            elif key == "affiliation":
                value = data_curator.profile.affiliation
            elif key == "username":
                key = "name"
            data[key] = value
        data_curator_data.append(data)

    return data_curator_data


def get_used_dicts(object_type, db_object, mapping):
    """Get a list of dictionaries used for a document or page object."""
    config = SPECIAL_KEY_CONFIG.get("used_dicts", {})
    return {}


def get_tag_list(object_type, db_object, mapping):
    """Get a list of tags for a document or page object."""
    config = SPECIAL_KEY_CONFIG.get("tag_list", {})
    return {}


def create_data_from_config(metadata, config, db_object=None, return_warnings=False):
    """Create a transformed dictionary from metadata using a configuration dictionary.
    :param metadata: dictionary containing metadata
    :param config: dictionary containing the transformation configuration
    :param db_object: object containing additional data
    :param return_warnings: boolean indicating whether to return warnings
    :return:  transformed dictionary, list of warnings
    """

    transformed = {}
    warnings = []

    for key, mapping in config.items():
        try:
            value_expression = mapping.get("value", "")
            empty_value = mapping.get("empty_value", "")

            # Handle nested keys and DB field references
            if value_expression.startswith("{__") and value_expression.endswith("__}"):
                # Handle DB field access like "{__tk_page_number__}"
                db_field = value_expression[3:-3]
                if db_object:
                    value = get_nested_value(db_object, db_field, empty_value)
                    if value == empty_value:
                        warnings.append(
                            f"Key '{key}' ({db_field}) missing in DB object"
                        )
                else:
                    warnings.append(f"Key '{key}' requires a DB object")
                    value = empty_value
            elif value_expression.startswith("{") and value_expression.endswith("}"):
                # Handle metadata dynamic reference like "{tags1}"
                metadata_key = value_expression[1:-1]
                if metadata_key in SPECIAL_KEYS:
                    value = get_special_value(
                        metadata_key, metadata, db_object, mapping
                    )
                else:
                    value = get_nested_value(metadata, metadata_key, empty_value)
            elif "{" in value_expression and "}" in value_expression:
                # Handle formatted strings like "p. {page}"
                try:
                    value = value_expression.format(**metadata)
                except KeyError:
                    warnings.append(f"Key '{key}' missing in metadata")
                    value = empty_value
            else:
                # Handle static values
                value = value_expression

            # Assign value to the transformed dictionary (handle nested keys)
            keys = key.split(".")
            current_level = transformed
            for i, sub_key in enumerate(keys):
                if i == len(keys) - 1:
                    current_level[sub_key] = value
                else:
                    current_level = current_level.setdefault(sub_key, {})
        except AttributeError as e:
            warnings.append(f"Error processing key '{key}': {e}")

    if return_warnings:
        return transformed, warnings
    return transformed


def create_data(db_object, return_warnings=False):
    """Create a dictionary from a database object.
    :param db_object: object to create data from
    :param return_warnings: boolean indicating whether to return warnings
    :return: dictionary, list of warnings
    """
    if isinstance(db_object, Project):
        return create_project_data(db_object, return_warnings)
    elif isinstance(db_object, Document):
        return create_document_data(db_object, return_warnings)
    elif isinstance(db_object, Page):
        return create_page_data(db_object, return_warnings)
    else:
        raise ValueError(f"Invalid object type: {db_object}")


def create_project_data(project, return_warnings=False):
    """Create a dictionary from a project object.
    :param project: Project object
    :param return_warnings: boolean indicating whether to return warnings
    :return: dictionary, list of warnings
    """
    project_export = []
    all_warnings = []
    for document in project.documents.all():
        if return_warnings:
            document_data, warnings = create_document_data(document, True)
            all_warnings.extend(warnings)
        else:
            document_data = create_document_data(document)
        project_export.append(document_data)

    if return_warnings:
        return project_export, all_warnings

    return project_export


def create_document_data(document, return_warnings=False):
    """Create a dictionary from a document object."""
    data = {**document.metadata}

    all_warnings = []
    config = document.project.get_export_configuration(
        "document_export_configuration", return_json=True
    )
    # If an empty config is returned, check if it is because the JSON could not be decoded
    if config == {}:
        try:
            str_config = document.project.get_export_configuration(
                "document_export_configuration", return_json=False
            )
            config = json.loads(str_config)
        except json.JSONDecodeError:
            all_warnings.append(
                "Invalid document export configuration: JSON could not be decoded"
            )

    if return_warnings:
        doc_export, warnings = create_data_from_config(data, config, document, True)
        all_warnings.extend(warnings)
    else:
        doc_export = create_data_from_config(data, config, document)

    doc_export["pages"] = []
    for page in document.pages.all():
        if return_warnings:
            page_data, warnings = create_page_data(page, True)
            all_warnings.extend(warnings)
        else:
            page_data = create_page_data(page)
        doc_export["pages"].append(page_data)

    if return_warnings:
        return doc_export, all_warnings
    return doc_export


def create_page_data(page, return_warnings=False):
    """Create a dictionary from a page object."""
    data = {**page.parsed_data, **page.metadata}
    all_warnings = []
    config = page.document.project.get_export_configuration("page_export_configuration")
    if config == {}:
        try:
            str_config = page.document.project.get_export_configuration(
                "page_export_configuration", return_json=False
            )
            config = json.loads(str_config)
        except json.JSONDecodeError:
            all_warnings.append(
                "Invalid page export configuration: JSON could not be decoded"
            )

    if return_warnings:
        page_export, warnings = create_data_from_config(data, config, page, True)
        warnings.extend(all_warnings)
        return page_export, warnings
    else:
        return create_data_from_config(data, config, page, False)


def flatten_dict_keys(d, parent_key="", sep="."):
    """
    Recursively flatten a dictionary and list to get keys in 'dot notation'.
    Only the first element of a list will be processed.

    :param d: The dictionary (or list) to flatten.
    :param parent_key: The base key (used in recursion).
    :param sep: The separator between keys (default is dot).
    :return: A list of keys in 'dot notation'.
    """
    keys = []
    if isinstance(d, dict):
        # Iterate through dictionary items
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                # Recurse into dictionary
                keys.extend(flatten_dict_keys(v, new_key, sep=sep))
            elif isinstance(v, list) and v:
                # Only handle the first item in the list
                list_key = f"{new_key}{sep}0"
                keys.extend(flatten_dict_keys(v[0], list_key, sep=sep))
            else:
                # Add simple key
                keys.append(new_key)
    elif isinstance(d, list) and d:
        # Only handle the first item in the list
        list_key = f"{parent_key}{sep}0"
        keys.extend(flatten_dict_keys(d[0], list_key, sep=sep))
    else:
        # Add key for simple values
        keys.append(parent_key)
    return keys

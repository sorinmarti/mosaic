import re


def parse_key_path(key_path):
    """Turns 'choices[0].message.content' into ['choices', 0, 'message', 'content']"""
    parts = []
    for part in key_path.split("."):
        matches = re.finditer(r"([^\[\]]+)|\[(\d+)\]", part)
        for match in matches:
            key, index = match.groups()
            if key:
                parts.append(key)
            elif index:
                parts.append(int(index))
    return parts


def set_nested_value(data, key_path, value):
    """
    Set a value in a nested dictionary or list structure using a dot-notation key path.

    Args:
        data: The root dictionary or list to modify
        key_path: Dot-notation path like 'choices[0].message.content'
        value: The value to set at the specified path

    Returns:
        None (modifies data in place)
    """
    keys = parse_key_path(key_path)
    ref = data
    for i, key in enumerate(keys[:-1]):
        next_key = keys[i + 1]
        if isinstance(key, int):
            while len(ref) <= key:
                ref.append({} if isinstance(next_key, str) else [])
            ref = ref[key]
        else:
            if key not in ref or not isinstance(ref[key], (dict, list)):
                ref[key] = {} if isinstance(next_key, str) else []
            ref = ref[key]
    last_key = keys[-1]
    if isinstance(last_key, int):
        while len(ref) <= last_key:
            ref.append(None)
        ref[last_key] = value
    else:
        ref[last_key] = value


def delete_nested_key(data, key_path):
    """
    Delete a key from a nested dictionary or list structure using a dot-notation key path.

    Args:
        data: The root dictionary or list to modify
        key_path: Dot-notation path like 'choices[0].message.content'

    Returns:
        None (modifies data in place, silently ignores if path doesn't exist)
    """
    keys = parse_key_path(key_path)
    ref = data
    for key in keys[:-1]:
        if isinstance(ref, list) and isinstance(key, int):
            if 0 <= key < len(ref):
                ref = ref[key]
            else:
                return
        elif isinstance(ref, dict):
            ref = ref.get(key, {})
        else:
            return
    last_key = keys[-1]
    if isinstance(ref, list) and isinstance(last_key, int):
        if 0 <= last_key < len(ref):
            ref.pop(last_key)
    elif isinstance(ref, dict):
        ref.pop(last_key, None)

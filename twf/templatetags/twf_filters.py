"""Render custom filters for the table."""

from django import template

register = template.Library()


@register.inclusion_tag("twf/tables/filter_form.html")
def twf_filter(my_twf_filter):
    """
    Render a custom filter form for the given filter.
    """
    return {"filter": my_twf_filter}


@register.filter
def add_class(field, css_class):
    """
    Add a CSS class to the given form field while preserving existing widget attributes.
    :param field:
    :param css_class:
    :return:
    """
    # Get existing widget attributes
    existing_attrs = field.field.widget.attrs.copy() if hasattr(field.field.widget, 'attrs') else {}

    # Merge existing class with new class
    existing_class = existing_attrs.get('class', '')
    if existing_class:
        existing_attrs['class'] = f"{existing_class} {css_class}"
    else:
        existing_attrs['class'] = css_class

    return field.as_widget(attrs=existing_attrs)


@register.filter
def sum_tags(pages):
    """Count the total number of tags across all pages."""
    return sum(page.tags.count() for page in pages)


@register.filter
def get_tag_types(pages):
    """Get a list of unique tag types across all pages."""
    tag_types = set()
    for page in pages:
        for tag in page.tags.all():
            if tag.variation_type:
                tag_types.add(tag.variation_type)
    return sorted(tag_types)


@register.filter
def truncate_text(text, length=50):
    """Truncate text to the specified length and add ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[:length] + "..."


@register.filter
def highlight_matches(text, search_term):
    """Highlight search term matches in text."""
    if not text or not search_term:
        return text

    # Escape HTML special characters to prevent injection
    from django.utils.html import escape

    text = escape(text)
    search_term = escape(search_term)

    # Replace matches with highlighted version
    import re

    pattern = re.compile(re.escape(search_term), re.IGNORECASE)
    highlighted = pattern.sub(r"<mark>\g<0></mark>", text)

    return highlighted


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key.

    Args:
        dictionary: Dictionary to retrieve value from
        key: Key to look up in the dictionary

    Returns:
        The value associated with the key, or None if key not found
    """
    return dictionary.get(key)


@register.filter
def replace(value, arg):
    """
    Replace occurrences of a substring in a string value.

    Argument format: 'old:new' where ':' separates the old and new values.
    Example: {{ value|replace:"T: " }} replaces 'T' with ' '.

    Args:
        value: The string to perform replacement on
        arg: Replacement spec in 'old:new' format

    Returns:
        String with replacements applied
    """
    parts = str(arg).split(':', 1)
    old = parts[0]
    new = parts[1] if len(parts) > 1 else ''
    return str(value).replace(old, new)


@register.filter
def highlight_tag_in_context(tag):
    """
    Highlight a tag within its line context using PageTag's built-in method.

    Uses the new explicit positional fields (offset_in_line, length, line_text)
    from simple-alto-parser v0.0.22+ for accurate highlighting.

    Args:
        tag: A PageTag instance

    Returns:
        HTML string with the tag highlighted in its line context
    """
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    # Use PageTag's built-in get_highlighted_context() method
    # This uses the explicit positional fields for accurate highlighting
    if tag.line_text and tag.offset_in_line >= 0:
        return mark_safe(tag.get_highlighted_context(context_chars=100))

    # Fallback for old data without explicit fields: search through parsed_data
    page = tag.page
    if not hasattr(page, "parsed_data") or not page.parsed_data:
        return escape(tag.variation)

    # Search for the line containing this tag variation
    variation_stripped = tag.variation.strip()
    target_line = None

    for element in page.parsed_data.get("elements", []):
        text_lines = element.get("element_data", {}).get("text_lines", [])
        for line in text_lines:
            if variation_stripped in line:
                target_line = line
                break
        if target_line:
            break

    if not target_line:
        # Can't find the line - just return the variation
        return escape(tag.variation)

    # Find the position of the variation in the line
    pos = target_line.find(variation_stripped)
    if pos < 0:
        # Shouldn't happen but handle it
        return escape(target_line)

    # Extract and highlight
    before = escape(target_line[:pos])
    highlighted = escape(variation_stripped)
    after = escape(target_line[pos + len(variation_stripped) :])

    return mark_safe(
        f'{before}<mark style="background-color: #ffc107; font-weight: bold; '
        f'padding: 2px 4px;">{highlighted}</mark>{after}'
    )


@register.filter
def mark_tags_inline(page):
    """
    Mark tags inline within the text using offset/length from parsed_data.

    Uses the custom_list data that's already in parsed_data - much simpler!

    Args:
        page: A Page model instance with parsed_data

    Returns:
        A list of blocks with marked-up text lines
    """
    import re
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    if not hasattr(page, "parsed_data") or not page.parsed_data:
        return []

    # Get all tags for this page to look up dictionary entries
    tags_dict = {}
    for tag in page.tags.all():
        # Index by (element_id, type, variation) for lookup
        key = (
            tag.additional_information.get("line_id", ""),
            tag.variation_type,
            tag.variation,
        )
        tags_dict[key] = {
            "has_entry": bool(tag.dictionary_entry),
            "entry_label": str(tag.dictionary_entry) if tag.dictionary_entry else None,
            "is_parked": tag.is_parked,
        }

    marked_blocks = []
    for block in page.parsed_data.get("elements", []):
        element_id = block.get("id", "")
        element_data = block.get("element_data", {})

        marked_block = {
            "structure_type": element_data.get("custom_structure", {})
            .get("structure", {})
            .get("type", "Unknown"),
            "text_lines": [],
        }

        text_lines = element_data.get("text_lines", [])
        custom_list = element_data.get("custom_list", [])

        # Process each line with its corresponding custom_list entry
        for idx, line_text in enumerate(text_lines):
            if idx < len(custom_list):
                custom_str = custom_list[idx]
                # Parse tags from custom string like "readingOrder {index:0;} person {offset:20; length:14;}"
                tags = _parse_tags_from_custom_string(custom_str, element_id, tags_dict)

                if tags:
                    # IMPORTANT: offsets in custom_list are relative to TRIMMED line text
                    # But text_lines preserves the original formatting with leading spaces
                    line_text_trimmed = line_text.lstrip()
                    leading_space_count = len(line_text) - len(line_text_trimmed)

                    # Extract actual text from TRIMMED line and try to match with database
                    enriched_tags = []
                    for tag in tags:
                        offset = tag["offset"]
                        length = tag["length"]

                        # Extract from trimmed text (where offsets are based)
                        if offset >= 0 and offset + length <= len(line_text_trimmed):
                            variation = line_text_trimmed[offset : offset + length]
                            tag["variation"] = variation

                            # Adjust offset for markup on original line_text with leading spaces
                            tag["offset"] = offset + leading_space_count

                            # Try to find matching database tag (strip for matching)
                            variation_stripped = variation.strip()
                            db_key = (
                                element_id,
                                tag["variation_type"],
                                variation_stripped,
                            )
                            if db_key in tags_dict:
                                db_info = tags_dict[db_key]
                                tag["has_entry"] = db_info["has_entry"]
                                tag["entry_label"] = db_info["entry_label"]
                                tag["is_parked"] = db_info["is_parked"]

                        enriched_tags.append(tag)

                    marked_text = _insert_tag_markup(line_text, enriched_tags)
                else:
                    marked_text = escape(line_text)
            else:
                marked_text = escape(line_text)

            marked_block["text_lines"].append(mark_safe(marked_text))

        marked_blocks.append(marked_block)

    return marked_blocks


def _parse_tags_from_custom_string(custom_str, element_id, tags_dict):
    """
    Parse tag information from custom string like:
    "readingOrder {index:0;} person {offset:20; length:14;} person {offset:35; length:4;}"

    Returns list of tag dicts with offset, length, type, and database info.
    """
    import re

    tags = []
    # Pattern to match tag_type {offset:N; length:M;}
    pattern = r"(\w+)\s+\{([^}]+)\}"

    for match in re.finditer(pattern, custom_str):
        tag_type = match.group(1)
        attrs_str = match.group(2)

        # Skip readingOrder tags
        if tag_type == "readingOrder":
            continue

        # Parse attributes
        offset = None
        length = None
        for attr in attrs_str.split(";"):
            attr = attr.strip()
            if ":" in attr:
                key, value = attr.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "offset":
                    offset = int(value)
                elif key == "length":
                    length = int(value)

        if offset is not None and length is not None and length > 0:
            tag_info = {
                "offset": offset,
                "length": length,
                "variation_type": tag_type,
                "has_entry": False,
                "entry_label": None,
                "is_parked": False,
                "variation": "",  # Will be extracted from text
            }

            tags.append(tag_info)

    # Sort by offset
    tags.sort(key=lambda t: t["offset"])
    return tags


def _insert_tag_markup(text, tags):
    """
    Insert HTML markup into text at positions specified by tags.

    Args:
        text: The original text line
        tags: List of tag dictionaries with offset, length, and other properties

    Returns:
        HTML string with tags marked up
    """
    from django.utils.html import escape

    if not tags:
        return escape(text)

    # We need to work with the original text for offsets,
    # then escape individual segments
    result_parts = []
    last_pos = 0

    # Process tags in order
    for tag in tags:
        offset = tag["offset"]
        length = tag["length"]

        # Handle overlapping or invalid offsets
        if offset < last_pos:
            continue

        # Determine CSS class based on tag properties
        if tag["is_parked"]:
            css_class = "tag-parked"
        elif tag["has_entry"]:
            css_class = "tag-resolved"
        else:
            css_class = "tag-unresolved"

        # Build tooltip with entry label and type if available
        tooltip_parts = []
        if tag["entry_label"]:
            tooltip_parts.append(f"{tag['variation_type']}: {tag['entry_label']}")
        else:
            tooltip_parts.append(f"{tag['variation_type']}: {tag['variation']}")
        title = " | ".join(tooltip_parts)

        # Add text before this tag
        if offset > last_pos:
            result_parts.append(escape(text[last_pos:offset]))

        # Add the tagged segment
        tagged_text = escape(text[offset : offset + length])
        result_parts.append(
            f'<span class="inline-tag {css_class}" '
            f'title="{escape(title)}">{tagged_text}</span>'
        )

        last_pos = offset + length

    # Add any remaining text after the last tag
    if last_pos < len(text):
        result_parts.append(escape(text[last_pos:]))

    return "".join(result_parts)

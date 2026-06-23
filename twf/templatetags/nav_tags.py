"""Custom template tags for the twf app."""

import hashlib
import json

import markdown as md
from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def value_to_color(value):
    """Converts a numerical value from 50 to 100 into a color between red and green."""
    if value < 50:
        return "#FF0000"
    if value > 100:
        return "#00FF00"

    # Calculate green component: Scale value from 50-100 to 0-255
    green = int((value - 50) / 50 * 255)
    # Red component decreases as value increases
    red = 255 - green
    blue = 0  # No blue component needed

    return f"#{red:02x}{green:02x}{blue:02x}"


@register.simple_tag
def any_value_to_color(value):
    """Converts a numerical value to a color"""
    hash_object = hashlib.md5(str(value).encode())
    hex_hash = hash_object.hexdigest()
    color_code = "#" + hex_hash[:6]
    return color_code


@register.filter
def limit_to(value, arg):
    """Limit a list to `arg` elements."""
    return value[:arg]


@register.filter(name="markdown")
def markdown_format(text):
    """Converts markdown text to HTML."""
    modified_text = text.replace("\n", "\n\n")
    return mark_safe(md.markdown(modified_text, extensions=["extra", "smarty"]))


@register.filter(name="nl2br")
def nl2br(value):
    """Converts newlines into <br> tags."""
    escaped_value = conditional_escape(value)
    return mark_safe(escaped_value.replace("\n", "<br>"))


@register.filter(name="sp2nbsp")
def sp2nbsp(value):
    """Converts spaces into non-breaking spaces."""
    escaped_value = conditional_escape(value)
    return mark_safe(escaped_value.replace(" ", "&nbsp;"))


@register.filter(name="pretty_json")
def pretty_json(value):
    """Pretty-formats a json value."""
    try:
        # If the value is a string, attempt to parse it as JSON
        if isinstance(value, str):
            value = json.loads(value)
        # Pretty-format the JSON data with an indent of 4 spaces
        return sp2nbsp(nl2br(json.dumps(value, indent=4)))
    except (TypeError, ValueError):
        # Return the original value if it's not JSON-serializable
        return value


@register.filter(name="type_check")
def type_check(value):
    """Returns the type of the value."""
    return type(value).__name__

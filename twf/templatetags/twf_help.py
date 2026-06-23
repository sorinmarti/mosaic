from django import template

register = template.Library()


@register.simple_tag
def help_url(url):
    """Custom filter to check if a profile has a specific permission."""
    return "https://rise-test1.philhist.unibas.ch/docs/" + url

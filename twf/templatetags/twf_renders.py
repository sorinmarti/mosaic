from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def render_metadata(obj_with_metadata):
    """Render metadata with outermost keys as tabs."""

    if obj_with_metadata.metadata is None:
        return mark_safe("<p><em>No metadata available</em></p>")

    if not isinstance(obj_with_metadata.metadata, dict):
        return mark_safe("<p><em>Invalid metadata format</em></p>")

    tab_headers = ""
    tab_contents = ""
    first = True
    obj_id = obj_with_metadata.id
    obj_type = obj_with_metadata.__class__.__name__.lower()

    # Create unique ID prefix for this object's metadata tabs
    unique_prefix = f"{obj_type}-{obj_id}"

    for key, value in obj_with_metadata.metadata.items():
        active_class = "active" if first else ""
        show_class = "show active" if first else ""

        # Create unique IDs for tabs using the unique prefix
        tab_id = f"{unique_prefix}-{key}-tab"
        pane_id = f"{unique_prefix}-{key}"

        tab_headers += "<li class='nav-item' role='presentation'>"
        tab_headers += (f"<button class='nav-link {active_class}' id='{tab_id}' "
                        f"data-bs-toggle='tab' data-bs-target='#{pane_id}' type='button' "
                        f"role='tab' aria-controls='{pane_id}' aria-selected='true'>{key}</button>")
        tab_headers += f"""<button class='btn btn-sm btn-circle btn-delete show-danger-modal ms-1'
                                  title='Delete entire "{key}" section'
                                  data-message='Are you sure you want to delete 
                                  the entire metadata section "{key}"?'
                                  data-start-url='/metadata/delete/{obj_type}/{obj_id}/{key}/'
                                  data-delete-base-key='{key}'>
                              <i class='fas fa-trash'></i>
                          </button>"""
        tab_headers += "</li>"

        tab_contents += (f"<div class='tab-pane fade {show_class}' id='{pane_id}' "
                         f"role='tabpanel' aria-labelledby='{tab_id}'>")
        tab_contents += f"{render_metadata_content(key, obj_type, obj_id, value)}"
        tab_contents += "</div>"

        first = False

    html_render = f"""
    <ul class='nav nav-tabs' id='metadataTabs-{unique_prefix}' role='tablist'>
        {tab_headers}
    </ul>
    <div class='tab-content' id='metadataTabsContent-{unique_prefix}'>
        {tab_contents}
    </div>
    """

    return mark_safe(html_render)


def render_metadata_content(base_key, obj_type, obj_id, metadata, parent_key=None):
    """Helper function to recursively render metadata content with edit/delete options."""

    if isinstance(metadata, dict):
        html_render = "<ul class='metadata-list'>"
        for key, value in metadata.items():
            edit_button = ""
            full_key = f"{parent_key}.{key}" if parent_key else key

            if not isinstance(value, dict) and not isinstance(value, list):
                edit_button = f"""<button class='btn btn-sm btn-circle btn-edit' 
                onclick='editMetadata("{base_key}", "{obj_type}", "{obj_id}", "{full_key}")' title='Edit'>
                    <i class="fas fa-edit"></i>
                </button>"""

            html_render += f"""
            <li id='metadata-{full_key}' class='metadata-item'>
                {edit_button}
                <button class="btn btn-sm btn-circle btn-delete show-danger-modal"
                        data-message="Are you sure you want to delete the key '{full_key}'?"
                        data-start-url="/metadata/delete/{obj_type}/{obj_id}/{base_key}/"
                        data-delete-md-key="{full_key}">
                    <i class="fas fa-trash"></i>
                </button>
                <strong>{key}:</strong> 
                <span id="metadata-value-{full_key}">
                  {render_metadata_content(base_key, obj_type, obj_id, value, full_key)}
                </span>
            </li>
            """
        html_render += "</ul>"

    elif isinstance(metadata, list):
        html_render = "<ul class='metadata-list'>"
        for index, item in enumerate(metadata):
            full_key = f"{parent_key}[{index}]" if parent_key else str(index)
            html_render += f"""
            <li id='metadata-{full_key}' class='metadata-item'>
                {render_metadata_content(base_key, obj_type, obj_id, item, full_key)}
            </li>
            """
        html_render += "</ul>"

    else:
        html_render = f"""
        <span id='metadata-{parent_key}'>{metadata}</span>
        """

    return html_render

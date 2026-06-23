import json
from crispy_forms.utils import flatatt
from django import forms
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe


class JSONAnnotationsWidget(forms.Widget):
    """
    A custom Django form widget to display and manage JSON annotations.
    It renders existing annotations with options to remove or split them,
    and includes a hidden textarea to store the JSON data.
    """
    template_name = None

    def __init__(self, attrs=None):
        default_attrs = {"class": "json-annotations-widget"}
        if attrs:
            default_attrs.update(attrs)
        super(JSONAnnotationsWidget, self).__init__(attrs=default_attrs)

    def get_context(self, name, value, attrs):
        context = super(JSONAnnotationsWidget, self).get_context(name, value, attrs)
        # You can add extra context variables here if needed
        return context

    def value_from_datadict(self, data, files, name):
        """
        Retrieves the JSON data submitted in the hidden input field.
        """
        json_data = data.get(name, "[]")  # Default to an empty list if not provided
        try:
            json_data = json.loads(json_data)  # Parse the JSON data
            json_data = {"annotations": json_data}
            return json_data
        except json.JSONDecodeError:
            return {"annotations": []}

    def render(self, name, value, attrs=None, renderer=None):
        if not value:
            value = []
        if isinstance(value, str):
            value = json.loads(value)

        if "annotations" in value:
            value = value["annotations"]

        annotations_html = ""
        item_pk = self.attrs.get("item_pk", 0)
        for index, annotation in enumerate(value):
            delete_annotation_url = reverse_lazy(
                "twf:collection_item_delete_annotation",
                kwargs={"pk": item_pk, "index": index + 1},
            )
            if "redirect_view" in self.attrs:
                delete_annotation_url += (
                    f'?redirect_to_view={self.attrs["redirect_view"]}'
                )

            split_item_url = reverse_lazy(
                "twf:collection_item_split", kwargs={"pk": item_pk, "index": index + 1}
            )
            if "redirect_view" in self.attrs:
                split_item_url += f'?redirect_to_view={self.attrs["redirect_view"]}'

            annotations_html += f"""
            <div class="annotation-item" data-index="{index}">
                <p><img src="{annotation.get('url', '')}" alt="Annotation Image"></p>
                <span class="annotation-text">{annotation.get('text', '')}</span>
                <small>({annotation.get('type', 'unknown')})</small>
                <a href="{delete_annotation_url}" class="btn btn-danger btn-sm remove-annotation">Remove</a>
            </div>
            """

            # Add split bar after each annotation except the last one
            if index < len(value) - 1:

                annotations_html += f"""
                <div class="split-bar">
                    <a href="{split_item_url}" class="btn btn-sm split-button">Split here and create new item</a>
                </div>
                """

        if len(value) == 0:
            annotations_html = "<p>No annotations found.</p>"

        final_attrs = self.build_attrs(attrs, {"name": name})
        html = f"""
        <div class="json-annotations-widget" {flatatt(final_attrs)}>
            <div id="annotations-container">
                {annotations_html}
            </div>
            <!-- Single hidden textarea for the entire annotations JSON -->
            <textarea name="{name}" id="annotations-json" hidden>{json.dumps(value)}</textarea>
        </div>
        """
        return mark_safe(html)

    class Media:
        css = {"all": ("twf/css/json_annotations_widget.css",)}
        js = ("twf/js/json_annotations_widget.js",)

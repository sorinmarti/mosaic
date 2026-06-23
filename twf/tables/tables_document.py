# pylint: disable=too-few-public-methods
"""This module contains the tables for displaying documents and dictionary entries."""
import django_tables2 as tables
from django.utils.html import format_html_join, format_html
from twf.models import Document

class DocumentTable(tables.Table):
    id = tables.Column(accessor='document_id', verbose_name="ID", orderable=True)
    num_pages = tables.Column(verbose_name="Pages", empty_values=[])
    num_tags = tables.Column(verbose_name="Tags", empty_values=[])
    num_blocks = tables.Column(verbose_name="Blocks", empty_values=[])
    title_metadata = tables.Column(verbose_name="Title / Metadata", orderable=False, empty_values=[])
    status = tables.Column(verbose_name="Status", orderable=True, empty_values=[])
    actions = tables.TemplateColumn(
        verbose_name='Options',
        template_code="""
        <a href="{% url 'twf:view_document' record.pk %}" class="btn btn-sm btn-dark" data-bs-toggle="tooltip" data-bs-placement="bottom" title="View Document Details"><i class="fa-solid fa-eye"></i></a>
        <a href="{% url 'twf:view_document' record.pk %}" class="btn btn-sm btn-dark" data-bs-toggle="tooltip" data-bs-placement="bottom" title="Edit Document"><i class="fa-solid fa-pen-to-square"></i></a>
        <a href="{{ record.get_transkribus_url }}" class="btn btn-sm btn-ext" target="_blank" data-bs-toggle="tooltip" data-bs-placement="bottom" title="View Document on Transkribus"><i class="fa-solid fa-scroll"></i></a>
        <a href="{% url 'twf:view_document' record.pk %}" class="btn btn-sm btn-danger" data-bs-toggle="tooltip" data-bs-placement="bottom" title="Delete Document"><i class="fa-solid fa-trash-can"></i></a>
        """,
        orderable=False
    )

    def render_num_pages(self, record):
        return record.pages.count()

    def render_num_tags(self, record):
        tag_types = set()
        for page in record.pages.all():
            for tag in page.tags.all():
                if tag.variation_type:
                    tag_types.add(tag.variation_type)

        badges = format_html_join(
            '',
            '<span class="badge-table">{}</span>',
            ((tt,) for tt in sorted(tag_types))
        )

        tag_count = sum(p.num_tags for p in record.pages.all())
        return format_html('<strong>{}</strong><br>{}', tag_count, badges)

    def render_num_blocks(self, record):
        structure_types = set()
        for p in record.pages.all():
            elements = p.parsed_data.get('elements', [])
            for element in elements:
                if "structure" in element['element_data']['custom_structure']:
                    if "type" in element['element_data']['custom_structure']['structure']:
                        structure_types.add(element['element_data']['custom_structure']['structure']['type'])

        badges = format_html_join(
            '',
            '<span class="badge-table">{}</span>',
            ((st,) for st in sorted(structure_types))
        )

        block_count = sum(len(p.parsed_data.get('elements', [])) for p in record.pages.all())
        return format_html('<strong>{}</strong><br>{}', block_count, badges)

    def render_title_metadata(self, record):
        title = record.title or "N/A"

        metadata_keys = record.metadata.keys() if isinstance(record.metadata, dict) else []

        badges = format_html_join(
            '',
            '<span class="badge-table">{}</span>',
            ((key,) for key in metadata_keys)
        )

        return format_html("<strong>{}</strong><br>{}", title, badges)

    def render_status(self, record):
        """Render the document status with a colored badge."""
        status = record.status
        status_display = record.get_status_display()

        # Define badge colors based on status
        badge_class = {
            'open': 'bg-secondary',
            'needs_tk_work': 'bg-warning',
            'reviewed': 'bg-success',
            'irrelevant': 'bg-danger',  # Legacy status
        }.get(status, 'bg-secondary')

        # Add additional indicators
        indicators = []
        if record.is_parked:
            indicators.append('<span class="badge bg-info" title="Parked">⏸</span>')
        if record.is_ignored:
            indicators.append('<span class="badge bg-dark" title="Ignored">✕</span>')

        indicators_html = ' '.join(indicators)

        return format_html(
            '<span class="badge {}">{}</span> {}',
            badge_class,
            status_display,
            indicators_html
        )

    class Meta:
        model = Document
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "title_metadata", "status", "num_pages", "num_tags", "num_blocks", "actions")

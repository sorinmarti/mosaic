# pylint: disable=too-few-public-methods
"""This module contains the tables for displaying documents and dictionary entries."""
import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from twf.models import DictionaryEntry, Dictionary, Variation, PageTag, Document


class DictionaryTable(tables.Table):
    """
    Table for displaying dictionaries.
    """
    label = tables.Column(verbose_name="Dictionary", attrs={"td": {"class": "fw-bold"}})
    type = tables.Column(verbose_name="Type")

    information = tables.Column(
        empty_values=(), verbose_name="Information", orderable=False
    )
    options = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    class Meta:
        """Metaclass for the DictionaryTable."""
        model = Dictionary
        fields = ("label", "type")
        attrs = {"class": "table table-striped table-hover table-sm"}

    def render_label(self, value, record):
        """
        Render the dictionary label with metadata.

        Args:
            value: Dictionary label
            record: Dictionary model instance

        Returns:
            SafeString: Formatted HTML with label, ID, and modification info
        """
        modified = record.modified_at.strftime("%Y-%m-%d %H:%M")
        return format_html(
            '{}<br><span class="text-muted small">ID: {}<br>{}, {}</span>',
            value,
            record.id,
            record.modified_by or "—",
            modified,
        )

    def render_information(self, record):
        """
        Render information column with entry and variation counts.

        Args:
            record: Dictionary model instance

        Returns:
            SafeString: Formatted HTML with statistics
        """
        entry_count = record.entries.count()
        variation_count = sum(e.variations.count() for e in record.entries.all())
        return format_html(
            '<span class="small">Entries: {}<br>Variations: {}</span>',
            entry_count,
            variation_count,
        )

    def render_options(self, record):
        """
        Render action buttons for viewing and editing the dictionary.

        Args:
            record: Dictionary model instance

        Returns:
            SafeString: Formatted HTML with action buttons
        """
        return format_html(
            "{} {}",
            format_html(
                '<a href="{}" class="btn btn-sm btn-dark me-1" title="View">'
                '<i class="fa fa-eye"></i></a>',
                reverse("twf:dictionaries_view", args=[record.pk]),
            ),
            format_html(
                '<a href="{}" class="btn btn-sm btn-dark me-1" title="Edit">'
                '<i class="fa fa-pen"></i></a>',
                reverse("twf:dictionaries_edit", args=[record.pk]),
            ),
        )


class DictionaryAddTable(DictionaryTable):
    """Table for displaying dictionaries to add to a project."""

    class Meta:
        """
        Metaclass for the DictionaryAddTable.
        """
        model = Dictionary
        fields = ("label", "type")
        attrs = {"class": "table table-striped table-hover table-sm"}

    def render_options(self, record):
        """
        Render action button for adding the dictionary to a project.
        Args:
            record: Dictionary model instance
        Returns:
            SafeString: Formatted HTML with add button
        """
        return format_html(
            "{}",
            format_html(
                '<a href="{}" class="btn btn-sm btn-dark me-1" title="Add">'
                '<i class="fa fa-plus"></i></a>',
                reverse("twf:dictionaries_add_to_project", args=[record.pk]),
            ),
        )


class DictionaryEntryTable(tables.Table):
    """Table for displaying dictionary entries."""

    label = tables.Column(verbose_name="Entry Label")
    variations = tables.Column(verbose_name="Variations", orderable=False)
    metadata = tables.Column(verbose_name="Normalization Data", orderable=False)
    review_status = tables.Column(verbose_name="Review", orderable=True)
    modified_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Modified")
    actions = tables.Column(empty_values=(), verbose_name="Actions", orderable=False)

    class Meta:
        """Meta class for the DictionaryEntryTable."""

        model = DictionaryEntry
        template_name = "django_tables2/bootstrap4.html"
        fields = ("label", "variations", "metadata", "review_status", "modified_at")
        attrs = {"class": "table table-striped table-hover"}

    def render_variations(self, record):
        """Renders the variations column with badges for each variation."""
        variations = record.variations.all()
        if not variations:
            return format_html('<span class="text-muted">{}</span>', "No variations")

        html = ""
        for var in variations[:5]:  # Limit to first 5 variations to avoid overflow
            html += format_html(
                '<span class="badge bg-secondary me-1 mb-1">{}</span>', var.variation
            )

        # Show count if there are more variations
        if variations.count() > 5:
            html += format_html(
                '<span class="badge bg-info">+{} more</span>', variations.count() - 5
            )

        return mark_safe(html)

    def render_metadata(self, record):
        """Renders the metadata column with truncated content and status badge."""
        if not record.metadata:
            return format_html('<span class="badge bg-warning">{}</span>', "No data")

        # Show a success badge for entries with metadata
        status_badge = format_html('<span class="badge bg-success mb-1">{}</span>', "Normalized")

        # Extract key information from metadata
        metadata_info = ""
        if "preferred_name" in record.metadata:
            metadata_info += format_html(
                "<strong>Name:</strong> {}<br>", record.metadata["preferred_name"]
            )
        if "id" in record.metadata:
            metadata_info += format_html(
                "<strong>ID:</strong> {}<br>", record.metadata["id"]
            )
        if "url" in record.metadata:
            metadata_info += format_html(
                '<a href="{}" target="_blank" class="small">Authority Link</a>',
                record.metadata["url"],
            )

        # If we couldn't extract specific fields, show truncated version
        if not metadata_info:
            metadata_str = str(record.metadata)
            if len(metadata_str) > 80:
                metadata_str = metadata_str[:77] + "..."

            metadata_info = format_html('<span class="small">{}</span>', metadata_str)

        return format_html("{}<br>{}", status_badge, metadata_info)

    def render_label(self, value, record):
        """Renders the label column with a link to the entry view."""
        from django.urls import reverse

        return format_html(
            '<a href="{}" class="fw-bold">{}</a><br>'
            '<span class="small text-muted">ID: {}</span>',
            reverse("twf:dictionaries_entry_view", args=[record.pk]),
            value,
            record.id,
        )

    def render_review_status(self, record):
        """Renders the review_status field as a coloured badge."""
        if record.is_parked:
            return format_html('<span class="badge bg-warning text-dark">{}</span>', "Parked")
        if record.review_status == "reviewed":
            return format_html('<span class="badge bg-success">{}</span>', "Reviewed")
        return format_html('<span class="badge bg-secondary">{}</span>', "Pending")

    def render_modified_at(self, value, record):
        """Renders the modified date with user information."""
        return format_html(
            '{}<br><span class="small text-muted">by {}</span>',
            value,
            record.modified_by or "—",
        )

    def render_actions(self, record):
        """Renders the actions column with buttons and dropdown."""
        from django.urls import reverse

        view_url = reverse("twf:dictionaries_entry_view", args=[record.pk])
        edit_url = reverse("twf:dictionaries_entry_edit", args=[record.pk])
        delete_url = reverse("twf:dictionaries_entry_delete", args=[record.pk])

        # Create dropdown menu for actions
        return format_html(
            '<div class="btn-group">'
            '<a href="{}" class="btn btn-sm btn-dark"><i class="fa fa-eye"></i></a>'
            '<a href="{}" class="btn btn-sm btn-secondary"><i class="fa fa-pencil"></i></a>'
            '<button type="button" class="btn btn-sm btn-dark dropdown-toggle dropdown-toggle-split" '
            'data-bs-toggle="dropdown" aria-expanded="false">'
            '<span class="visually-hidden">Toggle Dropdown</span>'
            "</button>"
            '<ul class="dropdown-menu dropdown-menu-end">'
            '<a class="dropdown-item" href="{}"><i class="fa fa-eye"></i> View Details</a>'
            '<a class="dropdown-item" href="{}"><i class="fa fa-pencil"></i> Edit Entry</a>'
            '<div class="dropdown-divider"></div>'
            '<a class="dropdown-item text-danger show-danger-modal" href="#" '
            'data-redirect-url="{}" '
            'data-message="Are you sure you want to delete this dictionary entry? This cannot be undone.">'
            '<i class="fa fa-trash"></i> Delete Entry</a>'
            "</ul>"
            "</div>",
            view_url,
            edit_url,
            view_url,
            edit_url,
            delete_url,
        )


class DictionaryEntryVariationTable(tables.Table):
    """Table for displaying dictionary entry variations."""

    information = tables.Column(accessor="id", verbose_name="Usages", orderable=False)
    options = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)

    def render_information(self, value, record):
        """Renders the information column with usage statistics."""
        from django.urls import reverse

        variation_usage_count = PageTag.objects.filter(
            page__document__project=self.project, variation=record.variation
        ).count()

        documents = Document.objects.filter(
            project=self.project, pages__tags__variation=record.variation
        ).distinct()

        # Generate document links using reverse()
        document_links = " | ".join(
            f'<a href="{reverse("twf:view_document", args=[doc.pk])}">{doc.title or doc.document_id}</a>'
            for doc in documents
        )

        # Truncate document links if they're too long
        if len(document_links) > 1000:
            # This is a simplification; in real life we might want to keep complete links
            truncated_links = "Multiple documents (too much to display)"
            return format_html(
                '<span title="{}">Usages: {}<br/>Documents: {}</span>',
                document_links,
                variation_usage_count,
                truncated_links,
            )

        return format_html(
            "Usages: {}<br/>Documents: {}",
            variation_usage_count,
            mark_safe(document_links) if document_links else "None",
        )

    def render_options(self, record):
        """Renders the options column with delete button."""
        from django.urls import reverse

        delete_url = reverse("twf:dictionaries_delete_variation", args=[record.pk])

        return format_html(
            '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
            'data-redirect-url="{}" '
            'data-message="Are you sure you want to delete this variation? '
            'Any tags using this variation will be unlinked." '
            'title="Delete"><i class="fa fa-trash"></i></a>',
            delete_url,
        )

    class Meta:
        """Meta class for the DictionaryEntryVariationTable."""

        model = Variation
        template_name = "django_tables2/bootstrap.html"
        fields = ("variation",)
        attrs = {"class": "table table-striped table-hover table-sm"}

# pylint: disable=too-few-public-methods
"""Table classes for displaying tags."""
import django_tables2 as tables
from django.urls import reverse_lazy
from django.utils.html import format_html
from twf.models import PageTag


class TagTable(tables.Table):
    """
    Table for displaying tags associated with pages.
    """
    variation = tables.Column(
        verbose_name="Page Tag", attrs={"td": {"class": "fw-bold"}}
    )
    variation_type = tables.Column(verbose_name="Type")
    status = tables.Column(
        verbose_name="Status",
        orderable=True,
        empty_values=(),
        order_by=("is_reserved", "is_parked", "dictionary_entry"),
        attrs={"th": {"class": "text-center"}, "td": {"class": "text-center"}},
    )
    entry = tables.Column(
        accessor="dictionary_entry", verbose_name="Entry/Enrichment", empty_values=()
    )
    options = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    def render_status(self, value, record):
        """
        Render comprehensive status badges for a tag.

        Shows: Reserved, Parked, Processed, or Unresolved status

        Args:
            value: Not used (column has no direct accessor)
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML badges showing tag status
        """
        from django.utils.safestring import mark_safe

        badges = []

        # Check if reserved (highest priority)
        if record.is_reserved:
            badges.append(
                '<span class="badge bg-info" data-bs-toggle="tooltip" '
                'title="Reserved in active workflow">'
                '<i class="fa fa-lock me-1"></i>Reserved</span>'
            )

        # Check if parked
        if record.is_parked:
            badges.append(
                '<span class="badge bg-warning text-dark" data-bs-toggle="tooltip" '
                'title="Parked for later processing">'
                '<i class="fa fa-box-archive me-1"></i>Parked</span>'
            )

        # Check if processed (has dictionary entry or enrichment)
        if record.dictionary_entry or record.tag_enrichment_entry or record.date_variation_entry:
            badges.append(
                '<span class="badge bg-success" data-bs-toggle="tooltip" '
                'title="Processed (grouped or enriched)">'
                '<i class="fa fa-check-circle me-1"></i>Processed</span>'
            )
        elif not record.is_parked:
            # Unresolved (not parked and not processed)
            badges.append(
                '<span class="badge bg-danger" data-bs-toggle="tooltip" '
                'title="Unresolved - needs processing">'
                '<i class="fa fa-exclamation-circle me-1"></i>Unresolved</span>'
            )

        return mark_safe(" ".join(badges) if badges else "-")

    class Meta:
        """
        Table metadata configuration.
        """
        model = PageTag
        fields = ("variation", "variation_type", "entry")
        template_name = "django_tables2/bootstrap4.html"
        attrs = {"class": "table table-striped table-hover"}

    def render_entry(self, value, record):
        """
        Render dictionary entry, enrichment data, or date normalization.

        Args:
            value: Dictionary entry value
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML showing entry or enrichment information
        """
        # Priority: enrichment > dictionary entry > date variation
        if record.tag_enrichment_entry:
            enrichment = record.tag_enrichment_entry
            return format_html(
                '<span class="badge bg-success me-1" data-bs-toggle="tooltip" '
                'title="Enrichment type: {}">'
                '<i class="fa fa-plus-circle"></i> {}</span>'
                '<span class="small text-muted">{}</span>',
                enrichment.enrichment_type,
                enrichment.enrichment_type.upper(),
                enrichment.normalized_value[:40] + "..." if len(enrichment.normalized_value) > 40 else enrichment.normalized_value
            )
        elif record.dictionary_entry:
            return format_html(
                '<span class="badge bg-primary me-1" data-bs-toggle="tooltip" '
                'title="Dictionary: {}">'
                '<i class="fa fa-book"></i></span>'
                '{}',
                record.dictionary_entry.dictionary.label if record.dictionary_entry.dictionary else "Unknown",
                record.dictionary_entry.label
            )
        elif record.date_variation_entry:
            return format_html(
                '<span class="badge bg-info me-1" data-bs-toggle="tooltip" '
                'title="Date normalization (legacy)">'
                '<i class="fa fa-calendar"></i></span>'
                '<code class="small">{}</code>',
                record.date_variation_entry.edtf_of_normalized_variation
            )
        return "-"

    def render_options(self, record):
        """
        Render action buttons for tag operations.

        Args:
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML with action buttons
        """
        from django.utils.safestring import mark_safe

        detail_button = format_html(
            '<a href="{}" class="btn btn-sm btn-primary me-1"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="View tag details">'
            '<i class="fa fa-eye"></i></a>',
            reverse_lazy("twf:tags_detail", kwargs={"pk": record.pk}),
        )

        park_button = format_html(
            '<a href="{}" class="btn btn-sm btn-dark me-1"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="Park tag (put aside for later)">'
            '<i class="fa fa-box-archive"></i></a>',
            reverse_lazy("twf:tags_park", kwargs={"pk": record.pk}),
        )

        transkribus_button = format_html(
            '<a href="{}" class="btn btn-sm btn-ext me-1" target="_blank"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="View on Transkribus">'
            '<i class="fa fa-scroll"></i></a>',
            record.get_transkribus_url(),
        )

        return mark_safe(
            f"{detail_button}{park_button}{transkribus_button}"
        )


class IgnoredTagTable(tables.Table):
    """
    Simplified table for displaying ignored tags.
    Shows only basic info and minimal action buttons.
    """
    variation = tables.Column(
        verbose_name="Page Tag", attrs={"td": {"class": "fw-bold"}}
    )
    variation_type = tables.Column(verbose_name="Type")
    options = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    class Meta:
        """
        Table metadata configuration.
        """
        model = PageTag
        fields = ("variation", "variation_type")
        template_name = "django_tables2/bootstrap4.html"
        attrs = {"class": "table table-striped table-hover"}

    def render_options(self, record):
        """
        Render minimal action buttons for ignored tags.

        Args:
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML with action buttons
        """
        from django.utils.safestring import mark_safe

        detail_button = format_html(
            '<a href="{}" class="btn btn-sm btn-primary me-1"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="View tag details">'
            '<i class="fa fa-eye"></i></a>',
            reverse_lazy("twf:tags_detail", kwargs={"pk": record.pk}),
        )

        transkribus_button = format_html(
            '<a href="{}" class="btn btn-sm btn-ext me-1" target="_blank"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="View on Transkribus">'
            '<i class="fa fa-scroll"></i></a>',
            record.get_transkribus_url(),
        )

        return mark_safe(f"{detail_button}{transkribus_button}")


class TagsWithCommentsTable(tables.Table):
    """
    Table for displaying tags with comments from dictionary entries.
    Includes a comments column showing the dictionary entry notes.
    """
    variation = tables.Column(
        verbose_name="Page Tag", attrs={"td": {"class": "fw-bold"}}
    )
    variation_type = tables.Column(verbose_name="Type")
    status = tables.Column(
        verbose_name="Status",
        orderable=True,
        empty_values=(),
        order_by=("is_reserved", "is_parked", "dictionary_entry"),
        attrs={"th": {"class": "text-center"}, "td": {"class": "text-center"}},
    )
    entry = tables.Column(
        accessor="dictionary_entry", verbose_name="Entry", empty_values=()
    )
    comments = tables.Column(
        accessor="dictionary_entry__notes",
        verbose_name="Comments",
        orderable=True,
        empty_values=(),
    )
    options = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    class Meta:
        """
        Table metadata configuration.
        """
        model = PageTag
        fields = ("variation", "variation_type", "entry", "comments")
        template_name = "django_tables2/bootstrap4.html"
        attrs = {"class": "table table-striped table-hover"}

    def render_status(self, value, record):
        """
        Render comprehensive status badges for a tag.

        Args:
            value: Not used (column has no direct accessor)
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML badges showing tag status
        """
        from django.utils.safestring import mark_safe

        badges = []

        # Check if reserved (highest priority)
        if record.is_reserved:
            badges.append(
                '<span class="badge bg-info" data-bs-toggle="tooltip" '
                'title="Reserved in active workflow">'
                '<i class="fa fa-lock me-1"></i>Reserved</span>'
            )

        # Check if parked
        if record.is_parked:
            badges.append(
                '<span class="badge bg-warning text-dark" data-bs-toggle="tooltip" '
                'title="Parked for later processing">'
                '<i class="fa fa-box-archive me-1"></i>Parked</span>'
            )

        # Check if processed (has dictionary entry or enrichment)
        if record.dictionary_entry or record.tag_enrichment_entry or record.date_variation_entry:
            badges.append(
                '<span class="badge bg-success" data-bs-toggle="tooltip" '
                'title="Processed (grouped or enriched)">'
                '<i class="fa fa-check-circle me-1"></i>Processed</span>'
            )
        elif not record.is_parked:
            # Unresolved (not parked and not processed)
            badges.append(
                '<span class="badge bg-danger" data-bs-toggle="tooltip" '
                'title="Unresolved - needs processing">'
                '<i class="fa fa-exclamation-circle me-1"></i>Unresolved</span>'
            )

        return mark_safe(" ".join(badges) if badges else "-")

    def render_entry(self, value, record):
        """
        Render dictionary entry information.

        Args:
            value: Dictionary entry value
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML showing entry information
        """
        if record.dictionary_entry:
            return format_html(
                '<span class="badge bg-primary me-1" data-bs-toggle="tooltip" '
                'title="Dictionary: {}">''<i class="fa fa-book"></i></span>'
                '{}',
                record.dictionary_entry.dictionary.label if record.dictionary_entry.dictionary else "Unknown",
                record.dictionary_entry.label
            )
        return "-"

    def render_comments(self, value, record):
        """
        Render dictionary entry notes/comments, truncated to 300 characters.

        Args:
            value: The notes field from dictionary entry
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML showing truncated comments
        """
        if record.dictionary_entry and record.dictionary_entry.notes:
            notes = record.dictionary_entry.notes
            max_length = 300

            if len(notes) > max_length:
                truncated = notes[:max_length] + "..."
                return format_html(
                    '<span class="text-muted small" data-bs-toggle="tooltip" '
                    'title="{}">''{}''</span>',
                    notes[:500],  # Full tooltip up to 500 chars
                    truncated
                )
            else:
                return format_html('<span class="text-muted small">{}</span>', notes)
        return "-"

    def render_options(self, record):
        """
        Render action buttons for tag operations.

        Args:
            record: PageTag model instance

        Returns:
            SafeString: Formatted HTML with action buttons
        """
        from django.utils.safestring import mark_safe

        detail_button = format_html(
            '<a href="{}" class="btn btn-sm btn-primary me-1"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="View tag details">'
            '<i class="fa fa-eye"></i></a>',
            reverse_lazy("twf:tags_detail", kwargs={"pk": record.pk}),
        )

        park_button = format_html(
            '<a href="{}" class="btn btn-sm btn-dark me-1"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="Park tag (put aside for later)">'
            '<i class="fa fa-box-archive"></i></a>',
            reverse_lazy("twf:tags_park", kwargs={"pk": record.pk}),
        )

        transkribus_button = format_html(
            '<a href="{}" class="btn btn-sm btn-ext me-1" target="_blank"'
            '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="View on Transkribus">'
            '<i class="fa fa-scroll"></i></a>',
            record.get_transkribus_url(),
        )

        return mark_safe(
            f"{detail_button}{park_button}{transkribus_button}"
        )

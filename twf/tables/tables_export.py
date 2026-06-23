import django_tables2 as tables
from django.urls import reverse_lazy
from django.utils.html import format_html
from twf.models import Export, ExportConfiguration


class ExportTable(tables.Table):
    """
    Table for displaying exports with actions.
    """
    created = tables.DateTimeColumn(accessor="created_at", verbose_name="Created")
    updated = tables.Column(accessor="modified_at", verbose_name="Updated")
    actions = tables.Column(empty_values=(), verbose_name="Options", orderable=False)
    export_size = tables.Column(verbose_name="Size", accessor="id")

    class Meta:
        """
        Metaclass for ExportTable defining model, fields, and table attributes.
        """
        model = Export
        fields = ("export_configuration__name", "created", "updated", "export_size")
        attrs = {"class": "table table-striped table-hover table-sm"}

    def render_created(self, value, record):
        """
        Render creation timestamp with creator username.

        Args:
            value: DateTime of creation
            record: Export model instance

        Returns:
            SafeString: Formatted HTML with timestamp and username
        """
        return format_html(
            '<span class="badge bg-light text-dark">{}</span> by {}',
            value.strftime("%Y-%m-%d %H:%M"),
            record.created_by.username,
        )

    def render_updated(self, value, record):
        """
        Render update timestamp with modifier username.

        Args:
            value: DateTime of last modification
            record: Export model instance

        Returns:
            SafeString: Formatted HTML with timestamp and username
        """
        return format_html(
            '<span class="badge bg-light text-dark">{}</span> by {}',
            value.strftime("%Y-%m-%d %H:%M"),
            record.modified_by.username,
        )

    def render_export_size(self, value, record):
        """
        Render file size in human-readable format.

        Args:
            value: Export ID (accessor value)
            record: Export model instance

        Returns:
            str: Formatted file size with appropriate unit
        """
        size = record.export_file.size
        if size < 1024:
            return f"{size} bytes"
        elif size < 1024**2:
            return f"{size / 1024:.2f} KB"
        elif size < 1024**3:
            return f"{size / (1024 ** 2):.2f} MB"
        else:
            return f"{size / (1024 ** 3):.2f} GB"

    def render_actions(self, record):
        """
        Render action buttons for export operations.

        Args:
            record: Export model instance

        Returns:
            SafeString: Formatted HTML with download and delete buttons
        """
        # export_exports_delete
        return format_html(
            "{} {}",
            format_html(
                '<a href="{}" class="btn btn-sm btn-dark me-1"'
                '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="Download the exported data">'
                '<i class="fa fa-download"></i></a>',
                reverse_lazy(
                    "twf:export_configure_view_sample", kwargs={"pk": record.pk}
                ),
            ),
            format_html(
                '<a href="#" class="btn btn-sm btn-danger show-danger-modal"'
                '  data-message="Are you sure you want to delete this export?" '
                '  data-redirect-url="{}" '
                '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="Delete Export">'
                '<i class="fa fa-trash"></i></a>',
                reverse_lazy("twf:export_exports_delete", kwargs={"pk": record.pk}),
            ),
        )


class ExportConfigTable(tables.Table):
    """
    Table for displaying export configurations with actions.
    """
    name = tables.Column(verbose_name="Name")
    export_type = tables.Column(verbose_name="Type")
    output_format = tables.Column(verbose_name="Output Format")

    created = tables.DateTimeColumn(accessor="created_at", verbose_name="Created")
    updated = tables.Column(accessor="modified_at", verbose_name="Updated")
    actions = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    class Meta:
        """
        Metaclass for ExportConfigTable defining model, fields, and table attributes.
        """
        model = ExportConfiguration
        fields = ("name", "export_type", "output_format", "created", "updated")
        attrs = {"class": "table table-striped table-hover table-sm"}

    def render_created(self, value, record):
        """
        Render creation timestamp with creator username.

        Args:
            value: DateTime of creation
            record: ExportConfiguration model instance

        Returns:
            SafeString: Formatted HTML with timestamp and username
        """
        return format_html(
            '<span class="badge bg-light text-dark">{}</span> by {}',
            value.strftime("%Y-%m-%d %H:%M"),
            record.created_by.username,
        )

    def render_updated(self, value, record):
        """
        Render update timestamp with modifier username.

        Args:
            value: DateTime of last modification
            record: ExportConfiguration model instance

        Returns:
            SafeString: Formatted HTML with timestamp and username
        """
        return format_html(
            '<span class="badge bg-light text-dark">{}</span> by {}',
            value.strftime("%Y-%m-%d %H:%M"),
            record.modified_by.username,
        )

    def render_output_format(self, value):
        """
        Render output format as a badge.

        Args:
            value: Output format string

        Returns:
            SafeString: Formatted HTML badge with format label
        """
        label = value.title() if value else "Unknown"
        return format_html('<span class="badge bg-light text-dark">{}</span>', label)

    def render_export_type(self, value):
        """
        Render export type as a badge.

        Args:
            value: Export type string

        Returns:
            SafeString: Formatted HTML badge with type label
        """
        label = value.title() if value else "Unknown"
        return format_html('<span class="badge bg-dark text-light">{}</span>', label)

    def render_actions(self, record):
        """
        Render action buttons for export configuration operations.

        Args:
            record: ExportConfiguration model instance

        Returns:
            SafeString: Formatted HTML with edit, view, and delete buttons
        """
        return format_html(
            "{} {} {}",
            format_html(
                '<a href="{}" class="btn btn-sm btn-dark me-1"'
                '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="Edit export configuration">'
                '<i class="fa fa-edit"></i></a>',
                reverse_lazy("twf:export_configure_edit", kwargs={"pk": record.pk}),
            ),
            format_html(
                '<a href="{}" class="btn btn-sm btn-dark me-1"'
                '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="View sample export item">'
                '<i class="fa fa-eye"></i></a>',
                reverse_lazy(
                    "twf:export_configure_view_sample", kwargs={"pk": record.pk}
                ),
            ),
            format_html(
                '<a href="#" class="btn btn-sm btn-danger show-danger-modal"'
                '  data-message="Are you sure you want to delete this tag?" '
                '  data-redirect-url="{}" '
                '  data-bs-toggle="tooltip" data-bs-placement="bottom" title="Delete tag">'
                '<i class="fa fa-trash"></i></a>',
                reverse_lazy("twf:export_conf_delete", kwargs={"pk": record.pk}),
            ),
        )

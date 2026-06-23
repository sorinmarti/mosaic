"""Table classes for displaying Collection and CollectionItem objects."""

import django_tables2 as tables
from django.urls import reverse_lazy
from django.utils.html import format_html

from twf.models import CollectionItem, Collection


class CollectionTable(tables.Table):
    """Table for displaying Collection objects."""

    title = tables.Column(verbose_name="Collection Title")
    description = tables.Column(verbose_name="Description")
    item_count = tables.Column(empty_values=(), verbose_name="Items", order_by="item_count_annotated")
    created_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Created")
    created_by = tables.Column(verbose_name="Created By")
    actions = tables.Column(empty_values=(), verbose_name="Options", orderable=False)

    def render_title(self, value, record):
        """Render the collection title."""
        return format_html('<span class="fw-bold">{}</span>', value)

    def render_description(self, value):
        """Render the description with truncation if needed."""
        if not value:
            return "-"
        if len(value) > 100:
            return format_html('<span title="{}">{}&hellip;</span>', value, value[:100])
        return value

    def render_item_count(self, record):
        """Render the item count."""
        count = record.items.count()

        # Calculate statuses for progress display
        reviewed = record.items.filter(status="reviewed").count()
        open_items = record.items.filter(status="open").count()
        faulty = record.items.filter(status="faulty").count()

        # Only show progress bar if there are items
        if count > 0:
            reviewed_percent = (reviewed / count) * 100
            open_percent = (open_items / count) * 100
            faulty_percent = (faulty / count) * 100

            return format_html(
                "<div>{} items</div>"
                '<div class="progress" style="height: 15px;" title="Reviewed: {} | Open: {} | Faulty: {}">'
                '<div class="progress-bar bg-success" style="width: {}%" title="Reviewed: {}">{}</div>'
                '<div class="progress-bar bg-info" style="width: {}%" title="Open: {}">{}</div>'
                '<div class="progress-bar bg-warning" style="width: {}%" title="Faulty: {}">{}</div>'
                "</div>",
                count,
                reviewed,
                open_items,
                faulty,
                reviewed_percent,
                reviewed,
                reviewed if reviewed > 0 else "",
                open_percent,
                open_items,
                open_items if open_items > 0 else "",
                faulty_percent,
                faulty,
                faulty if faulty > 0 else "",
            )
        return "0 items"

    def render_actions(self, record):
        """Render the action buttons."""
        view_url = reverse_lazy("twf:collection_view", kwargs={"pk": record.pk})
        edit_url = reverse_lazy("twf:collection_edit", kwargs={"pk": record.pk})
        delete_modal = format_html(
            '<a href="#" class="btn btn-sm btn-danger show-danger-modal" '
            'data-redirect-url="/collections/delete/{}" '
            'data-message="Are you sure you want to delete this collection? '
            'This will remove all collection items as well.">'
            '<i class="fa fa-trash"></i></a>',
            record.pk,
        )

        return format_html(
            '<div class="btn-group" role="group">'
            '<a href="{}" class="btn btn-sm btn-dark me-1"><i class="fa fa-eye"></i> View</a>'
            '<a href="{}" class="btn btn-sm btn-secondary me-1"><i class="fa fa-pencil"></i> Edit</a>'
            "{}"
            "</div>",
            view_url,
            edit_url,
            delete_modal,
        )

    class Meta:
        """Meta class for the CollectionTable."""

        model = Collection
        fields = ("title", "description", "item_count", "created_at", "created_by")
        attrs = {"class": "table table-striped table-hover"}
        template_name = "django_tables2/bootstrap4.html"


class CollectionItemTable(tables.Table):
    """Table for displaying CollectionItem objects."""

    document_id = tables.Column(
        accessor="document.document_id", verbose_name="Document ID"
    )
    title = tables.Column(verbose_name="Item Title")
    document_title = tables.Column(
        accessor="document.title", verbose_name="Document Title"
    )
    created_at = tables.DateTimeColumn(format="Y-m-d H:i", verbose_name="Created")
    status = tables.Column(verbose_name="Status")
    actions = tables.Column(empty_values=(), verbose_name="Actions", orderable=False)

    def render_document_id(self, record, value):
        """Render the document ID with a link to the document."""
        if not value:
            return "-"
        return format_html(
            '<a href="{}" class="fw-bold">{}</a>',
            reverse_lazy("twf:view_document", kwargs={"pk": record.document.pk}),
            value,
        )

    def render_title(self, value, record):
        """Render the item title with a link to the item view."""
        return format_html(
            '<a href="{}">{}</a>',
            reverse_lazy("twf:collection_item_view", kwargs={"pk": record.pk}),
            value if value else "Untitled Item",
        )

    def render_document_title(self, value):
        """Render the document title with truncation if needed."""
        if not value:
            return "-"
        if len(value) > 40:
            return format_html('<span title="{}">{}&hellip;</span>', value, value[:40])
        return value

    def render_status(self, record):
        """Render the status as a badge."""
        status_classes = {
            "open": "bg-info",
            "reviewed": "bg-success",
            "faulty": "bg-warning",
        }

        status_html = format_html(
            '<span class="badge {}">{}</span>',
            status_classes.get(record.status, "bg-secondary"),
            record.status,
        )

        # Add workflow indicator if item is reserved
        if record.is_reserved:
            status_html = format_html(
                '{}<br><span class="badge bg-secondary mt-1">In Workflow</span>',
                status_html,
            )

        return status_html

    def render_actions(self, record):
        """Render action buttons."""
        view_url = reverse_lazy("twf:collection_item_view", kwargs={"pk": record.pk})
        edit_url = reverse_lazy("twf:collection_item_edit", kwargs={"pk": record.pk})

        # Determine if we should show download buttons based on having annotations
        has_annotations = (
            record.document_configuration
            and "annotations" in record.document_configuration
            and record.document_configuration["annotations"]
        )

        download_buttons = ""
        if has_annotations:
            txt_url = reverse_lazy(
                "twf:collection_item_download_txt", kwargs={"pk": record.pk}
            )
            json_url = reverse_lazy(
                "twf:collection_item_download_json", kwargs={"pk": record.pk}
            )
            download_buttons = format_html(
                '<div class="dropdown-divider"></div>'
                '<a class="dropdown-item" href="{}" target="_blank">'
                '<i class="fa fa-file-text-o"></i> Download TXT</a>'
                '<a class="dropdown-item" href="{}" target="_blank">'
                '<i class="fa fa-file-code-o"></i> Download JSON</a>',
                txt_url,
                json_url,
            )

        # Status update links
        status_links = format_html(
            '<div class="dropdown-divider"></div>'
            '<a class="dropdown-item" href="{}">'
            '<i class="fa fa-check text-success"></i> Mark Reviewed</a>'
            '<a class="dropdown-item" href="{}">'
            '<i class="fa fa-exclamation-triangle text-warning"></i> Mark Faulty</a>'
            '<a class="dropdown-item" href="{}">'
            '<i class="fa fa-refresh text-info"></i> Mark Open</a>',
            reverse_lazy(
                "twf:collection_item_status_reviewed", kwargs={"pk": record.pk}
            ),
            reverse_lazy("twf:collection_item_status_faulty", kwargs={"pk": record.pk}),
            reverse_lazy("twf:collection_item_status_open", kwargs={"pk": record.pk}),
        )

        # Delete button (using danger modal)
        delete_modal = format_html(
            '<div class="dropdown-divider"></div>'
            '<a class="dropdown-item text-danger show-danger-modal" href="#" '
            'data-redirect-url="{}" '
            'data-message="Are you sure you want to delete this collection item? This cannot be undone.">'
            '<i class="fa fa-trash"></i> Delete</a>',
            reverse_lazy("twf:collection_item_delete", kwargs={"pk": record.pk}),
        )

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
            '<a class="dropdown-item" href="{}"><i class="fa fa-pencil"></i> Edit Item</a>'
            "{}{}{}"
            "</ul>"
            "</div>",
            view_url,
            edit_url,
            view_url,
            edit_url,
            download_buttons,
            status_links,
            delete_modal,
        )

    class Meta:
        """Meta class for the CollectionItemTable."""

        model = CollectionItem
        fields = ("document_id", "title", "document_title", "created_at", "status")
        attrs = {"class": "table table-striped table-hover"}
        template_name = "django_tables2/bootstrap4.html"

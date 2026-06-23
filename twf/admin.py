"""Admin View configuration for the twf models."""

from django.contrib import admin
from .models import (
    UserProfile,
    Project,
    Document,
    Page,
    Dictionary,
    DictionaryEntry,
    Variation,
    PageTag,
    Collection,
    CollectionItem,
    DateVariation,
    Workflow,
    Task,
    ExportConfiguration,
    Export,
    Note,
    DocumentSyncHistory,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin View for UserProfile."""

    list_filter = ["user"]
    search_fields = ["user__username", "user__email"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin View for Project."""

    list_filter = ["status", "created_at", "owner"]
    search_fields = ["title", "collection_id"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Admin View for Document."""

    list_display = [
        "project",
        "title",
        "document_id",
        "metadata",
        "status",
        "is_parked",
        "is_reserved",
    ]
    list_filter = ["project", "created_at"]
    search_fields = ["title", "document_id"]


@admin.register(DocumentSyncHistory)
class DocumentSyncHistoryAdmin(admin.ModelAdmin):
    """Admin View for DocumentSyncHistory."""

    list_display = ["document", "sync_type", "synced_at", "user", "project"]
    list_filter = ["sync_type", "project", "synced_at"]
    search_fields = ["document__document_id", "document__title", "user__username"]
    readonly_fields = [
        "document",
        "task",
        "project",
        "user",
        "sync_type",
        "changes",
        "synced_at",
        "created_at",
        "modified_at",
        "created_by",
        "modified_by",
    ]

    def has_add_permission(self, request):
        """Prevent manual creation of sync history records."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup purposes."""
        return request.user.is_superuser


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Admin View for Page."""

    list_filter = ["document", "document__document_id", "tk_page_number", "is_ignored"]
    search_fields = ["tk_page_id", "document__document_id"]


@admin.register(Dictionary)
class DictionaryAdmin(admin.ModelAdmin):
    """Admin View for Dictionary."""

    list_filter = ["type", "created_at"]
    search_fields = ["label"]


@admin.register(DictionaryEntry)
class DictionaryEntryAdmin(admin.ModelAdmin):
    """Admin View for DictionaryEntry."""

    list_filter = ["dictionary", "created_at"]
    search_fields = ["label"]


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    """Admin View for Variation."""

    list_filter = ["entry", "created_at"]
    search_fields = ["variation"]


@admin.register(PageTag)
class PageTagAdmin(admin.ModelAdmin):
    """Admin View for PageTag."""

    list_filter = ["page", "variation_type", "is_parked"]
    search_fields = ["variation"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    """Admin View for Collection."""

    list_filter = ["project", "created_at"]
    search_fields = ["title"]


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    """Admin View for CollectionItem."""

    list_display = ["collection", "title", "document", "status", "is_reserved"]
    list_filter = ["collection", "created_at"]
    search_fields = ["title", "document__title"]


@admin.register(DateVariation)
class DateVariationAdmin(admin.ModelAdmin):
    """Admin View for DateVariation."""

    list_filter = ["created_at"]
    search_fields = ["variation"]


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    """Admin View for Workflow."""

    list_filter = ["workflow_type", "status", "created_at"]
    search_fields = ["user__username", "project__title"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin View for Task."""

    list_display = ["title", "project", "status", "progress", "start_time", "end_time"]
    list_filter = ["status", "project", "start_time"]
    search_fields = ["title", "celery_task_id", "user__username"]


@admin.register(ExportConfiguration)
class ExportConfigurationAdmin(admin.ModelAdmin):
    """Admin View for ExportConfiguration."""

    list_display = ["name", "project", "export_type", "output_format"]
    list_filter = ["project", "export_type", "output_format"]
    search_fields = ["name", "description"]


@admin.register(Export)
class ExportAdmin(admin.ModelAdmin):
    """Admin View for Export."""

    list_display = ["export_configuration", "created_at"]
    list_filter = ["export_configuration__project", "created_at"]
    search_fields = ["export_configuration__name"]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Admin View for Note."""

    list_display = ["title", "project", "created_at"]
    list_filter = ["project", "created_at"]
    search_fields = ["title", "note"]


# Register all models without custom admin classes
# admin.site.register(UserProfile, UserProfileAdmin)
# admin.site.register(Project, ProjectAdmin)
# admin.site.register(Document, DocumentAdmin)
# admin.site.register(Page, PageAdmin)
# admin.site.register(Dictionary, DictionaryAdmin)
# admin.site.register(DictionaryEntry, DictionaryEntryAdmin)
# admin.site.register(Variation, VariationAdmin)
# admin.site.register(PageTag, PageTagAdmin)
# admin.site.register(Collection, CollectionAdmin)
# admin.site.register(CollectionItem, CollectionItemAdmin)
# admin.site.register(DateVariation, DateVariationAdmin)

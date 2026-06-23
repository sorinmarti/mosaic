"""Management command to clean up orphaned reserved items."""

from django.core.management.base import BaseCommand
from django.db.models import Q
from twf.models import PageTag, Document, CollectionItem


class Command(BaseCommand):
    """Clean up orphaned reserved items (tags, documents, collections)."""

    help = "Release items marked as reserved but not in any active workflow"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleaned up without actually doing it",
        )
        parser.add_argument(
            "--project-id",
            type=int,
            help="Only clean up items from a specific project",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        dry_run = options["dry_run"]
        project_id = options.get("project_id")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Clean up reserved tags
        self.stdout.write("\n=== CHECKING RESERVED TAGS ===")
        reserved_tags = PageTag.objects.filter(is_reserved=True)

        if project_id:
            reserved_tags = reserved_tags.filter(page__document__project_id=project_id)

        orphaned_tags = []
        for tag in reserved_tags:
            # Check if tag is in any active workflow
            has_active_workflow = tag.workflows.filter(status="started").exists()
            if not has_active_workflow:
                orphaned_tags.append(tag)

        if orphaned_tags:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(orphaned_tags)} orphaned reserved tags:"
                )
            )
            for tag in orphaned_tags[:10]:  # Show first 10
                self.stdout.write(
                    f"  - Tag {tag.id}: {tag.variation} (type: {tag.variation_type})"
                )
            if len(orphaned_tags) > 10:
                self.stdout.write(f"  ... and {len(orphaned_tags) - 10} more")

            if not dry_run:
                PageTag.objects.filter(
                    id__in=[t.id for t in orphaned_tags]
                ).update(is_reserved=False)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Released {len(orphaned_tags)} orphaned tags"
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS("✓ No orphaned tags found"))

        # Clean up reserved documents
        self.stdout.write("\n=== CHECKING RESERVED DOCUMENTS ===")
        reserved_docs = Document.objects.filter(is_reserved=True)

        if project_id:
            reserved_docs = reserved_docs.filter(project_id=project_id)

        orphaned_docs = []
        for doc in reserved_docs:
            # Check if document is in any active workflow
            has_active_workflow = doc.workflows.filter(status="started").exists()
            if not has_active_workflow:
                orphaned_docs.append(doc)

        if orphaned_docs:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(orphaned_docs)} orphaned reserved documents:"
                )
            )
            for doc in orphaned_docs[:10]:
                self.stdout.write(f"  - Doc {doc.id}: {doc.title}")
            if len(orphaned_docs) > 10:
                self.stdout.write(f"  ... and {len(orphaned_docs) - 10} more")

            if not dry_run:
                Document.objects.filter(
                    id__in=[d.id for d in orphaned_docs]
                ).update(is_reserved=False)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Released {len(orphaned_docs)} orphaned documents"
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS("✓ No orphaned documents found"))

        # Clean up reserved collection items
        self.stdout.write("\n=== CHECKING RESERVED COLLECTION ITEMS ===")
        reserved_items = CollectionItem.objects.filter(is_reserved=True)

        if project_id:
            reserved_items = reserved_items.filter(collection__project_id=project_id)

        orphaned_items = []
        for item in reserved_items:
            # Check if item is in any active workflow
            has_active_workflow = item.workflows.filter(status="started").exists()
            if not has_active_workflow:
                orphaned_items.append(item)

        if orphaned_items:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(orphaned_items)} orphaned reserved collection items:"
                )
            )
            for item in orphaned_items[:10]:
                self.stdout.write(
                    f"  - Item {item.id} from collection {item.collection.name}"
                )
            if len(orphaned_items) > 10:
                self.stdout.write(f"  ... and {len(orphaned_items) - 10} more")

            if not dry_run:
                CollectionItem.objects.filter(
                    id__in=[i.id for i in orphaned_items]
                ).update(is_reserved=False)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Released {len(orphaned_items)} orphaned collection items"
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("✓ No orphaned collection items found")
            )

        # Summary
        total_orphaned = len(orphaned_tags) + len(orphaned_docs) + len(orphaned_items)
        self.stdout.write("\n" + "=" * 50)
        if total_orphaned > 0:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"Would release {total_orphaned} orphaned reserved items"
                    )
                )
                self.stdout.write(
                    "Run without --dry-run to actually release these items"
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Successfully released {total_orphaned} orphaned reserved items!"
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("✓ No orphaned reserved items found!")
            )

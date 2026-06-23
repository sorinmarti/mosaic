"""Management command to identify and remove duplicate PageTag objects."""

from django.core.management.base import BaseCommand
from django.db.models import Count
from twf.models import PageTag


class Command(BaseCommand):
    """Management command to identify and remove duplicate PageTag objects."""

    help = (
        "Identify and optionally remove duplicate PageTag objects. "
        "Duplicates are identified by matching page, variation, variation_type, "
        "and dictionary_entry fields."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            help="Optional: Filter by project ID to check only PageTags in specific project.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete duplicate PageTags, keeping only the first one for each duplicate group.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform a dry run without actually deleting anything.",
        )

    def handle(self, *args, **options):
        """Handle the management command."""
        project_id = options.get("project_id")
        delete_duplicates = options["delete"]
        dry_run = options["dry_run"]

        # Build queryset
        queryset = PageTag.objects.all()

        if project_id:
            queryset = queryset.filter(page__document__project_id=project_id)
            self.stdout.write(f"Checking PageTags for project ID {project_id}...\n")
        else:
            self.stdout.write("Checking all PageTags across all projects...\n")

        # Get total count before deduplication
        total_count = queryset.count()
        self.stdout.write(f"Total PageTags: {total_count}\n")

        # Find duplicates based on unique fields
        # Group by page, variation, variation_type, and dictionary_entry
        duplicates = (
            queryset.values("page", "variation", "variation_type", "dictionary_entry")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .order_by("-count")
        )

        if not duplicates:
            self.stdout.write(self.style.SUCCESS("No duplicate PageTags found!"))
            return

        duplicate_count = len(duplicates)
        total_duplicates = sum(d["count"] - 1 for d in duplicates)

        self.stdout.write(
            self.style.WARNING(
                f"Found {duplicate_count} duplicate PageTag group(s) "
                f"with {total_duplicates} redundant entries.\n"
            )
        )

        deleted_count = 0

        for duplicate in duplicates:
            page_id = duplicate["page"]
            variation = duplicate["variation"]
            variation_type = duplicate["variation_type"]
            dictionary_entry_id = duplicate["dictionary_entry"]
            count = duplicate["count"]

            # Fetch all PageTags in this duplicate group
            duplicate_tags = queryset.filter(
                page_id=page_id,
                variation=variation,
                variation_type=variation_type,
                dictionary_entry_id=dictionary_entry_id,
            ).order_by("id")

            self.stdout.write(
                self.style.WARNING(f"\nDuplicate Group ({count} instances):")
            )
            self.stdout.write(f"  Page ID: {page_id}")
            self.stdout.write(f"  Variation: {variation}")
            self.stdout.write(f"  Type: {variation_type}")
            self.stdout.write(f"  Dictionary Entry ID: {dictionary_entry_id}")

            # Show details of each duplicate
            first_tag = duplicate_tags.first()
            self.stdout.write(f"\n  PageTag IDs: {[tag.id for tag in duplicate_tags]}")
            self.stdout.write(f"  Keeping: PageTag ID {first_tag.id}")

            # Check for differences in additional_information or other fields
            has_differences = False
            for tag in duplicate_tags[1:]:
                if (
                    tag.additional_information != first_tag.additional_information
                    or tag.date_variation_entry_id != first_tag.date_variation_entry_id
                    or tag.is_parked != first_tag.is_parked
                ):
                    has_differences = True
                    self.stdout.write(
                        self.style.WARNING(
                            f"  WARNING: PageTag ID {tag.id} has different metadata!"
                        )
                    )
                    self.stdout.write(
                        f"    - additional_information: {tag.additional_information}"
                    )
                    self.stdout.write(
                        f"    - date_variation_entry_id: {tag.date_variation_entry_id}"
                    )
                    self.stdout.write(f"    - is_parked: {tag.is_parked}")

            # Delete duplicates if requested
            if delete_duplicates and not dry_run:
                to_delete = duplicate_tags.exclude(id=first_tag.id)
                delete_count = to_delete.count()
                to_delete.delete()
                deleted_count += delete_count
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Deleted {delete_count} duplicate(s), kept PageTag ID {first_tag.id}"
                    )
                )
            elif delete_duplicates and dry_run:
                to_delete = duplicate_tags.exclude(id=first_tag.id)
                delete_count = to_delete.count()
                self.stdout.write(
                    self.style.NOTICE(
                        f"  [DRY RUN] Would delete {delete_count} duplicate(s)"
                    )
                )
            else:
                self.stdout.write(
                    f"  Would delete {count - 1} duplicate(s) with --delete flag"
                )

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if delete_duplicates and not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCompleted! Deleted {deleted_count} duplicate PageTags."
                )
            )
            remaining = total_count - deleted_count
            self.stdout.write(f"Remaining PageTags: {remaining}")
        elif delete_duplicates and dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"\n[DRY RUN] Would delete {total_duplicates} duplicate PageTags."
                )
            )
            self.stdout.write("Run without --dry-run to perform actual deletion.")
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nFound {total_duplicates} duplicate PageTags. "
                    "Use --delete flag to remove them."
                )
            )

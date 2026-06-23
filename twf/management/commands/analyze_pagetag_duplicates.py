"""Management command to analyze PageTag duplicates and check for position data."""

from django.core.management.base import BaseCommand
from django.db.models import Count
from twf.models import PageTag
import json


class Command(BaseCommand):
    """Analyze PageTag duplicates to determine if position data exists."""

    help = "Analyze PageTag duplicates to see if additional_information contains position data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id", type=int, help="Optional: Filter by project ID."
        )
        parser.add_argument(
            "--sample-size",
            type=int,
            default=5,
            help="Number of duplicate groups to analyze in detail (default: 5).",
        )

    def handle(self, *args, **options):
        """Handle the management command."""
        project_id = options.get("project_id")
        sample_size = options["sample_size"]

        # Build queryset
        queryset = PageTag.objects.all()

        if project_id:
            queryset = queryset.filter(page__document__project_id=project_id)
            self.stdout.write(f"Analyzing PageTags for project ID {project_id}...\n")
        else:
            self.stdout.write("Analyzing all PageTags...\n")

        total_count = queryset.count()
        self.stdout.write(f"Total PageTags: {total_count}\n")

        # Find potential duplicates
        duplicates = (
            queryset.values("page", "variation", "variation_type", "dictionary_entry")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
            .order_by("-count")
        )

        if not duplicates:
            self.stdout.write(self.style.SUCCESS("No potential duplicates found!"))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {len(duplicates)} potential duplicate groups.\n")
        )

        # Analyze sample groups in detail
        for i, duplicate in enumerate(duplicates[:sample_size]):
            page_id = duplicate["page"]
            variation = duplicate["variation"]
            variation_type = duplicate["variation_type"]
            dictionary_entry_id = duplicate["dictionary_entry"]
            count = duplicate["count"]

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(
                self.style.WARNING(f"\nGroup {i+1}: {count} instances of '{variation}'")
            )
            self.stdout.write(f"  Page ID: {page_id}")
            self.stdout.write(f"  Type: {variation_type}")
            self.stdout.write(f"  Dictionary Entry ID: {dictionary_entry_id}")

            # Fetch all tags in this group
            tags = queryset.filter(
                page_id=page_id,
                variation=variation,
                variation_type=variation_type,
                dictionary_entry_id=dictionary_entry_id,
            ).order_by("id")

            # Analyze each tag
            self.stdout.write("\n  Detailed Analysis:")

            unique_additional_info = set()
            unique_timestamps = set()
            all_identical = True

            for tag in tags:
                self.stdout.write(f"\n    PageTag ID: {tag.id}")
                self.stdout.write(f"      Created: {tag.created_at}")
                self.stdout.write(f"      Modified: {tag.modified_at}")
                self.stdout.write(f"      Created by: {tag.created_by}")
                self.stdout.write(f"      Is parked: {tag.is_parked}")
                self.stdout.write(
                    f"      Date variation entry: {tag.date_variation_entry_id}"
                )

                # Convert additional_information to string for comparison
                info_str = json.dumps(tag.additional_information, sort_keys=True)
                unique_additional_info.add(info_str)

                if tag.additional_information:
                    self.stdout.write(
                        f"      Additional info: {tag.additional_information}"
                    )
                else:
                    self.stdout.write("      Additional info: (empty)")

                # Track timestamps
                timestamp_tuple = (
                    tag.created_at.isoformat() if tag.created_at else None,
                    tag.modified_at.isoformat() if tag.modified_at else None,
                )
                unique_timestamps.add(timestamp_tuple)

            # Summary for this group
            self.stdout.write("\n  Summary:")
            self.stdout.write(
                f"    Unique additional_information values: {len(unique_additional_info)}"
            )
            self.stdout.write(
                f"    Unique timestamp combinations: {len(unique_timestamps)}"
            )

            if len(unique_additional_info) == 1:
                self.stdout.write(
                    self.style.SUCCESS(
                        "    ✓ All tags have IDENTICAL additional_information"
                    )
                )
                self.stdout.write(
                    self.style.NOTICE(
                        "    → These appear to be TRUE DUPLICATES (safe to deduplicate)"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "    ✗ Tags have DIFFERENT additional_information"
                    )
                )
                self.stdout.write(
                    self.style.ERROR(
                        "    → These may be LEGITIMATE MULTIPLE OCCURRENCES (careful!)"
                    )
                )

        # Overall recommendation
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("\nRECOMMENDATION:")

        # Check if we need enhanced grouping
        needs_enhanced_grouping = False
        for duplicate in duplicates[:sample_size]:
            tags = queryset.filter(
                page_id=duplicate["page"],
                variation=duplicate["variation"],
                variation_type=duplicate["variation_type"],
                dictionary_entry_id=duplicate["dictionary_entry"],
            )

            unique_info = set(
                json.dumps(tag.additional_information, sort_keys=True) for tag in tags
            )

            if len(unique_info) > 1:
                needs_enhanced_grouping = True
                break

        if needs_enhanced_grouping:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠ Some groups have different additional_information values."
                )
            )
            self.stdout.write(
                "This suggests legitimate multiple occurrences on the same page."
            )
            self.stdout.write(
                "You should use an ENHANCED deduplication script that groups by"
            )
            self.stdout.write(
                "additional_information as well to preserve legitimate occurrences."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✓ All analyzed groups have identical additional_information."
                )
            )
            self.stdout.write(
                "These appear to be true duplicates. The basic fix_duplicate_pagetags"
            )
            self.stdout.write("command should work safely.")

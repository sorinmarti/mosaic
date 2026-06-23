"""
Management command to migrate TagEnrichment data to PageTag.enrichment field.

This command migrates enrichment data from the TagEnrichment model to the
PageTag.enrichment JSONField for a specific project or all projects.

Usage:
    python manage.py migrate_tag_enrichment --dry-run
    python manage.py migrate_tag_enrichment --project-id=1
    python manage.py migrate_tag_enrichment --all
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from twf.models import PageTag, TagEnrichment, Project


class Command(BaseCommand):
    """Migrate TagEnrichment data to PageTag.enrichment field."""

    help = "Migrate TagEnrichment data to PageTag.enrichment JSONField"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making any changes",
        )
        parser.add_argument(
            "--project-id",
            type=int,
            help="Migrate tags for a specific project ID",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Migrate tags for all projects",
        )

    def handle(self, *args, **options):
        """Execute the migration."""
        dry_run = options["dry_run"]
        project_id = options.get("project_id")
        all_projects = options.get("all")

        if not project_id and not all_projects:
            self.stdout.write(
                self.style.ERROR(
                    "Please specify either --project-id=<id> or --all"
                )
            )
            return

        # Build query for tags with enrichment entries
        tags_query = PageTag.objects.filter(
            tag_enrichment_entry__isnull=False
        ).select_related('tag_enrichment_entry', 'page__document__project')

        if project_id:
            try:
                project = Project.objects.get(id=project_id)
                tags_query = tags_query.filter(page__document__project=project)
                self.stdout.write(f"Processing project: {project.title}")
            except Project.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Project with ID {project_id} not found")
                )
                return

        tags_with_enrichment = tags_query
        total_count = tags_with_enrichment.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No tags with enrichment entries found.")
            )
            return

        self.stdout.write(
            f"Found {total_count} tags with enrichment entries to migrate"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would migrate {total_count} tag enrichments"
                )
            )

            # Show sample of what would be migrated
            sample_tags = tags_with_enrichment[:5]
            for tag in sample_tags:
                enrichment_entry = tag.tag_enrichment_entry
                self.stdout.write(
                    f"  - Tag '{tag.variation}' ({tag.variation_type}) "
                    f"→ {enrichment_entry.enrichment_type}: "
                    f"{enrichment_entry.normalized_value}"
                )

            if total_count > 5:
                self.stdout.write(f"  ... and {total_count - 5} more")

            return

        # Perform the migration with transaction
        with transaction.atomic():
            migrated_count = 0
            errors = []

            for tag in tags_with_enrichment:
                try:
                    enrichment_entry = tag.tag_enrichment_entry

                    # Initialize enrichment dict if needed
                    if tag.enrichment is None:
                        tag.enrichment = {}

                    # Check if enrichment type already exists
                    if enrichment_entry.enrichment_type in tag.enrichment:
                        warning_msg = (
                            f"Tag {tag.id} already has enrichment type "
                            f"'{enrichment_entry.enrichment_type}' - skipping"
                        )
                        self.stdout.write(self.style.WARNING(warning_msg))
                        continue

                    # Add enrichment data in the new format
                    tag.enrichment[enrichment_entry.enrichment_type] = {
                        "normalized_value": enrichment_entry.normalized_value,
                        "enrichment_data": enrichment_entry.enrichment_data or {},
                    }

                    tag.save(update_fields=['enrichment'])
                    migrated_count += 1

                    if migrated_count % 100 == 0:
                        self.stdout.write(f"Migrated {migrated_count}/{total_count} tags...")

                except Exception as e:
                    error_msg = f"Error migrating tag {tag.id}: {str(e)}"
                    errors.append(error_msg)
                    self.stdout.write(self.style.ERROR(error_msg))

            if errors:
                self.stdout.write(
                    self.style.ERROR(
                        f"Migration completed with {len(errors)} errors"
                    )
                )
                for error in errors[:10]:  # Show first 10 errors
                    self.stdout.write(f"  - {error}")
                raise Exception("Migration had errors - transaction rolled back")

            # Validation: check that migrated tags now have the enrichment data
            validation_count = tags_query.filter(
                enrichment__isnull=False
            ).exclude(enrichment={}).count()

            if validation_count < migrated_count:
                raise Exception(
                    f"Validation failed! Expected {migrated_count} tags with enrichment, "
                    f"but found {validation_count}. Rolling back migration."
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully migrated {migrated_count} tag enrichments"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Validation passed: {validation_count} tags have enrichment data"
                )
            )

        # Summary of enrichment types
        enrichment_types = {}
        for tag in tags_query:
            if tag.enrichment:
                for enrich_type in tag.enrichment.keys():
                    enrichment_types[enrich_type] = enrichment_types.get(enrich_type, 0) + 1

        if enrichment_types:
            self.stdout.write("\nEnrichment types migrated:")
            for enrich_type, count in sorted(enrichment_types.items()):
                self.stdout.write(f"  - {enrich_type}: {count} tags")

"""
Management command to migrate documents with irrelevant status to needs_tk_work.

This command updates all documents that have status='irrelevant' to status='needs_tk_work'
and adds an explanatory note to their workflow_remarks field.
"""

from django.core.management.base import BaseCommand
from twf.models import Document


class Command(BaseCommand):
    """Migrate documents with irrelevant status to needs_tk_work."""

    help = "Migrate documents with irrelevant status to needs_tk_work"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making any changes",
        )

    def handle(self, *args, **options):
        """Execute the migration."""
        dry_run = options["dry_run"]

        irrelevant_docs = Document.objects.filter(status="irrelevant")
        count = irrelevant_docs.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("No documents found with irrelevant status.")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would migrate {count} documents from irrelevant to needs_tk_work"
                )
            )
            for doc in irrelevant_docs[:10]:  # Show first 10
                self.stdout.write(f"  - Document {doc.document_id}: {doc.title}")
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
            return

        # Perform the migration
        migration_note = (
            "Previously marked as irrelevant - needs Exclude label in Transkribus"
        )

        for doc in irrelevant_docs:
            doc.status = "needs_tk_work"
            if not doc.workflow_remarks:
                doc.workflow_remarks = migration_note
            elif migration_note not in doc.workflow_remarks:
                doc.workflow_remarks += f"\n[{migration_note}]"
            doc.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully migrated {count} documents from irrelevant to needs_tk_work"
            )
        )

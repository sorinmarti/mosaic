"""Management command to update is_ignored flag for documents that already have 'Exclude' label in metadata."""
import logging
from django.core.management import BaseCommand
from twf.models import Document, Page

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Update is_ignored flag for documents and pages with 'Exclude' label in metadata."""
    help = 'Updates is_ignored flag for documents/pages that have "Exclude" label in metadata'

    def add_arguments(self, parser):
        """Add arguments to the command."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating'
        )

    def handle(self, *args, **options):
        """Handle the command."""
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')

        # Update documents
        self.stdout.write('Checking documents for "Exclude" labels...')
        documents_updated = 0
        documents_checked = 0

        for doc in Document.objects.all():
            documents_checked += 1

            if not doc.metadata:
                continue

            # Check for transkribus_api metadata
            tk_api = doc.metadata.get('transkribus_api', {})
            if not tk_api:
                continue

            # Check for Exclude label
            labels = tk_api.get('labels', [])
            has_exclude = any(label.get('name', '').lower() == 'exclude' for label in labels)

            if has_exclude and not doc.is_ignored:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Document {doc.id} (doc_id: {doc.document_id}): '
                        f'Has "Exclude" label but is_ignored=False'
                    )
                )

                if not dry_run:
                    doc.is_ignored = True
                    doc.save(update_fields=['is_ignored'])
                    documents_updated += 1
                else:
                    documents_updated += 1  # Count what would be updated

        self.stdout.write('')
        self.stdout.write(f'Documents checked: {documents_checked}')
        self.stdout.write(
            self.style.SUCCESS(f'Documents {"would be " if dry_run else ""}updated: {documents_updated}')
        )

        # Update pages
        self.stdout.write('')
        self.stdout.write('Checking pages for "Exclude" labels...')
        pages_updated = 0
        pages_checked = 0

        for page in Page.objects.all():
            pages_checked += 1

            if not page.metadata:
                continue

            # Check for transkribus_api metadata
            tk_api = page.metadata.get('transkribus_api', {})
            if not tk_api:
                continue

            # Check if page is marked as excluded
            is_excluded = tk_api.get('is_excluded', False)

            if is_excluded and not page.is_ignored:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Page {page.id} (page_id: {page.tk_page_id}, doc: {page.document.document_id}): '
                        f'Has is_excluded=True but is_ignored=False'
                    )
                )

                if not dry_run:
                    page.is_ignored = True
                    page.save(update_fields=['is_ignored'])
                    pages_updated += 1
                else:
                    pages_updated += 1  # Count what would be updated

        self.stdout.write('')
        self.stdout.write(f'Pages checked: {pages_checked}')
        self.stdout.write(
            self.style.SUCCESS(f'Pages {"would be " if dry_run else ""}updated: {pages_updated}')
        )

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes were made'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to apply changes'))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ Update complete!'))

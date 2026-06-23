"""Management command to regenerate normalized_value for TagEnrichment entries."""

from django.contrib.auth.models import User
from django.core.management import BaseCommand

from twf.models import TagEnrichment


class Command(BaseCommand):
    """Management command to regenerate normalized_value for TagEnrichment entries."""

    help = "Regenerate normalized_value for existing TagEnrichment entries"

    def add_arguments(self, parser):
        """Add arguments to the command."""
        parser.add_argument(
            "user_id",
            type=int,
            help="The user id to use for saving updates",
        )
        parser.add_argument(
            "--type",
            type=str,
            default=None,
            help="Only update specific enrichment type (e.g., 'verse', 'date')",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving",
        )

    def handle(self, *args, **options):
        """Handle the command."""
        user = User.objects.get(pk=options["user_id"])
        enrichment_type = options.get("type")
        dry_run = options.get("dry_run", False)

        # Query enrichments
        queryset = TagEnrichment.objects.all()
        if enrichment_type:
            queryset = queryset.filter(enrichment_type=enrichment_type)
            self.stdout.write(f"Processing {enrichment_type} enrichments...")
        else:
            self.stdout.write("Processing all enrichments...")

        updated_count = 0
        skipped_count = 0
        error_count = 0

        for enrichment in queryset:
            try:
                old_value = enrichment.normalized_value
                new_value = self._generate_normalized_value(enrichment)

                if old_value != new_value:
                    if dry_run:
                        self.stdout.write(
                            f"[DRY RUN] Would update ID {enrichment.pk}: "
                            f'"{old_value}" -> "{new_value}"'
                        )
                    else:
                        enrichment.normalized_value = new_value
                        enrichment.save(current_user=user)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Updated ID {enrichment.pk}: "
                                f'"{old_value}" -> "{new_value}"'
                            )
                        )
                    updated_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing ID {enrichment.pk}: {str(e)}"
                    )
                )
                error_count += 1

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes saved"))
        self.stdout.write(f"Total processed: {queryset.count()}")
        self.stdout.write(self.style.SUCCESS(f"Updated: {updated_count}"))
        self.stdout.write(f"Unchanged: {skipped_count}")
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))

    def _generate_normalized_value(self, enrichment):
        """
        Generate normalized_value from enrichment_data.

        Parameters
        ----------
        enrichment : TagEnrichment
            The enrichment instance

        Returns
        -------
        str
            Generated normalized value
        """
        if enrichment.enrichment_type == "verse":
            return self._generate_verse_normalized_value(enrichment)
        elif enrichment.enrichment_type == "date":
            return self._generate_date_normalized_value(enrichment)
        elif enrichment.enrichment_type == "authority_id":
            return self._generate_authority_id_normalized_value(enrichment)
        else:
            # For unknown types, keep the existing value
            return enrichment.normalized_value

    def _generate_verse_normalized_value(self, enrichment):
        """Generate normalized value for verse enrichments."""
        data = enrichment.enrichment_data
        book = data.get("book", "")

        # Get book display name from BOOK_CHOICES
        from twf.forms.tags.enrichment_forms import BibleVerseEnrichmentForm

        book_choices = dict(BibleVerseEnrichmentForm.BOOK_CHOICES)
        book_display = book_choices.get(book, book)
        if book_display:
            book_display = book_display.split(" / ")[0]  # Get English name

        chapter = data.get("chapter")

        # No chapter means entire book
        if not chapter or chapter == 0:
            return book_display

        # Chapter only
        verse_start = data.get("verse_start")
        verse_end = data.get("verse_end")

        if not verse_start:
            # Also check old format (single "verse" field)
            verse = data.get("verse")
            if verse:
                return f"{book_display} {chapter}:{verse}"
            return f"{book_display} {chapter}"

        # Verse range
        if verse_start == verse_end:
            return f"{book_display} {chapter}:{verse_start}"
        else:
            return f"{book_display} {chapter}:{verse_start}-{verse_end}"

    def _generate_date_normalized_value(self, enrichment):
        """Generate normalized value for date enrichments."""
        data = enrichment.enrichment_data
        # For dates, the EDTF format is already the normalized value
        return data.get("edtf", enrichment.normalized_value)

    def _generate_authority_id_normalized_value(self, enrichment):
        """Generate normalized value for authority ID enrichments."""
        # For authority IDs, use the variation as normalized value
        return enrichment.variation.strip()
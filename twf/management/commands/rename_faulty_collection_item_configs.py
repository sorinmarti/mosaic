"""Management command to normalize collection item configurations."""

from django.core.management import BaseCommand
from twf.models import CollectionItem


class Command(BaseCommand):
    """Management command to normalize collection item configurations."""

    help = 'Renames "parts" to "annotations" in collection items'

    def handle(self, *args, **options):
        items = CollectionItem.objects.filter(
            document_configuration__contains={"parts": []}
        )
        updated_count = 0

        for item in items:
            item.document_configuration["annotations"] = (
                item.document_configuration.pop("parts")
            )
            item.save(update_fields=["document_configuration"])
            updated_count += 1

        self.stdout.write(f"Successfully updated {updated_count} collection items.")

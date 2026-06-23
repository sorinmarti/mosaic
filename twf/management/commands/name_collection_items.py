"""Management command to set collection item titles based on annotations."""

from django.core.management.base import BaseCommand
from twf.models import CollectionItem


class Command(BaseCommand):
    """Management command to set collection item titles based on annotations."""

    help = (
        "Set collection item titles for a specific collection based "
        "on the first 100 characters of document_configuration['annotations'][0]"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "collection_id", type=int, help="ID of the collection to update items for."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without saving them.",
        )

    def handle(self, *args, **options):
        collection_id = options["collection_id"]
        dry_run = options["dry_run"]
        updated_count = 0

        # Fetch items in the specified collection
        collection_items = CollectionItem.objects.filter(collection_id=collection_id)

        if not collection_items.exists():
            self.stdout.write(
                self.style.WARNING(f"No items found for collection ID {collection_id}.")
            )
            return

        for item in collection_items:
            try:
                annotations = item.document_configuration.get("annotations", [])
                if not annotations:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping item {item.id}: No annotations found in document_configuration."
                        )
                    )
                    continue

                # Get the text and truncate it to 100 characters without cutting off words
                full_text = ""
                for anno in annotations:
                    if anno["type"] == "lyrics" or anno["type"] == "heading":
                        full_text = anno["text"]
                        break
                full_text = full_text.replace("\n", " ").replace(" ¶", " ").strip()
                if full_text.startswith("1.") or full_text.startswith("I."):
                    full_text = full_text[3:].strip()
                if full_text.startswith("1"):
                    full_text = full_text[1:].strip()
                if full_text.startswith("(1.)"):
                    full_text = full_text[4:].strip()

                full_text = full_text.replace("  ", " ")

                truncated_title = self._truncate_text(full_text, 100)
                if truncated_title.endswith("/"):
                    truncated_title = truncated_title[:-1].strip()

                if dry_run:
                    self.stdout.write(
                        f"[Dry Run] Item {item.id}: '{item.title}' -> '{truncated_title}'"
                    )
                else:
                    item.title = truncated_title
                    item.save()
                    self.stdout.write(
                        f"Updated Item {item.id}: '{item.title}' -> '{truncated_title}'"
                    )
                    updated_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing item {item.id}: {str(e)}")
                )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("Dry run completed. No changes were saved.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"{updated_count} collection item titles updated.")
            )

    def _truncate_text(self, text, limit):
        """
        Truncate text to the specified character limit without cutting off words.

        Args:
            text (str): The text to truncate.
            limit (int): The character limit.

        Returns:
            str: Truncated text.
        """
        if len(text) <= limit:
            return text

        truncated = text[:limit]
        if " " in truncated:
            # Find the last space and truncate there
            truncated = truncated[: truncated.rfind(" ")]
        return truncated

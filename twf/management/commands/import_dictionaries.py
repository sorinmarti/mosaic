"""Management command to import dictionaries from a CSV file."""

from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from twf.import_utils import import_dictionary_from_csv


class Command(BaseCommand):
    """Management command to import dictionaries from a CSV file."""

    help = "Imports dictionaries from a CSV file"

    def add_arguments(self, parser):
        """Add arguments to the command.

        Args:
            parser: The parser object

        Returns:
            None"""
        parser.add_argument("user", type=str, help="The importing user")
        parser.add_argument(
            "csv_file", type=str, help="The path to the CSV file to import"
        )

        parser.add_argument("--type", type=str, help="The type of the dictionary")
        parser.add_argument("--label", type=str, help="The label of the dictionary")

    def handle(self, *args, **options):
        """Handle the command."""
        csv_file = options["csv_file"]

        user = User.objects.get(username=options["user"])
        csv_path = Path(csv_file)
        if not csv_path.exists() or not csv_path.is_file():
            raise CommandError(f"The file {csv_file} does not exist.")

        try:
            import_dictionary_from_csv(
                csv_file, user, options["type"], options["label"]
            )
            self.stdout.write(
                self.style.SUCCESS("Successfully imported dictionaries from CSV.")
            )
        except Exception as e:
            raise CommandError(f"An error occurred: {str(e)}")

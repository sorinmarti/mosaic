"""Management command to check the integrity of a dictionary."""

from collections import Counter
from django.core.management import BaseCommand
from twf.models import Project, Variation


class Command(BaseCommand):
    """Management command to import dictionaries from a CSV file."""

    help = "Imports dictionaries from a CSV file"

    def add_arguments(self, parser):
        """Add arguments to the command"""
        parser.add_argument(
            "project_id", type=int, help="The project id to create the collection from"
        )

    def handle(self, *args, **options):
        """Handle the command"""
        print("Trying to create a song collection...")
        project = Project.objects.get(pk=options["project_id"])

        for dictionary in project.selected_dictionaries.all():
            # Flat list of all variations in the dictionary

            all_variations_in_dictionary = Variation.objects.filter(
                entry__dictionary=dictionary
            ).values_list("variation", flat=True)
            # Check if there ary duplicate variations
            # Count occurrences of each variation
            variation_counts = Counter(all_variations_in_dictionary)

            # Identify duplicates
            duplicate_variations = [
                variation for variation, count in variation_counts.items() if count > 1
            ]

            print(
                f"Dictionary {dictionary} has {len(duplicate_variations)} duplicate variations."
            )

"""Management command to clean metadata from all pages in a project."""

from django.contrib.auth.models import User
from django.core.management import BaseCommand

from twf.models import Project, Page


class Command(BaseCommand):
    """Management command to clean metadata from all pages in a project."""

    help = "Imports PAGE metadata from a CSV file"

    def add_arguments(self, parser):
        """Add arguments to the command"""
        parser.add_argument(
            "project_id", type=int, help="The project id to create the collection from"
        )
        parser.add_argument(
            "user_id", type=int, help="The user id to create the collection for"
        )

    def handle(self, *args, **options):
        """Handle the command"""
        print("Trying to clean data...")

        project = Project.objects.get(pk=options["project_id"])
        user = User.objects.get(pk=options["user_id"])

        # Read data from file (must be a list of json objects)
        pages = Page.objects.filter(document__project=project)
        for p in pages:
            p.metadata = {}
            p.save(current_user=user)

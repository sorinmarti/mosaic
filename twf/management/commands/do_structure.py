"""Django management command to structure a project."""

from django.core.management import BaseCommand
from twf.tasks.structure_tasks import extract_zip_export_task


class Command(BaseCommand):
    """Management command to import dictionaries from a CSV file."""

    help = "Imports dictionaries from a CSV file"

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
        print("Start structuring...")
        project_id = options["project_id"]
        user_id = options["user_id"]
        task_result = extract_zip_export_task.delay(project_id, user_id)

        self.stdout.write(
            self.style.SUCCESS(f"Task triggered with ID: {task_result.id}")
        )

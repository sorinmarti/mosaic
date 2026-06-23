"""Management command to load metadata from a JSON file."""

import json
from django.core.management.base import BaseCommand, CommandError
from twf.models import Project, Document, Page


class Command(BaseCommand):
    """Management command to load metadata from a JSON file."""

    help = "Load metadata from a JSON file and save it to the database"

    def add_arguments(self, parser):
        # Define the arguments that can be passed to the command
        parser.add_argument(
            "project_id", type=int, help="The ID of the project to load metadata for"
        )
        parser.add_argument(
            "data_target_type",
            choices=["document", "page"],
            help="Specify whether the data is for documents or pages",
        )
        parser.add_argument(
            "json_data_key",
            type=str,
            help="The key in the JSON data that matches the document or page",
        )
        parser.add_argument(
            "data_file", type=str, help="The path to the JSON file containing the data"
        )
        parser.add_argument(
            "match_to_field",
            choices=["dbid", "docid"],
            help="The field to match the JSON data with the database records",
        )

    def handle(self, *args, **options):
        project_id = options["project_id"]
        data_target_type = options["data_target_type"]
        json_data_key = options["json_data_key"]
        data_file = options["data_file"]
        match_to_field = options["match_to_field"]

        # Load the project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project with id {project_id} does not exist")

        # Open and read the JSON file
        try:
            with open(data_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            raise CommandError(f"File {data_file} not found")
        except json.JSONDecodeError:
            raise CommandError(f"Failed to parse JSON from {data_file}")

        # Process each item in the JSON data
        for item in data:
            id_value_of_item = item.get(json_data_key)

            if not id_value_of_item:
                self.stdout.write(
                    self.style.WARNING(f"Skipping item without {json_data_key}")
                )
                continue

            if data_target_type == "document":
                try:
                    document = None
                    if match_to_field == "dbid":
                        document = Document.objects.get(
                            project=project, id=id_value_of_item
                        )
                    elif match_to_field == "docid":
                        document = Document.objects.get(
                            project=project, document_id=id_value_of_item
                        )

                    if document:
                        document.metadata["import"] = item
                        document.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Saved metadata for document {document}"
                            )
                        )

                except Document.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Document with {match_to_field} "
                            f"{id_value_of_item} does not exist."
                        )
                    )

            elif data_target_type == "page":
                try:
                    page = None
                    if match_to_field == "dbid":
                        page = Page.objects.get(
                            document__project=project, id=id_value_of_item
                        )
                    elif match_to_field == "docid":
                        page = Page.objects.get(
                            document__project=project, dbid=id_value_of_item
                        )

                    if page:
                        page.metadata["import"] = item
                        page.save()
                        self.stdout.write(
                            self.style.SUCCESS(f"Saved metadata for page {page}")
                        )

                except Page.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Page with {match_to_field} "
                            f"{id_value_of_item} does not exist."
                        )
                    )

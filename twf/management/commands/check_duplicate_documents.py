""" Management command to check for duplicate documents in a project. """

from django.core.management.base import BaseCommand
from twf.models import Document, CollectionItem
from django.db.models import Count


class Command(BaseCommand):
    """Management command to check for duplicate documents in a project."""

    help = (
        "Check for duplicate documents in a specific project and "
        "provide detailed information. Optionally delete duplicates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "project_id",
            type=int,
            help="ID of the project to check for duplicate documents.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete duplicate documents, keeping only the first document for each duplicate group.",
        )

    def handle(self, *args, **options):
        """Handle the management command."""
        project_id = options["project_id"]
        delete_duplicates = options["delete"]

        # Step 1: Filter documents by project and find duplicates by `document_id`
        duplicates = (
            Document.objects.filter(project_id=project_id)
            .values("document_id")
            .annotate(doc_count=Count("id"))
            .filter(doc_count__gt=1)
        )

        if not duplicates:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No duplicate documents found for project ID {project_id}."
                )
            )
            return

        self.stdout.write(
            f"Found {len(duplicates)} duplicate document(s) in project ID {project_id}.\n"
        )

        for duplicate in duplicates:
            document_id = duplicate["document_id"]

            # Fetch all documents with this `document_id` in the project
            duplicate_docs = Document.objects.filter(
                project_id=project_id, document_id=document_id
            ).order_by("id")

            self.stdout.write(
                self.style.WARNING(f"Duplicate Document ID: {document_id}")
            )

            # Step 2: Check if any document is used in a collection item
            is_used_in_collection = CollectionItem.objects.filter(
                document__document_id=document_id
            ).exists()
            if is_used_in_collection:
                self.stdout.write(
                    self.style.WARNING("This document is used in a collection item.")
                )
            else:
                self.stdout.write("This document is not used in any collection item.")

            # Step 3: Display differences between documents
            self.stdout.write("Document Differences:")
            base_doc = duplicate_docs.first()

            for doc in duplicate_docs:
                differences = self._compare_documents(base_doc, doc)
                if differences:
                    self.stdout.write(f"  Differences with Document ID {doc.id}:")
                    for field, diff in differences.items():
                        self.stdout.write(f"    {field}: {diff}")
                else:
                    self.stdout.write(f"  No differences with Document ID {doc.id}.")

            # Step 4: Optionally delete duplicates
            if delete_duplicates:
                self._delete_duplicates(duplicate_docs)

            self.stdout.write("\n")

        if delete_duplicates:
            self.stdout.write(
                self.style.SUCCESS("Duplicate document deletion completed.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Duplicate document check completed."))

    def _compare_documents(self, doc1, doc2):
        """
        Compare two documents and return a dictionary of differences.

        Args:
            doc1 (Document): The first document.
            doc2 (Document): The second document.

        Returns:
            dict: A dictionary with field names as keys and their differences as values.
        """
        differences = {}
        fields_to_compare = [
            "title",
            "metadata",
            "last_parsed_at",
            "is_parked",
            "workflow_remarks",
        ]

        for field in fields_to_compare:
            value1 = getattr(doc1, field, None)
            value2 = getattr(doc2, field, None)
            if value1 != value2:
                differences[field] = {"doc1": value1, "doc2": value2}

        return differences

    def _delete_duplicates(self, duplicate_docs):
        """
        Delete all but the first document in a duplicate group.

        Args:
            duplicate_docs (QuerySet): The queryset of duplicate documents.
        """
        base_doc = duplicate_docs.first()  # Keep the first document
        to_delete = duplicate_docs.exclude(id=base_doc.id)

        self.stdout.write(
            f"Deleting {to_delete.count()} duplicate document(s), keeping Document ID {base_doc.id}."
        )

        # Perform deletion
        to_delete.delete()

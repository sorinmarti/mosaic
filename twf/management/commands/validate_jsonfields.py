"""
Management command to validate all JSONFields in the database.

Usage:
    python manage.py validate_jsonfields
    python manage.py validate_jsonfields --model Project
    python manage.py validate_jsonfields --fix
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from twf.models import (
    Project,
    UserProfile,
    Document,
    Page,
    PageTag,
    DictionaryEntry,
    CollectionItem,
)
from twf.utils.jsonfield_validators import validate_all_jsonfields


class Command(BaseCommand):
    help = "Validate all JSONFields in the TWF database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            help="Validate only specific model (Project, Document, Page, etc.)",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Attempt to fix common issues (WARNING: modifies data)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output for each record",
        )

    def handle(self, *args, **options):
        model_name = options.get("model")
        fix_issues = options.get("fix")
        verbose = options.get("verbose")

        self.stdout.write(
            self.style.SUCCESS("=" * 70)
        )
        self.stdout.write(
            self.style.SUCCESS("TWF JSONField Validation")
        )
        self.stdout.write(
            self.style.SUCCESS("=" * 70)
        )

        # Determine which models to validate
        if model_name:
            model_map = {
                "Project": Project,
                "UserProfile": UserProfile,
                "Document": Document,
                "Page": Page,
                "PageTag": PageTag,
                "DictionaryEntry": DictionaryEntry,
                "CollectionItem": CollectionItem,
            }
            if model_name not in model_map:
                self.stdout.write(
                    self.style.ERROR(f"Unknown model: {model_name}")
                )
                self.stdout.write(
                    f"Available models: {', '.join(model_map.keys())}"
                )
                return

            models_to_validate = [(model_name, model_map[model_name])]
        else:
            models_to_validate = [
                ("Project", Project),
                ("UserProfile", UserProfile),
                ("Document", Document),
                ("Page", Page),
                ("PageTag", PageTag),
                ("DictionaryEntry", DictionaryEntry),
                ("CollectionItem", CollectionItem),
            ]

        # Validation results
        total_records = 0
        total_errors = 0
        models_with_errors = []

        # Validate each model
        for model_name, model_class in models_to_validate:
            self.stdout.write(f"\n{model_name}:")
            self.stdout.write("-" * 70)

            records = model_class.objects.all()
            count = records.count()
            total_records += count

            if count == 0:
                self.stdout.write(
                    self.style.WARNING(f"  No {model_name} records found")
                )
                continue

            errors_in_model = 0
            records_with_errors = []

            for record in records:
                errors = validate_all_jsonfields(record)

                if errors:
                    errors_in_model += 1
                    total_errors += 1
                    record_id = getattr(record, "id", "?")
                    records_with_errors.append((record_id, errors))

                    if verbose:
                        self.stdout.write(
                            self.style.ERROR(f"  ✗ {model_name} #{record_id}")
                        )
                        for field, field_errors in errors.items():
                            self.stdout.write(f"    Field: {field}")
                            for error in field_errors:
                                self.stdout.write(f"      - {error}")

            # Summary for this model
            if errors_in_model == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ All {count} {model_name} records valid"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ {errors_in_model}/{count} {model_name} records have errors"
                    )
                )
                models_with_errors.append({
                    "model": model_name,
                    "count": errors_in_model,
                    "records": records_with_errors
                })

        # Final summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total records checked: {total_records}")
        self.stdout.write(f"Records with errors: {total_errors}")
        self.stdout.write(f"Records valid: {total_records - total_errors}")

        if total_errors > 0:
            self.stdout.write(
                self.style.ERROR(f"\n{total_errors} records have validation errors")
            )

            # Show summary of errors by model
            self.stdout.write("\nErrors by model:")
            for model_info in models_with_errors:
                self.stdout.write(
                    f"  - {model_info['model']}: {model_info['count']} errors"
                )

            if fix_issues:
                self.stdout.write(
                    self.style.WARNING("\n--fix flag specified, but auto-fix not yet implemented")
                )
                self.stdout.write(
                    "Please review errors manually or create a custom data migration"
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ All JSONFields are valid!")
            )

        self.stdout.write("")
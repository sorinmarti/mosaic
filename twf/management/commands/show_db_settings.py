"""Management command to display database settings."""

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    """Management command to display database settings."""

    help = "Displays database settings"

    def handle(self, *args, **kwargs):
        db_settings = settings.DATABASES
        if db_settings:
            self.stdout.write(self.style.SUCCESS("Database Settings:"))
            for alias, config in db_settings.items():
                self.stdout.write(f"\nAlias: {alias}")
                for key, value in config.items():
                    # Mask passwords for security
                    """if key == 'PASSWORD' and value:
                    value = '*' * len(value)"""
                    self.stdout.write(f"  {key}: {value}")
        else:
            self.stdout.write(self.style.ERROR("No database settings found!"))

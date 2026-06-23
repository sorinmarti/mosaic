"""Tests for the twf app."""

from django.test import TestCase

from twf.models import Document, Project, User


class TestTagAssigner(TestCase):
    """Test the tag_assigner function."""

    def test_tag_assigner(self):
        """Test the tag_assigner function."""
        self.user = User.objects.create_user(
            username="testuser", password="password123", email="testuser@example.com"
        )
        self.userprofile = self.user.profile

        self.project = Project(
            title="Test Project",
            collection_id="test_collection",
            description="A test project",
            owner=self.userprofile,
        )
        self.project.save(current_user=self.user)

        doc_instance, created = Document.objects.get_or_create(
            project=self.project,
            document_id="12345",
            created_by=self.user,
            modified_by=self.user,
        )

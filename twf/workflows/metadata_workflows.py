"""
Metadata Workflow Management
=============================

This module provides functions for managing metadata-related workflows.
"""

from django.shortcuts import redirect
from twf.workflows.workflow_utils import end_workflow
from twf.views.views_base import TWFView


def end_metadata_document_review_workflow(request):
    """End/cancel the current document metadata review workflow."""
    project = TWFView.s_get_project(request)
    user = request.user

    end_workflow(request, project, user, "review_metadata_documents", "twf:metadata_review_documents")

    return redirect("twf:metadata_review_documents")


def end_metadata_page_review_workflow(request):
    """End/cancel the current page metadata review workflow."""
    project = TWFView.s_get_project(request)
    user = request.user

    end_workflow(request, project, user, "review_metadata_pages", "twf:metadata_review_pages")

    return redirect("twf:metadata_review_pages")
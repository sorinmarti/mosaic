"""Forms for tag workflow management."""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Div, HTML
from django import forms

from twf.utils.tags_utils import get_all_tag_types, get_enrichment_types
from twf.workflows.tag_workflows import (
    get_available_tag_count,
    get_available_date_count,
)


class StartTagGroupingWorkflowForm(forms.Form):
    """Form to start a tag grouping workflow."""

    tag_type = forms.ChoiceField(
        label="Tag Type",
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Select the type of tags to group in this workflow.",
    )

    batch_size = forms.IntegerField(
        label="Batch Size (number of unique tags)",
        min_value=1,
        max_value=100,
        initial=10,
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of unique tag variations to process in this workflow session. "
        "Note: All identical tags are grouped together automatically.",
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required.")

        # Get all available non-date tag types
        tag_types = get_all_tag_types(project)

        # Build choices with availability counts
        choices = []
        for tag_type in tag_types:
            count = get_available_tag_count(project, tag_type)
            choices.append(
                (tag_type, f"{tag_type.title()} ({count} unique tags available)")
            )

        if not choices:
            choices = [("", "No tag types available")]

        self.fields["tag_type"].choices = choices

        # Set initial batch_size from project configuration
        workflow_def = project.get_workflow_definition("review_tags_grouping")
        self.fields["batch_size"].initial = workflow_def.get("batch_size", 10)

        self.helper = FormHelper()
        self.helper.method = "post"
        self.helper.form_id = "start-tag-grouping-workflow-form"
        self.helper.layout = Layout(
            "tag_type",
            "batch_size",
            Div(
                Submit(
                    "start_workflow", "Start Workflow", css_class="btn btn-dark"
                ),
                css_class="mt-3",
            ),
        )


class StartDateNormalizationWorkflowForm(forms.Form):
    """Form to start a date normalization workflow."""

    batch_size = forms.IntegerField(
        label="Batch Size (number of date tags)",
        min_value=1,
        max_value=100,
        initial=20,
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of date tags to normalize in this workflow session.",
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required.")

        # Set initial batch_size from project configuration
        workflow_def = project.get_workflow_definition("review_tags_dates")
        self.fields["batch_size"].initial = workflow_def.get("batch_size", 20)

        # Get available date count for display
        available_count = get_available_date_count(project)

        self.helper = FormHelper()
        self.helper.method = "post"
        self.helper.form_id = "start-date-normalization-workflow-form"
        self.helper.layout = Layout(
            Div(
                HTML("<h5>Start Date Normalization Workflow</h5>"),
                HTML(
                    f'<p class="text-muted">{available_count} date tags available for normalization</p>'
                ),
                "batch_size",
                Div(
                    Submit(
                        "start_workflow", "Start Workflow", css_class="btn btn-primary"
                    ),
                    css_class="mt-3",
                ),
                css_class="card card-body mb-3",
            )
        )


class StartEnrichmentWorkflowForm(forms.Form):
    """Form to start a generic tag enrichment workflow."""

    tag_type = forms.ChoiceField(
        label="Tag Type",
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Select the type of tags to enrich in this workflow.",
    )

    batch_size = forms.IntegerField(
        label="Batch Size (number of tags)",
        min_value=1,
        max_value=100,
        initial=20,
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of tags to enrich in this workflow session.",
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not project:
            raise ValueError("Project is required.")

        self.project = project

        # Get enrichment types from configuration
        enrichment_types = get_enrichment_types(project)

        # Build choices with availability counts
        from twf.models import PageTag

        choices = []
        for tag_type, config in enrichment_types.items():
            from django.db.models import Q
            count = PageTag.objects.filter(
                page__document__project=project,
                page__is_ignored=False,
                variation_type=tag_type,
                tag_enrichment_entry__isnull=True,
                is_parked=False,
                is_reserved=False,
            ).filter(Q(enrichment__isnull=True) | Q(enrichment={})).count()

            workflow_title = config.get(
                "workflow_title", f"{tag_type.title()} Enrichment"
            )
            choices.append((tag_type, f"{workflow_title} ({count} tags available)"))

        if not choices:
            choices = [("", "No enrichment types configured")]

        self.fields["tag_type"].choices = choices

        # Set initial batch_size from project configuration
        workflow_def = project.get_workflow_definition("review_tags_enrichment")
        self.fields["batch_size"].initial = workflow_def.get("batch_size", 20)

        self.helper = FormHelper()
        self.helper.method = "post"
        self.helper.form_id = "start-enrichment-workflow-form"
        self.helper.layout = Layout(
            "tag_type",
            "batch_size",
            Div(
                Submit(
                    "start_workflow", "Start Workflow", css_class="btn btn-dark"
                ),
                css_class="mt-3",
            ),
        )

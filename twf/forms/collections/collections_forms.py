from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Div, Submit
from django import forms
from django.db.models import Subquery
from django.urls import reverse_lazy
from django_select2.forms import Select2Widget

from twf.forms.twf_form_widgets import JSONAnnotationsWidget
from twf.models import Collection, Document, CollectionItem


class CollectionCreateForm(forms.ModelForm):
    """
    Form for creating a new collection with options for automatic item creation.
    """

    creation_routine = forms.ChoiceField(
        choices=[
            ("manual", "Manual Creation"),
            ("an_item_per_document", "Create a collection item per document"),
            ("an_item_per_page", "Create a collection item per page"),
            ("structure_tag_based", "Based on structure tags"),
        ],
        required=True,
        label="Creation Routine",
    )

    structure_tag_filter = forms.CharField(
        required=False,
        label="Structure Tag Filter",
        help_text="For the document- and page-based and structure-tag-based creation routines, you can specify a "
        "comma-separated list of structure tags to filter (=ignore) when creating collection items.",
    )

    skip_empty_types = forms.BooleanField(
        required=False,
        label="Skip empty types",
        help_text="Skip empty structure tag types when creating collection items.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        creation_routine_info = """
        <div class="alert alert-info" id="creationRoutineInfo">
            <p class="mb-0"><strong>Title</strong></p>
            <p>Text</p>
        </div>
        """

        self.helper.layout = Layout(
            Row(
                Column("title", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("creation_routine", css_class="form-group col-6 mb-3"),
                Column(HTML(creation_routine_info), css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("structure_tag_filter", css_class="form-group col-6 mb-3"),
                Column("skip_empty_types", css_class="form-group col-6 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("description", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Div(
                    Submit("submit", "Create Collection", css_class="btn btn-dark"),
                    css_class="text-end pt-3",
                )
            ),
        )

    class Meta:
        model = Collection
        fields = ["title", "description"]


class CollectionUpdateForm(forms.ModelForm):
    """
    Form for updating an existing collection's title and description.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the form and set up the crispy forms layout."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        self.helper.layout = Layout(
            Row(
                Column("title", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("description", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Div(
                    Submit("submit", "Save Collection", css_class="btn btn-dark"),
                    css_class="text-end pt-3",
                )
            ),
        )

    class Meta:
        model = Collection
        fields = ["title", "description"]


class CollectionItemForm(forms.ModelForm):
    """
    Base form for collection items with fields for title,
    document configuration, and review notes.
    """

    class Meta:
        model = CollectionItem
        fields = ["title", "document_configuration", "review_notes"]
        widgets = {
            "document_configuration": JSONAnnotationsWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            # Update the widget's attributes to include the pk
            self.fields["document_configuration"].widget.attrs.update(
                {"item_pk": str(self.instance.pk)}
            )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        self.helper.layout = Layout(
            Row(
                Column(*self.get_left_part(), css_class="col-8"),
                Column(*self.get_right_part(), css_class="col-4"),
            )
        )

    def get_left_part(self):
        """
        Get the left column layout components for the form.

        Returns:
            list: List of Row/Column crispy forms layout objects for the left side
        """
        left_part = [
            Row(
                Column("title", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column("document_configuration", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
        ]
        return left_part

    def get_right_part(self):
        """
        Get the right column layout components for the form.

        Returns:
            list: Empty list (no right side components in base form)
        """
        return []

    def get_option_a_button(self, view, label, color="dark"):
        """
        Generate an HTML button link for a specific view.

        Args:
            view: Django view name to generate URL for
            label: Button text label
            color: Bootstrap color class (default: "dark")

        Returns:
            HTML: Crispy forms HTML object with the button link
        """
        if self.instance.pk:
            url = reverse_lazy(view, kwargs={"pk": self.instance.pk})
        else:
            url = "#"
        return HTML(
            f'<a href="{url}" class="btn btn-{color}" style="width: 100%">{label}</a>'
        )

    def get_option_info(self, text):
        """
        Generate an HTML info paragraph.

        Args:
            text: Text content for the info paragraph

        Returns:
            HTML: Crispy forms HTML object with the paragraph
        """
        return HTML(f'<p class="mt-3">{text}</p>')

    def get_status_display(self):
        """
        Get the Bootstrap color class for the instance status.

        Returns:
            str: Bootstrap color class ("info", "success", "warning", or "dark")
        """
        status = self.instance.status
        display = "dark"

        if status == "open":
            display = "info"
        elif status == "reviewed":
            display = "success"
        elif status == "faulty":
            display = "warning"

        return display


class CollectionItemUpdateForm(CollectionItemForm):
    """
    Form for updating a collection item with options to change status,
    view document, copy, or delete.
    """

    class Meta:
        model = CollectionItem
        fields = ["title", "document_configuration", "review_notes"]
        widgets = {
            "document_configuration": JSONAnnotationsWidget(),
        }

    def get_right_part(self):
        status_span = '<span class="badge bg-%s">%s</span>' % (
            self.get_status_display(),
            self.instance.status,
        )

        if self.instance and self.instance.pk:
            copy_item_url = reverse_lazy(
                "twf:collection_item_copy", kwargs={"pk": self.instance.pk}
            )
            delete_item_url = reverse_lazy(
                "twf:collection_item_delete", kwargs={"pk": self.instance.pk}
            )
            go_back_url = reverse_lazy(
                "twf:collection_item_view", kwargs={"pk": self.instance.pk}
            )
            if self.instance.document:
                view_doc_url = reverse_lazy(
                    "twf:view_document", kwargs={"pk": self.instance.document.pk}
                )
            else:
                view_doc_url = "#"
        else:
            copy_item_url = "#"
            delete_item_url = "#"
            go_back_url = "#"
            view_doc_url = "#"

        right_part = [
            Row(
                Column(
                    HTML(
                        "<strong>Collection Item Status</strong> "
                        f"(Current status: {status_span})"
                    ),
                    css_class="form-group col-12 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Open is the default state for a collection item."
                    ),
                    css_class="form-group col-6 mb-1",
                ),
                Column(
                    self.get_option_a_button(
                        "twf:collection_item_status_open", "Set Status Open", "info"
                    ),
                    css_class="form-group col-6 mb-1",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Reviewed is the state for a collection item that has been checked."
                    ),
                    css_class="form-group col-6 mb-1",
                ),
                Column(
                    self.get_option_a_button(
                        "twf:collection_item_status_reviewed",
                        "Set Status Reviewed",
                        "success",
                    ),
                    css_class="form-group col-6 mb-1",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Faulty is the state for a collection item that has been checked and is faulty."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    self.get_option_a_button(
                        "twf:collection_item_status_faulty",
                        "Set Status Faulty",
                        "warning",
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    HTML("<strong>Collection Item Options</strong>"),
                    css_class="form-group col-12 mt-3 mb-0",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Connection items are connected to a document item if possible. "
                        "As long as all the annotations stem"
                        " from the same document, the connections will be kept. This does not "
                        "work for structure-tag-based collection items."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    HTML(
                        f'<a href="{view_doc_url}" class="btn btn-dark" style="width: 100%">View Document</a>'
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info("You can create a copy of this item."),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    HTML(
                        f'<a href="{copy_item_url}" class="btn btn-dark" style="width: 100%">Copy This Item</a>'
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info("Deleting the item cannot be undone."),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    HTML(
                        f'<a href="{delete_item_url}" class="btn btn-danger" style="width: 100%">Delete This Item</a>'
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    HTML("<strong>Notes on Item</strong>"),
                    css_class="form-group col-12 mt-3 mb-0",
                ),
                css_class="row form-row",
            ),
            Row(
                Column("review_notes", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column(
                    HTML("<strong>Save Item</strong>"),
                    css_class="form-group col-12 mt-3 mb-0",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Save the collection item if you changed the title or the notes."
                        "Status and annotation changes are saved instantly."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    Submit(
                        "submit",
                        "Save Collection Item",
                        css_class="btn btn-dark",
                        style="width: 100%",
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info("Go back to viewing the collection item."),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    HTML(
                        f'<a href="{go_back_url}" class="btn btn-dark" style="width: 100%">Go Back</a>'
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
        ]
        return right_part


class CollectionItemReviewForm(CollectionItemForm):
    """
    Form for reviewing a collection item with options to mark as reviewed, faulty, copy, or delete.
    """

    class Meta:
        """
        Metaclass for CollectionItemReviewForm.
        """
        model = CollectionItem
        fields = ["title", "document_configuration", "review_notes"]
        widgets = {
            "document_configuration": JSONAnnotationsWidget(
                attrs={"redirect_view": "twf:collections_review"}
            ),
        }

    def get_right_part(self):
        if self.instance and self.instance.pk:
            copy_item_url = reverse_lazy(
                "twf:collection_item_copy", kwargs={"pk": self.instance.pk}
            )
            copy_item_url += "?redirect_to_view=twf:collections_review"

            delete_item_url = reverse_lazy(
                "twf:collection_item_delete", kwargs={"pk": self.instance.pk}
            )
            delete_item_url += "?redirect_to_view=twf:collections_review"
        else:
            copy_item_url = "#"
            delete_item_url = "#"

        right_part = [
            Row(
                Column(
                    HTML("<strong>Collection Item Review Options</strong>"),
                    css_class="form-group col-12 mt-3 mb-0",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "You can create a copy of this item. Unsaved changes will be lost."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    HTML(
                        f'<a href="{copy_item_url}" class="btn btn-dark" style="width: 100%">Copy This Item</a>'
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Save changes to title and notes before updating annotations. "
                        "Annotation changes are saved instantly. Title and notes also get saved "
                        "when setting the status to reviewed or faulty."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    Submit(
                        "submit-u",
                        "Save Item",
                        css_class="btn btn-dark",
                        style="width: 100%",
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    HTML("<strong>Notes on Item</strong>"),
                    css_class="form-group col-12 mt-3 mb-0",
                ),
                css_class="row form-row",
            ),
            Row(
                Column("review_notes", css_class="form-group col-12 mb-3"),
                css_class="row form-row",
            ),
            Row(
                Column(
                    HTML("<strong>Save Item and continue Review Workflow</strong>"),
                    css_class="form-group col-12 mt-3 mb-0",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Delete this item and continue with the next item."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    Submit(
                        "submit-d",
                        "Delete This Item",
                        css_class="btn btn-danger",
                        style="width: 100%",
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Set this item as reviewed and continue with the next item."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    Submit(
                        "submit-f",
                        "Mark as faulty",
                        css_class="btn btn-warning",
                        style="width: 100%",
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
            Row(
                Column(
                    self.get_option_info(
                        "Set this item as reviewed and continue with the next item."
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                Column(
                    Submit(
                        "submit-r",
                        "Mark as reviewed",
                        css_class="btn btn-success",
                        style="width: 100%",
                    ),
                    css_class="form-group col-6 mb-3",
                ),
                css_class="row form-row",
            ),
        ]
        return right_part


class CollectionAddDocumentForm(forms.Form):
    """Form for adding a document to a collection."""

    document = forms.ModelChoiceField(
        label="Document",
        required=True,
        help_text="Please select the document to add to the collection.",
        widget=Select2Widget(attrs={"style": "width: 100%;"}),
        queryset=Document.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        collection = kwargs.pop("collection")
        super().__init__(*args, **kwargs)

        if collection:
            # Filter documents that are not in the specified collection
            self.fields["document"].queryset = Document.objects.filter(
                project=collection.project
            ).exclude(
                id__in=Subquery(
                    CollectionItem.objects.filter(collection=collection).values(
                        "document_id"
                    )
                )
            )

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form form-control"

        self.helper.layout = Layout(
            Row(Column("document", css_class="form-group"), css_class="row form-row"),
            Div(
                Submit("submit", "Add Document", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

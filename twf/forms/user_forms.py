"""Forms for the twf app."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Column, Row, Div


class LoginForm(AuthenticationForm):
    """Form for logging in users."""

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "username",
            "password",
            Div(
                Submit("submit", "Login", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class ChangePasswordForm(PasswordChangeForm):
    """Form for changing the password of a user."""

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            "old_password",
            "new_password1",
            "new_password2",
            Div(
                Submit("submit", "Change Password", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class CreateUserForm(forms.ModelForm):
    """Form for managing users."""

    class Meta:
        """Meta class for the form."""

        model = User
        fields = ["username", "email"]
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Username"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)

        self.fields["email"].required = True

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("username", css_class="form-group col-6 mb-0"),
                Column("email", css_class="form-group col-6 mb-0"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Create User", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )


class UserProfileForm(forms.ModelForm):
    """Form for editing the profile of a user."""

    class Meta:
        """Meta class for the form."""

        model = User
        fields = ["username", "first_name", "last_name", "email"]

    orcid = forms.CharField(max_length=19, required=False)
    affiliation = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)

        self.fields["orcid"].initial = self.instance.profile.orc_id
        self.fields["affiliation"].initial = self.instance.profile.affiliation

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Row(
                Column("username", css_class="form-group col-6 mb-0"),
                Column("email", css_class="form-group col-6 mb-0"),
                css_class="row form-row",
            ),
            Row(
                Column("first_name", css_class="form-group col-6 mb-0"),
                Column("last_name", css_class="form-group col-6 mb-0"),
                css_class="row form-row",
            ),
            Row(
                Column("orcid", css_class="form-group col-6 mb-0"),
                Column("affiliation", css_class="form-group col-6 mb-0"),
                css_class="row form-row",
            ),
            Div(
                Submit("submit", "Save Changes", css_class="btn btn-dark"),
                css_class="text-end pt-3",
            ),
        )

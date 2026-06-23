"""Views for CRUD operations on users."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, get_object_or_404
from django.utils.crypto import get_random_string

from twf.permissions import check_permission
from twf.utils.mail_utils import send_reset_email
from twf.views.views_base import get_referrer_or_default

User = get_user_model()


def activate_user(request, pk):
    """Activate a user account."""
    # Check system.edit permission - staff/superusers can manage users
    if not check_permission(request.user, "system.edit", None):
        messages.error(request, "You do not have permission to manage users.")
        return redirect("twf:home")

    # Get the user to activate
    user = get_object_or_404(User, pk=pk)

    # Activate the user
    user.is_active = True
    user.save()

    messages.success(
        request, f"User '{user.username}' has been activated successfully."
    )
    return get_referrer_or_default(request, default="twf:twf_user_management")


def deactivate_user(request, pk):
    """Deactivate a user account."""
    # Check system.edit permission - staff/superusers can manage users
    if not check_permission(request.user, "system.edit", None):
        messages.error(request, "You do not have permission to manage users.")
        return redirect("twf:home")

    # Get the user to deactivate
    user = get_object_or_404(User, pk=pk)

    # Cannot deactivate yourself
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return get_referrer_or_default(request, default="twf:twf_user_management")

    # Deactivate the user
    user.is_active = False

    # Clear permissions when deactivating
    if hasattr(user, "profile"):
        user.profile.permissions = {}
        user.profile.save()

    user.save()

    messages.success(
        request, f"User '{user.username}' has been deactivated successfully."
    )
    return get_referrer_or_default(request)


def delete_user(request, pk):
    """Delete a user."""
    # Check system.manage permission - only superusers/staff can delete users
    if not check_permission(request.user, "system.manage", None):
        messages.error(request, "Only administrators can delete users.")
        return redirect("twf:home")

    # Get the user to delete
    user = get_object_or_404(User, pk=pk)

    # Cannot delete yourself
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return get_referrer_or_default(request, default="twf:twf_user_management")

    # Check if the user owns any projects
    if hasattr(user, "profile") and user.profile.owned_projects.exists():
        messages.error(
            request,
            f"Cannot delete user '{user.username}' because they own projects. "
            "Transfer project ownership first or delete their projects.",
        )
        return get_referrer_or_default(request, default="twf:twf_user_management")

    # Store username for confirmation message
    username = user.username

    try:
        # Delete the user
        user.delete()
        messages.success(request, f"User '{username}' has been deleted successfully.")
    except Exception as e:
        messages.error(request, f"Error deleting user: {str(e)}")

    return get_referrer_or_default(request, default="twf:twf_user_management")


def reset_password(request, pk):
    """Reset a user's password and send them a new one."""
    # Check system.edit permission - staff/superusers can reset passwords
    if not check_permission(request.user, "system.edit", None):
        messages.error(request, "You do not have permission to reset passwords.")
        return redirect("twf:home")

    # Get the user to reset password for
    user = get_object_or_404(User, pk=pk)

    # Generate new password
    new_password = get_random_string(length=10)

    try:
        # Set and save the new password
        user.set_password(new_password)
        user.save()

        # Send email with new password
        if user.email:
            sent = send_reset_email(user.email, user.username, new_password)
            if sent:
                messages.success(
                    request,
                    f"Password for '{user.username}' has been reset. A new password has been sent to their email.",
                )
            else:
                messages.error(
                    request,
                    f"Password for '{user.username}' has been reset, but there was an error sending the email.",
                )
        else:
            messages.warning(
                request,
                f"Password for '{user.username}' has been reset to '{new_password}', but they have no email address.",
            )
    except Exception as e:
        messages.error(request, f"Error resetting password: {str(e)}")

    return get_referrer_or_default(request, default="twf:twf_user_management")

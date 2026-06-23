"""
Module: mail_utils

This module handles email notifications for user account management in TWF.
It includes functions to send welcome emails and password reset emails.

Functions:
    - send_welcome_email(user_email, username, temp_password): Sends a welcome email with login details.
    - send_reset_email(user_email, username, temp_password): Sends a password reset email with a temporary password.
"""

import logging

from django.core.mail import send_mail
from transkribusWorkflow.settings import DEFAULT_FROM_EMAIL

logger = logging.getLogger(__name__)


def send_welcome_email(user_email, username, temp_password):
    """
    Sends a welcome email to a new user with their initial login credentials.

    Parameters:
        user_email (str): The recipient's email address.
        username (str): The user's username.
        temp_password (str): A temporary password assigned to the user.
    """
    subject = "Welcome to TWF - Your Account Details"
    message = (
        f"Dear {username},\n\n"
        "Welcome to TWF! We are excited to have you on board.\n\n"
        f"Here are your initial login credentials:\n"
        f"Username: {username}\n"
        f"Temporary Password: {temp_password}\n\n"
        "Please log in and change your password as soon as possible.\n\n"
        "Best regards,\n"
        "The TWF Team"
    )

    try:
        send_mail(
            subject, message, DEFAULT_FROM_EMAIL, [user_email], fail_silently=False
        )
        return True
    except Exception as e:
        # Log the error or handle it as needed
        logger.error(e)
        return False


def send_reset_email(user_email, username, temp_password):
    """
    Sends a password reset email with a new temporary password.

    Parameters:
        user_email (str): The recipient's email address.
        username (str): The user's username.
        temp_password (str): A temporary password assigned to the user.
    """
    subject = "TWF Password Reset Request"
    message = (
        f"Hello {username},\n\n"
        "You recently requested a password reset. Below is your new temporary password:\n\n"
        f"Temporary Password: {temp_password}\n\n"
        "Please log in and change your password immediately for security reasons.\n\n"
        "If you did not request this change, please contact our support team immediately.\n\n"
        "Best regards,\n"
        "The TWF Team"
    )

    try:
        send_mail(subject, message, DEFAULT_FROM_EMAIL, [user_email])
        return True
    except Exception as e:
        # Log the error or handle it as needed
        logger.error(e)
        return False

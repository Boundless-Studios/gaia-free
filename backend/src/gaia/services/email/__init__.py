"""Email services package"""

from gaia.services.email.service import (
    EmailService,
    EmailProvider,
    get_email_service,
)

__all__ = [
    "EmailService",
    "EmailProvider",
    "get_email_service",
]

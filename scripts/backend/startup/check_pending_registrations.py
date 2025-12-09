#!/usr/bin/env python3
"""
Startup script to check for users stuck in pending registration state.

This script runs during backend startup to identify and attempt to notify
admins about users who completed registration but whose admin notification
email failed to send.

This prevents users from being stuck indefinitely in "waiting for approval" state.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.src.models import User
from db.src import get_async_db
from gaia.services.email.service import get_email_service

logger = logging.getLogger(__name__)


async def check_and_notify_pending_registrations() -> None:
    """
    Check for users who completed registration but admin was never notified.

    This identifies users in indeterminate state:
    - registration_status = 'completed'
    - is_active = False (not yet approved)
    - admin_notified_at IS NULL (admin was never notified)

    For each such user, attempt to send admin notification email.
    """
    logger.info("🔍 Checking for users with pending admin notifications...")

    # Get database session
    async for db in get_async_db():
        try:
            # Query for users who need admin notification
            query = select(User).where(
                User.registration_status == "completed",
                User.is_active == False,
                User.admin_notified_at == None
            ).order_by(User.registration_completed_at.desc())

            result = await db.execute(query)
            pending_users: List[User] = list(result.scalars().all())

            if not pending_users:
                logger.info("✅ No pending admin notifications found")
                return

            logger.warning(
                f"⚠️  Found {len(pending_users)} user(s) with pending admin notifications"
            )

            # Get email service
            email_service = get_email_service()
            admin_email = os.getenv("PRIMARY_ADMIN_EMAIL")

            if not admin_email:
                logger.warning(
                    "⚠️  PRIMARY_ADMIN_EMAIL not configured, cannot send admin notifications"
                )
                return

            # Attempt to send notification for each user
            success_count = 0
            failed_count = 0

            for user in pending_users:
                try:
                    logger.info(f"📧 Attempting to notify admin about: {user.email}")

                    success = await email_service.send_access_request_email(
                        admin_email=admin_email,
                        user_email=user.email,
                        display_name=user.display_name or user.email,
                        reason=None,
                    )

                    if success:
                        user.admin_notified_at = datetime.now(timezone.utc)
                        user.admin_notification_failed = False
                        user.admin_notification_error = None
                        await db.commit()
                        success_count += 1
                        logger.info(f"✅ Successfully notified admin about: {user.email}")
                    else:
                        user.admin_notification_failed = True
                        user.admin_notification_error = "Email service returned False"
                        await db.commit()
                        failed_count += 1
                        logger.error(
                            f"❌ Failed to notify admin about: {user.email} "
                            "(email service returned False)"
                        )

                except Exception as e:
                    user.admin_notification_failed = True
                    user.admin_notification_error = str(e)
                    await db.commit()
                    failed_count += 1
                    logger.error(
                        f"❌ Exception notifying admin about: {user.email} - {e}",
                        exc_info=True
                    )

            # Summary
            logger.info(
                f"📊 Admin notification summary: "
                f"{success_count} successful, {failed_count} failed"
            )

            if failed_count > 0:
                logger.warning(
                    f"⚠️  {failed_count} user(s) still pending admin notification. "
                    "Check email configuration and logs."
                )

        except Exception as e:
            logger.error(f"❌ Error checking pending registrations: {e}", exc_info=True)
            await db.rollback()
        finally:
            await db.close()
            break  # Exit after first iteration (async for loop pattern)


def run_pending_registration_check() -> None:
    """
    Synchronous wrapper to run the async check function.

    Called from main.py during backend startup.
    """
    try:
        asyncio.run(check_and_notify_pending_registrations())
    except Exception as e:
        logger.error(f"❌ Failed to run pending registration check: {e}", exc_info=True)


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run the check
    run_pending_registration_check()

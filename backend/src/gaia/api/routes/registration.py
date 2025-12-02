"""
Registration API endpoints for user onboarding flow.

Handles EULA acceptance, email opt-in, and registration completion.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from auth.src.middleware import get_current_user
from auth.src.models import User, RegistrationStatus
from db.src import get_async_db
from gaia.services.email import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["registration"])

# EULA version constant - update this when EULA changes
CURRENT_EULA_VERSION = "1.0"


class EULAResponse(BaseModel):
    """Response containing EULA text and metadata"""

    version: str
    content: str
    effective_date: str


class CompleteRegistrationRequest(BaseModel):
    """Request to complete user registration"""

    eula_accepted: bool
    eula_version: str
    email_opt_in: bool = False


class AccessRequestRequest(BaseModel):
    """Request to request access to the system"""

    eula_accepted: bool
    eula_version: str
    email_opt_in: bool = False
    reason: Optional[str] = None


class RegistrationStatusResponse(BaseModel):
    """Response containing user's registration status"""

    registration_status: str
    eula_accepted: bool
    eula_version_accepted: str | None
    registration_completed_at: str | None
    is_authorized: bool  # Whether user is on the allowlist (is_active)


@router.get("/eula", response_model=EULAResponse)
async def get_eula():
    """
    Get the current EULA text.

    This endpoint is accessible to all authenticated users, even those
    who haven't completed registration yet.

    Returns:
        EULAResponse: EULA content and metadata
    """
    try:
        # Read EULA from static file
        # Path: routes -> api -> gaia -> src -> static
        eula_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "static", "EULA.md"
        )

        with open(eula_path, "r") as f:
            content = f.read()

        return EULAResponse(
            version=CURRENT_EULA_VERSION,
            content=content,
            effective_date="2025-10-23",
        )

    except FileNotFoundError:
        logger.error(f"EULA file not found at {eula_path}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EULA document not found",
        )
    except Exception as e:
        logger.error(f"Error reading EULA: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load EULA",
        )


@router.get("/registration-status", response_model=RegistrationStatusResponse)
async def get_registration_status(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the current user's registration status.

    This endpoint is accessible to all authenticated users.

    Returns:
        RegistrationStatusResponse: User's registration status
    """
    return RegistrationStatusResponse(
        registration_status=current_user.registration_status,
        eula_accepted=current_user.eula_accepted_at is not None,
        eula_version_accepted=current_user.eula_version_accepted,
        registration_completed_at=(
            current_user.registration_completed_at.isoformat()
            if current_user.registration_completed_at
            else None
        ),
        is_authorized=current_user.is_active,
    )


@router.post("/request-access", status_code=status.HTTP_200_OK)
async def request_access(
    request: AccessRequestRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db),
):
    """
    Request access to the system after accepting EULA.

    This marks the user as completed/inactive (awaiting admin approval).
    Sends an email to admin with approval instructions.

    Args:
        request: Access request data with EULA acceptance
        current_user: Authenticated user
        db: Database session

    Returns:
        Success message indicating access request is pending

    Raises:
        HTTPException: If EULA not accepted or version mismatch
    """
    # Validate EULA acceptance
    if not request.eula_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the EULA to request access",
        )

    if request.eula_version != CURRENT_EULA_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"EULA version mismatch. Please accept version {CURRENT_EULA_VERSION}",
        )

    # Check if already completed
    if current_user.registration_status == RegistrationStatus.COMPLETED.value:
        return {
            "message": "Access request already submitted",
            "status": "pending_approval",
            "is_active": current_user.is_active,
        }

    try:
        # Update user record - mark as completed but inactive (awaiting approval)
        current_user.registration_status = RegistrationStatus.COMPLETED.value
        current_user.eula_accepted_at = datetime.now(timezone.utc)
        current_user.eula_version_accepted = request.eula_version
        current_user.registration_email_opt_in = request.email_opt_in
        current_user.registration_completed_at = datetime.now(timezone.utc)
        # Keep is_active=False until admin approves

        await db.commit()
        await db.refresh(current_user)

        logger.info(
            f"User {current_user.email} requested access (email_opt_in={request.email_opt_in})"
        )

        # Send access request email to admin
        email_service = get_email_service()
        try:
            success = await email_service.send_access_request_email(
                admin_email="ilya@your-domain.com",
                user_email=current_user.email,
                display_name=current_user.display_name or current_user.email,
                reason=request.reason,
            )
            if success:
                current_user.admin_notified_at = datetime.now(timezone.utc)
                current_user.admin_notification_failed = False
                current_user.admin_notification_error = None
                logger.info(f"Access request email sent to admin for {current_user.email}")
            else:
                current_user.admin_notification_failed = True
                current_user.admin_notification_error = "Email service returned False"
                logger.warning(f"Email service returned False for {current_user.email}")
        except Exception as e:
            current_user.admin_notification_failed = True
            current_user.admin_notification_error = str(e)
            logger.error(f"Failed to send access request email: {e}")
            # Don't fail the request if email fails

        return {
            "message": "Access request submitted successfully",
            "status": "pending_approval",
            "is_active": False,
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to process access request for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit access request. Please try again.",
        )


@router.post("/complete-registration", status_code=status.HTTP_200_OK)
async def complete_registration(
    request: CompleteRegistrationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_async_db),
):
    """
    Complete user registration by accepting EULA and setting preferences.

    This endpoint is accessible to users with pending registration status.

    Args:
        request: Registration completion data
        current_user: Authenticated user
        db: Database session

    Returns:
        Success message and updated user status

    Raises:
        HTTPException: If EULA not accepted or version mismatch
    """
    # Validate EULA acceptance
    if not request.eula_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the EULA to complete registration",
        )

    if request.eula_version != CURRENT_EULA_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"EULA version mismatch. Please accept version {CURRENT_EULA_VERSION}",
        )

    # Check if already completed
    if current_user.registration_status == RegistrationStatus.COMPLETED.value:
        return {
            "message": "Registration already completed",
            "status": "completed",
        }

    try:
        # Update user record
        current_user.registration_status = RegistrationStatus.COMPLETED.value
        current_user.eula_accepted_at = datetime.now(timezone.utc)
        current_user.eula_version_accepted = request.eula_version
        current_user.registration_email_opt_in = request.email_opt_in
        current_user.registration_completed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(current_user)

        logger.info(
            f"User {current_user.email} completed registration (email_opt_in={request.email_opt_in})"
        )

        # Send emails asynchronously (don't block registration on email failure)
        email_service = get_email_service()

        # Send welcome email if user opted in
        if request.email_opt_in:
            try:
                await email_service.send_welcome_email(
                    to_email=current_user.email,
                    display_name=current_user.display_name or current_user.email,
                )
                logger.info(f"Welcome email sent to {current_user.email}")
            except Exception as e:
                logger.error(f"Failed to send welcome email: {e}")
                # Don't fail registration if email fails

        # Always send registration completion email
        try:
            await email_service.send_registration_complete_email(
                to_email=current_user.email,
                display_name=current_user.display_name or current_user.email,
            )
            logger.info(f"Registration complete email sent to {current_user.email}")
        except Exception as e:
            logger.error(f"Failed to send registration complete email: {e}")
            # Don't fail registration if email fails

        return {
            "message": "Registration completed successfully",
            "status": "completed",
            "eula_version": current_user.eula_version_accepted,
            "email_opt_in": current_user.registration_email_opt_in,
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to complete registration for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete registration. Please try again.",
        )

"""
Admin endpoints for managing registered users (allowlist) and campaign inspection.

Access control: restricted to users with is_admin=True in the database.
"""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.src import get_async_db
from auth.src.models import User
from auth.src.auth0_jwt_verifier import get_auth0_verifier
from gaia.models.campaign_db import Campaign
from gaia.models.campaign_state_db import CampaignState
from gaia.models.turn_event_db import TurnEvent


security = HTTPBearer(auto_error=True)


async def require_super_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Verify Auth0 token and require is_admin=True in database.

    Returns the User object on success.
    """
    token = credentials.credentials if credentials else None
    verifier = get_auth0_verifier()
    if not verifier:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth0 not configured")

    payload = verifier.verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

    # Look up user in database and check admin status
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not found in database")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is not active")

    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    return user


class RegisterUserRequest(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    username: Optional[str]
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_admin: bool
    is_active: bool
    # Registration fields
    registration_status: str
    eula_accepted_at: Optional[str]
    eula_version_accepted: Optional[str]
    registration_completed_at: Optional[str]
    created_at: Optional[str]
    last_login: Optional[str]

    @staticmethod
    def from_model(user: User) -> "UserResponse":
        return UserResponse(
            user_id=str(user.user_id),
            email=user.email,
            username=user.username,
            display_name=getattr(user, "display_name", None),
            avatar_url=getattr(user, "avatar_url", None),
            is_admin=bool(getattr(user, "is_admin", False)),
            is_active=bool(getattr(user, "is_active", True)),
            registration_status=getattr(user, "registration_status", "pending"),
            eula_accepted_at=user.eula_accepted_at.isoformat() if user.eula_accepted_at else None,
            eula_version_accepted=getattr(user, "eula_version_accepted", None),
            registration_completed_at=user.registration_completed_at.isoformat() if user.registration_completed_at else None,
            created_at=user.created_at.isoformat() if user.created_at else None,
            last_login=user.last_login.isoformat() if user.last_login else None,
        )


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_super_admin)])


@router.get("/allowlist/users", response_model=List[UserResponse])
async def list_registered_users(db: AsyncSession = Depends(get_async_db)) -> List[UserResponse]:
    result = await db.execute(select(User).order_by(User.email))
    users = result.scalars().all()
    return [UserResponse.from_model(u) for u in users]


async def _generate_unique_username(db: AsyncSession, base: str) -> str:
    base = (base or "user").strip().lower().replace(" ", "_")
    candidate = base
    counter = 1
    while True:
        result = await db.execute(select(User).where(User.username == candidate))
        if not result.scalar_one_or_none():
            return candidate
        counter += 1
        candidate = f"{base}{counter}"


@router.post("/allowlist/register", response_model=UserResponse)
async def register_user(
    req: RegisterUserRequest,
    db: AsyncSession = Depends(get_async_db),
):
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if user:
        # Optionally update fields if provided
        updated = False
        if req.username and req.username != user.username:
            user.username = req.username
            updated = True
        if req.display_name is not None and req.display_name != getattr(user, "display_name", None):
            user.display_name = req.display_name
            updated = True
        if req.avatar_url is not None and req.avatar_url != getattr(user, "avatar_url", None):
            user.avatar_url = req.avatar_url
            updated = True
        if req.is_admin is not None and req.is_admin != getattr(user, "is_admin", False):
            user.is_admin = req.is_admin
            updated = True
        if req.is_active is not None and req.is_active != getattr(user, "is_active", True):
            user.is_active = req.is_active
            updated = True
        if updated:
            await db.commit()
        return UserResponse.from_model(user)

    # Create new pre-registered user
    username = req.username or await _generate_unique_username(db, req.email.split("@")[0])
    user = User(
        email=req.email,
        username=username,
        display_name=req.display_name,
        avatar_url=req.avatar_url,
        is_admin=req.is_admin,
        is_active=req.is_active,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Retry with a unique username
        username = await _generate_unique_username(db, username)
        user.username = username
        db.add(user)
        await db.commit()

    return UserResponse.from_model(user)


@router.patch("/allowlist/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if req.username is not None:
        user.username = req.username
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url
    if req.is_admin is not None:
        user.is_admin = req.is_admin
    if req.is_active is not None:
        user.is_active = req.is_active

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already in use")

    return UserResponse.from_model(user)


@router.post("/allowlist/users/{user_id}/disable", response_model=UserResponse)
async def disable_user(user_id: str, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = False
    await db.commit()
    return UserResponse.from_model(user)


@router.post("/allowlist/users/{user_id}/enable", response_model=UserResponse)
async def enable_user(user_id: str, db: AsyncSession = Depends(get_async_db)):
    """Enable/activate a user account."""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = True
    await db.commit()
    return UserResponse.from_model(user)


class OnboardUserRequest(BaseModel):
    """Request to onboard a user - marks them as active with completed registration."""
    send_welcome_email: bool = True


@router.post("/allowlist/users/{user_id}/onboard", response_model=UserResponse)
async def onboard_user(
    user_id: str,
    req: OnboardUserRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Onboard a user who has accepted EULA and requested access.

    This sets is_active=True so the user can access the system.
    Optionally sends a welcome email.
    """
    from datetime import datetime, timezone

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Activate the user
    user.is_active = True
    await db.commit()

    # Send welcome email if requested
    if req.send_welcome_email:
        from gaia.services.email.service import get_email_service
        email_service = get_email_service()
        try:
            await email_service.send_welcome_email(
                to_email=user.email,
                display_name=user.display_name or user.username or user.email.split('@')[0]
            )
        except Exception as e:
            # Log but don't fail the onboarding
            import logging
            logging.getLogger(__name__).warning(f"Failed to send welcome email to {user.email}: {e}")

    return UserResponse.from_model(user)


class TestEmailRequest(BaseModel):
    email: EmailStr
    test_type: str = "welcome"  # welcome, registration_complete, or access_request


@router.post("/test-email")
async def test_email(
    req: TestEmailRequest,
    admin_user: User = Depends(require_super_admin),
):
    """
    Test email sending functionality in production.

    Sends a test email to verify SMTP configuration is working correctly.
    Restricted to admin users only.
    """
    from gaia.services.email.service import get_email_service

    email_service = get_email_service()

    try:
        if req.test_type == "welcome":
            success = await email_service.send_welcome_email(
                to_email=req.email,
                display_name="Test User"
            )
        elif req.test_type == "registration_complete":
            success = await email_service.send_registration_complete_email(
                to_email=req.email,
                display_name="Test User"
            )
        elif req.test_type == "access_request":
            success = await email_service.send_access_request_email(
                admin_email=req.email,
                user_email="test.requester@example.com",
                display_name="Test Requester",
                reason="Testing email functionality"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid test_type: {req.test_type}. Must be welcome, registration_complete, or access_request"
            )

        if success:
            return {"success": True, "message": f"Test email sent successfully to {req.email}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email. Check server logs for details."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending email: {str(e)}"
        )


# ============================================================================
# Campaign Admin Response Models
# ============================================================================


class CampaignStateResponse(BaseModel):
    """Response model for campaign state."""
    state_id: str
    campaign_id: str
    current_turn: int
    last_turn_started_at: Optional[str]
    last_turn_completed_at: Optional[str]
    is_processing: bool
    active_turn: Optional[Dict[str, Any]]
    version: int

    @staticmethod
    def from_model(state: CampaignState) -> "CampaignStateResponse":
        return CampaignStateResponse(
            state_id=str(state.state_id),
            campaign_id=str(state.campaign_id),
            current_turn=state.current_turn,
            last_turn_started_at=state.last_turn_started_at.isoformat() if state.last_turn_started_at else None,
            last_turn_completed_at=state.last_turn_completed_at.isoformat() if state.last_turn_completed_at else None,
            is_processing=state.is_processing,
            active_turn=state.active_turn,
            version=state.version,
        )


class CampaignAdminResponse(BaseModel):
    """Response model for campaign listing."""
    campaign_id: str
    external_campaign_id: str
    environment: str
    name: Optional[str]
    description: Optional[str]
    owner_id: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    # Nested state summary
    current_turn: int
    is_processing: bool
    event_count: int

    @staticmethod
    def from_model(campaign: Campaign, event_count: int = 0) -> "CampaignAdminResponse":
        state = campaign.state
        return CampaignAdminResponse(
            campaign_id=str(campaign.campaign_id),
            external_campaign_id=campaign.external_campaign_id,
            environment=campaign.environment,
            name=campaign.name,
            description=campaign.description,
            owner_id=campaign.owner_id,
            is_active=campaign.is_active,
            created_at=campaign.created_at.isoformat() if hasattr(campaign, 'created_at') and campaign.created_at else None,
            updated_at=campaign.updated_at.isoformat() if hasattr(campaign, 'updated_at') and campaign.updated_at else None,
            current_turn=state.current_turn if state else 0,
            is_processing=state.is_processing if state else False,
            event_count=event_count,
        )


class CampaignDetailResponse(BaseModel):
    """Response model for campaign details with full state."""
    campaign_id: str
    external_campaign_id: str
    environment: str
    name: Optional[str]
    description: Optional[str]
    owner_id: Optional[str]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]
    state: Optional[CampaignStateResponse]
    event_count: int

    @staticmethod
    def from_model(campaign: Campaign, event_count: int = 0) -> "CampaignDetailResponse":
        return CampaignDetailResponse(
            campaign_id=str(campaign.campaign_id),
            external_campaign_id=campaign.external_campaign_id,
            environment=campaign.environment,
            name=campaign.name,
            description=campaign.description,
            owner_id=campaign.owner_id,
            is_active=campaign.is_active,
            created_at=campaign.created_at.isoformat() if hasattr(campaign, 'created_at') and campaign.created_at else None,
            updated_at=campaign.updated_at.isoformat() if hasattr(campaign, 'updated_at') and campaign.updated_at else None,
            state=CampaignStateResponse.from_model(campaign.state) if campaign.state else None,
            event_count=event_count,
        )


class TurnEventResponse(BaseModel):
    """Response model for turn events."""
    event_id: str
    campaign_id: str
    turn_number: int
    event_index: int
    type: str
    role: str
    content: Optional[Dict[str, Any]]
    event_metadata: Dict[str, Any]
    created_at: str

    @staticmethod
    def from_model(event: TurnEvent) -> "TurnEventResponse":
        return TurnEventResponse(
            event_id=str(event.event_id),
            campaign_id=str(event.campaign_id),
            turn_number=event.turn_number,
            event_index=event.event_index,
            type=event.type,
            role=event.role,
            content=event.content,
            event_metadata=event.event_metadata,
            created_at=event.created_at.isoformat(),
        )


class CampaignStatsResponse(BaseModel):
    """Response model for campaign statistics."""
    total_campaigns: int
    active_campaigns: int
    inactive_campaigns: int
    campaigns_by_environment: Dict[str, int]
    total_events: int
    events_by_type: Dict[str, int]
    campaigns_processing: int


# ============================================================================
# Campaign Admin Endpoints
# ============================================================================


@router.get("/campaigns/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(db: AsyncSession = Depends(get_async_db)) -> CampaignStatsResponse:
    """Get aggregate statistics about campaigns."""
    # Total campaigns
    total_result = await db.execute(select(func.count(Campaign.campaign_id)))
    total_campaigns = total_result.scalar() or 0

    # Active/inactive counts
    active_result = await db.execute(
        select(func.count(Campaign.campaign_id)).where(Campaign.is_active == True)
    )
    active_campaigns = active_result.scalar() or 0

    # Campaigns by environment
    env_result = await db.execute(
        select(Campaign.environment, func.count(Campaign.campaign_id))
        .group_by(Campaign.environment)
    )
    campaigns_by_environment = {row[0]: row[1] for row in env_result.fetchall()}

    # Total events
    events_result = await db.execute(select(func.count(TurnEvent.event_id)))
    total_events = events_result.scalar() or 0

    # Events by type
    type_result = await db.execute(
        select(TurnEvent.type, func.count(TurnEvent.event_id))
        .group_by(TurnEvent.type)
    )
    events_by_type = {row[0]: row[1] for row in type_result.fetchall()}

    # Campaigns currently processing
    processing_result = await db.execute(
        select(func.count(CampaignState.state_id))
        .where(CampaignState.active_turn.isnot(None))
    )
    campaigns_processing = processing_result.scalar() or 0

    return CampaignStatsResponse(
        total_campaigns=total_campaigns,
        active_campaigns=active_campaigns,
        inactive_campaigns=total_campaigns - active_campaigns,
        campaigns_by_environment=campaigns_by_environment,
        total_events=total_events,
        events_by_type=events_by_type,
        campaigns_processing=campaigns_processing,
    )


@router.get("/campaigns", response_model=List[CampaignAdminResponse])
async def list_campaigns(
    db: AsyncSession = Depends(get_async_db),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by ID, name, or owner"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> List[CampaignAdminResponse]:
    """List all campaigns with optional filtering."""
    query = select(Campaign).options(selectinload(Campaign.state))

    if environment:
        query = query.where(Campaign.environment == environment)
    if is_active is not None:
        query = query.where(Campaign.is_active == is_active)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Campaign.external_campaign_id.ilike(search_pattern)) |
            (Campaign.name.ilike(search_pattern)) |
            (Campaign.owner_id.ilike(search_pattern))
        )

    query = query.order_by(desc(Campaign.campaign_id)).limit(limit).offset(offset)

    result = await db.execute(query)
    campaigns = result.scalars().all()

    # Get event counts for each campaign
    campaign_ids = [c.campaign_id for c in campaigns]
    if campaign_ids:
        count_result = await db.execute(
            select(TurnEvent.campaign_id, func.count(TurnEvent.event_id))
            .where(TurnEvent.campaign_id.in_(campaign_ids))
            .group_by(TurnEvent.campaign_id)
        )
        event_counts = {row[0]: row[1] for row in count_result.fetchall()}
    else:
        event_counts = {}

    return [
        CampaignAdminResponse.from_model(c, event_counts.get(c.campaign_id, 0))
        for c in campaigns
    ]


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> CampaignDetailResponse:
    """Get detailed information about a specific campaign."""
    # Try to find by external_campaign_id first, then by UUID
    query = select(Campaign).options(selectinload(Campaign.state))

    result = await db.execute(
        query.where(Campaign.external_campaign_id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        # Try UUID
        try:
            import uuid
            campaign_uuid = uuid.UUID(campaign_id)
            result = await db.execute(
                query.where(Campaign.campaign_id == campaign_uuid)
            )
            campaign = result.scalar_one_or_none()
        except ValueError:
            pass

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    # Get event count
    count_result = await db.execute(
        select(func.count(TurnEvent.event_id))
        .where(TurnEvent.campaign_id == campaign.campaign_id)
    )
    event_count = count_result.scalar() or 0

    return CampaignDetailResponse.from_model(campaign, event_count)


@router.get("/campaigns/{campaign_id}/events", response_model=List[TurnEventResponse])
async def get_campaign_events(
    campaign_id: str,
    db: AsyncSession = Depends(get_async_db),
    turn_number: Optional[int] = Query(None, description="Filter by turn number"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    role: Optional[str] = Query(None, description="Filter by role"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> List[TurnEventResponse]:
    """Get turn events for a campaign."""
    # Find the campaign first
    result = await db.execute(
        select(Campaign).where(Campaign.external_campaign_id == campaign_id)
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        try:
            import uuid
            campaign_uuid = uuid.UUID(campaign_id)
            result = await db.execute(
                select(Campaign).where(Campaign.campaign_id == campaign_uuid)
            )
            campaign = result.scalar_one_or_none()
        except ValueError:
            pass

    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    # Build query for events
    query = select(TurnEvent).where(TurnEvent.campaign_id == campaign.campaign_id)

    if turn_number is not None:
        query = query.where(TurnEvent.turn_number == turn_number)
    if event_type:
        query = query.where(TurnEvent.type == event_type)
    if role:
        query = query.where(TurnEvent.role == role)

    query = query.order_by(TurnEvent.turn_number, TurnEvent.event_index).limit(limit).offset(offset)

    result = await db.execute(query)
    events = result.scalars().all()

    return [TurnEventResponse.from_model(e) for e in events]


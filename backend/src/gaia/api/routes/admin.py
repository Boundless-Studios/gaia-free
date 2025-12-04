"""
Admin endpoints for managing registered users (allowlist).

Access control: restricted to users with is_admin=True in the database.
"""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.src import get_async_db
from auth.src.models import User
from auth.src.auth0_jwt_verifier import get_auth0_verifier


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


"""
SQLAlchemy models for OAuth2 authentication

These models match the PostgreSQL schema created in the init scripts.
"""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4
from enum import Enum

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    UniqueConstraint, CheckConstraint, Text, JSON, UUID
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import INET

from db.src.base import BaseModel, Base


class AuthProvider(str, Enum):
    """Supported OAuth2 providers"""
    GOOGLE = "google"
    GITHUB = "github"
    DISCORD = "discord"
    LOCAL = "local"  # For future local auth support


class PermissionLevel(str, Enum):
    """Permission levels for access control"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class RegistrationStatus(str, Enum):
    """User registration flow status"""
    PENDING = "pending"
    COMPLETED = "completed"


class User(BaseModel):
    """User model for authentication"""
    
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}
    
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    user_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Registration flow fields
    registration_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )
    eula_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    eula_version_accepted: Mapped[Optional[str]] = mapped_column(String(50))
    registration_email_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    registration_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Admin notification tracking for access requests
    admin_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    admin_notification_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_notification_error: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    oauth_accounts: Mapped[List["OAuthAccount"]] = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    access_controls: Mapped[List["AccessControl"]] = relationship(
        "AccessControl",
        back_populates="user",
        foreign_keys="AccessControl.user_id",
        cascade="all, delete-orphan"
    )
    granted_permissions: Mapped[List["AccessControl"]] = relationship(
        "AccessControl",
        back_populates="granter",
        foreign_keys="AccessControl.granted_by"
    )
    
    def __repr__(self):
        return f"<User(email={self.email}, username={self.username})>"
    
    def has_permission(self, resource_type: str, resource_id: str, level: PermissionLevel) -> bool:
        """Check if user has specific permission"""
        if self.is_admin:
            return True
        
        for access in self.access_controls:
            if (access.resource_type == resource_type and 
                access.resource_id == resource_id and
                access.permission_level == level and
                (not access.expires_at or access.expires_at > datetime.utcnow())):
                return True
        return False


class OAuthAccount(BaseModel):
    """OAuth account linked to a user"""
    
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint('provider', 'provider_account_id', name='uq_provider_account'),
        {"schema": "auth"}
    )
    
    account_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Note: access_token and refresh_token removed - Auth0 handles token management
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")
    
    def __repr__(self):
        return f"<OAuthAccount(provider={self.provider}, user_id={self.user_id})>"




class AccessControl(BaseModel):
    """Resource-level access control"""
    
    __tablename__ = "access_control"
    __table_args__ = (
        UniqueConstraint('user_id', 'resource_type', 'resource_id', name='uq_user_resource'),
        CheckConstraint(
            "permission_level IN ('read', 'write', 'admin')",
            name='check_permission_level'
        ),
        {"schema": "auth"}
    )
    
    access_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.user_id"),
        nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User", 
        back_populates="access_controls",
        foreign_keys=[user_id]
    )
    granter: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="granted_permissions",
        foreign_keys=[granted_by]
    )
    
    def __repr__(self):
        return f"<AccessControl(user_id={self.user_id}, resource={self.resource_type}:{self.resource_id}, level={self.permission_level})>"



class SecurityEvent(Base):
    """Audit log for security events"""
    
    __tablename__ = "security_events"
    __table_args__ = {"schema": "audit"}
    
    event_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.user_id"),
        nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
    
    def __repr__(self):
        return f"<SecurityEvent(event_type={self.event_type}, user_id={self.user_id}, success={self.success})>"
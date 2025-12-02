"""
Base models and mixins for SQLAlchemy ORM
"""

from datetime import datetime
from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncAttrs

# Create base class for all models
Base = declarative_base()


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps to models"""
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class BaseModel(Base, AsyncAttrs, TimestampMixin):
    """Base model class with common fields and async support"""
    
    __abstract__ = True
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update(self, **kwargs):
        """Update model attributes"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
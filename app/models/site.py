"""Site and AdminUser models for WebsiteCMS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import bcrypt
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.content import SiteContent
    from app.models.site_config import SiteConfig
    from app.models.history import ContentChange


class Site(Base, BaseMixin):
    """Model representing a deployed website."""

    __tablename__ = "sites"

    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    site_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'band', 'rolfing'
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships - use string annotations for forward references
    admin_users: Mapped[List["AdminUser"]] = relationship(
        "AdminUser", back_populates="site", cascade="all, delete-orphan"
    )
    content: Mapped[Optional["SiteContent"]] = relationship(
        "SiteContent", back_populates="site", uselist=False, cascade="all, delete-orphan"
    )
    config: Mapped[Optional["SiteConfig"]] = relationship(
        "SiteConfig", back_populates="site", uselist=False, cascade="all, delete-orphan"
    )
    changes: Mapped[List["ContentChange"]] = relationship(
        "ContentChange", back_populates="site", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Site(id={self.id}, domain={self.domain}, type={self.site_type})>"


class AdminUser(Base, BaseMixin):
    """Model representing an admin user for a site."""

    __tablename__ = "admin_users"

    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="admin_users")
    changes: Mapped[List["ContentChange"]] = relationship(
        "ContentChange", back_populates="admin_user"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("site_id", "username", name="uq_site_username"),
        Index("ix_admin_users_site_username", "site_id", "username"),
    )

    def set_password(self, password: str) -> None:
        """Hash and set the user's password.
        
        Args:
            password: Plain text password to hash.
        """
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash.
        
        Args:
            password: Plain text password to verify.
            
        Returns:
            True if password matches, False otherwise.
        """
        return bcrypt.checkpw(
            password.encode("utf-8"), 
            self.password_hash.encode("utf-8")
        )

    def update_last_login(self) -> None:
        """Update the last_login timestamp to now."""
        self.last_login = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, username={self.username}, site_id={self.site_id})>"

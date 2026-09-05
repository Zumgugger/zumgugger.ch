"""Admin session model for WebsiteCMS."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin
from app.config import get_settings

if TYPE_CHECKING:
    from app.models.site import AdminUser, Site


class AdminSession(Base, BaseMixin):
    """Model representing an admin login session."""

    __tablename__ = "admin_sessions"

    admin_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    admin_user: Mapped["AdminUser"] = relationship("AdminUser", backref="sessions")
    site: Mapped["Site"] = relationship("Site", backref="sessions")

    # Indexes
    __table_args__ = (
        Index("ix_admin_sessions_expires_at", "expires_at"),
        Index("ix_admin_sessions_admin_user_id", "admin_user_id"),
        Index("ix_admin_sessions_site_id", "site_id"),
    )

    @classmethod
    def create_session(
        cls,
        admin_user_id: int,
        site_id: int,
        token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> "AdminSession":
        """Create a new admin session.
        
        Args:
            admin_user_id: The admin user's ID.
            site_id: The site's ID.
            token: The session token.
            ip_address: Client IP address (optional).
            user_agent: Client user agent (optional).
            
        Returns:
            New AdminSession instance.
        """
        settings = get_settings()
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.session_timeout_seconds
        )
        
        return cls(
            admin_user_id=admin_user_id,
            site_id=site_id,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def is_expired(self) -> bool:
        """Check if the session has expired.
        
        Returns:
            True if session is expired, False otherwise.
        """
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        
        # Handle timezone-naive datetime from database
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        
        return now > expires

    def refresh(self) -> None:
        """Refresh the session expiry time."""
        settings = get_settings()
        self.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.session_timeout_seconds
        )

    def __repr__(self) -> str:
        return (
            f"<AdminSession(id={self.id}, admin_user_id={self.admin_user_id}, "
            f"expires_at={self.expires_at})>"
        )

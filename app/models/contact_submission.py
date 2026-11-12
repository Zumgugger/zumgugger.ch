"""Model for stored contact form submissions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.site import Site


class ContactSubmission(Base, BaseMixin):
    """Model storing a complete contact form submission.

    Email/SMS notifications may truncate the message due to provider
    limits, so the full submission is persisted here for the admin view.
    """

    __tablename__ = "contact_submissions"

    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )

    # Contact details as submitted and after normalization
    contact_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_value: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_type: Mapped[str] = mapped_column(String(20), nullable=False)  # email or phone

    # Full message without any truncation
    message: Mapped[str] = mapped_column(Text, nullable=False)

    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Notification delivery status
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="contact_submissions")

    __table_args__ = (
        Index("ix_contact_submissions_site_created", "site_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ContactSubmission(id={self.id}, site_id={self.site_id}, "
            f"contact={self.contact_value})>"
        )

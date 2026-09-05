"""History and audit models for tracking content changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.site import AdminUser, Site


class ContentChange(Base, BaseMixin):
    """Model tracking content changes for undo/audit functionality.
    
    Stores the before and after values of content changes, along with
    metadata about who made the change and when.
    """

    __tablename__ = "content_changes"

    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    admin_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    
    # Timestamp for the change (separate from created_at for explicit control)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # What was changed
    module_type: Mapped[str] = mapped_column(String(50), nullable=False)  # hero, services, etc.
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)  # headline, cta_text, etc.
    
    # Values before and after (stored as JSON for flexibility)
    old_value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
    # Optional description of the change
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="changes")
    admin_user: Mapped[Optional["AdminUser"]] = relationship("AdminUser", back_populates="changes")

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_content_changes_site_timestamp", "site_id", "timestamp"),
        Index("ix_content_changes_site_id", "site_id"),
    )

    def describe(self) -> str:
        """Generate a human-readable description of the change.
        
        Returns:
            A description like "Changed hero headline" or "Updated services item".
        """
        if self.description:
            return self.description
        
        # Generate default description based on module and field
        module_labels = {
            "hero": "Hero",
            "services": "Angebot",
            "about": "Über mich",
            "trust": "Referenzen",
            "media": "Medien",
            "faq": "FAQ",
            "contact": "Kontakt",
            "footer": "Footer",
        }
        
        field_labels = {
            "headline": "Überschrift",
            "cta_text": "Button-Text",
            "cta_target": "Button-Ziel",
            "bg_image": "Hintergrundbild",
            "items": "Einträge",
            "blocks": "Inhaltsblöcke",
            "testimonials": "Testimonials",
            "images": "Bilder",
            "phone": "Telefon",
            "email": "E-Mail",
            "address": "Adresse",
            "social_links": "Social Links",
        }
        
        module = module_labels.get(self.module_type, self.module_type)
        field = field_labels.get(self.field_name, self.field_name)
        
        return f"{module}: {field} geändert"

    def __repr__(self) -> str:
        return f"<ContentChange(id={self.id}, site_id={self.site_id}, module={self.module_type}, field={self.field_name})>"

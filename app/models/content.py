"""Content models for WebsiteCMS - stores all site content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.site import Site


class SiteContent(Base, BaseMixin):
    """Model storing all content for a site.
    
    This is a single-row-per-site model that contains all the content
    for the various modules (hero, services, about, etc.).
    """

    __tablename__ = "site_content"

    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Hero module
    hero_headline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hero_cta_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hero_cta_target: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="contact")
    hero_bg_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Path to image

    # Trust/Proof module - stored as JSON arrays
    trust_images: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)
    testimonials: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)
    review_source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    review_source_text: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Services/Offer module - stored as JSON array
    services: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)

    # About module - stored as JSON array of blocks
    about_blocks: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)

    # Repertoire module - stored as ordered JSON entries
    repertoire_entries: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)

    # Media module - stored as JSON array of blocks
    media_blocks: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)

    # FAQ module - stored as JSON array
    faq_items: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)

    # Contact module
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # E.164 format
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contact_maps_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Footer module - stored as JSON array
    footer_social_links: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True, default=list)

    # Legal pages
    impressum_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    datenschutz_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="content")

    # Indexes
    __table_args__ = (
        Index("ix_site_content_site_id", "site_id"),
    )

    def __repr__(self) -> str:
        return f"<SiteContent(id={self.id}, site_id={self.site_id})>"

    def get_module_data(self, module_type: str) -> Dict[str, Any]:
        """Get data for a specific module.
        
        Args:
            module_type: The type of module (hero, services, about, etc.)
            
        Returns:
            Dictionary containing the module's data.
        """
        module_data = {
            "hero": {
                "headline": self.hero_headline,
                "cta_text": self.hero_cta_text,
                "cta_target": self.hero_cta_target,
                "bg_image": self.hero_bg_image,
            },
            "trust": {
                "images": self.trust_images or [],
                "testimonials": self.testimonials or [],
                "review_source_url": self.review_source_url,
                "review_source_text": self.review_source_text,
            },
            "services": {
                "items": self.services or [],
            },
            "about": {
                "blocks": self.about_blocks or [],
            },
            "repertoire": {
                "entries": self.repertoire_entries or [],
                "groups": self._get_repertoire_groups(),
                "import_text": self._get_repertoire_import_text(),
            },
            "media": {
                "blocks": self.media_blocks or [],
            },
            "faq": {
                "items": self.faq_items or [],
            },
            "contact": {
                "phone": self.contact_phone,
                "email": self.contact_email,
                "address": self.contact_address,
                "maps_link": self.contact_maps_link,
            },
            "footer": {
                "social_links": self.footer_social_links or [],
                "phone": self.contact_phone,
                "email": self.contact_email,
                "address": self.contact_address,
            },
        }
        return module_data.get(module_type, {})

    def _get_repertoire_groups(self) -> List[Dict[str, Any]]:
        """Group repertoire entries in the order their decades were entered."""
        groups: List[Dict[str, Any]] = []
        groups_by_decade: Dict[str, Dict[str, Any]] = {}

        for index, entry in enumerate(self.repertoire_entries or []):
            decade = entry.get("decade", "Weitere Titel")
            if decade not in groups_by_decade:
                group = {"decade": decade, "entries": []}
                groups_by_decade[decade] = group
                groups.append(group)
            display_entry = dict(entry)
            display_entry["index"] = index
            groups_by_decade[decade]["entries"].append(display_entry)

        return groups

    def _get_repertoire_import_text(self) -> str:
        """Serialize saved repertoire entries for the admin bulk editor."""
        lines: List[str] = []
        current_decade: Optional[str] = None

        for entry in self.repertoire_entries or []:
            decade = entry.get("decade", "Weitere Titel")
            if decade != current_decade:
                if lines:
                    lines.append("")
                lines.append(decade)
                current_decade = decade

            title = entry.get("title", "")
            if entry.get("mundart"):
                title = f"{title} (Mundart)"
            year = entry.get("year", "")
            lines.append(f"{year} {title}".strip())

        return "\n".join(lines)

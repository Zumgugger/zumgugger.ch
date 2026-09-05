"""Site configuration model for theme, module states, and settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseMixin

if TYPE_CHECKING:
    from app.models.site import Site


# Valid module states
MODULE_STATES = ["enabled", "available", "excluded"]

# Default module order
DEFAULT_MODULE_ORDER = [
    "hero",
    "trust",
    "services",
    "about",
    "repertoire",
    "media",
    "faq",
    "contact",
    "footer",
]


class SiteConfig(Base, BaseMixin):
    """Model storing site-level configuration.
    
    Includes theme selection, module states (enabled/available/excluded),
    CSS variable overrides, and custom navigation labels.
    """

    __tablename__ = "site_config"

    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Theme selection
    theme_name: Mapped[str] = mapped_column(String(50), nullable=False, default="clean")

    # Module states: {"hero": "enabled", "media": "available", ...}
    # States: "enabled" (visible), "available" (can be enabled), "excluded" (not shipped)
    module_states: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    # Module order: ["hero", "trust", "services", ...]
    module_order: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list
    )

    # CSS variable overrides: {"--color-primary": "#ff0000", ...}
    css_variables: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON, nullable=True, default=dict
    )

    # Custom navigation labels: {"services": "Leistungen", "about": "Über uns", ...}
    nav_labels: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON, nullable=True, default=dict
    )

    # Logo image path (uploaded logo)
    logo_image: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default=None
    )

    # Favicon image path (uploaded favicon)
    favicon_image: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default=None
    )

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="config")

    # Indexes
    __table_args__ = (
        Index("ix_site_config_site_id", "site_id"),
    )

    def __repr__(self) -> str:
        return f"<SiteConfig(id={self.id}, site_id={self.site_id}, theme={self.theme_name})>"

    def is_module_enabled(self, module_type: str) -> bool:
        """Check if a module is enabled.
        
        Args:
            module_type: The module type to check.
            
        Returns:
            True if the module is enabled, False otherwise.
        """
        return self.module_states.get(module_type) == "enabled"

    def is_module_available(self, module_type: str) -> bool:
        """Check if a module is available (can be enabled).
        
        Args:
            module_type: The module type to check.
            
        Returns:
            True if the module is available (enabled or can be enabled), False if excluded.
        """
        state = self.module_states.get(module_type)
        return state in ("enabled", "available")

    def get_enabled_modules(self) -> List[str]:
        """Get list of enabled modules in order.
        
        Returns:
            List of module types that are enabled, in display order.
        """
        order = self.module_order or DEFAULT_MODULE_ORDER
        return [m for m in order if self.is_module_enabled(m)]

    def get_nav_label(self, module_type: str) -> str:
        """Get the navigation label for a module.
        
        Args:
            module_type: The module type.
            
        Returns:
            Custom label if set, otherwise default label.
        """
        default_labels = {
            "hero": "",  # No nav item for hero
            "trust": "Referenzen",
            "services": "Angebot",
            "about": "Über mich",
            "repertoire": "Repertoire",
            "media": "Medien",
            "faq": "FAQ",
            "contact": "Kontakt",
            "footer": "",  # No nav item for footer
        }
        
        if self.nav_labels and module_type in self.nav_labels:
            return self.nav_labels[module_type]
        
        return default_labels.get(module_type, module_type.capitalize())

    def set_module_state(self, module_type: str, state: str) -> None:
        """Set the state of a module.
        
        Args:
            module_type: The module type.
            state: One of "enabled", "available", "excluded".
            
        Raises:
            ValueError: If state is not valid.
        """
        if state not in MODULE_STATES:
            raise ValueError(f"Invalid module state: {state}. Must be one of {MODULE_STATES}")
        
        if self.module_states is None:
            self.module_states = {}
        
        self.module_states[module_type] = state

    def set_module_order(self, order: List[str]) -> None:
        """Set the display order of modules.
        
        Args:
            order: List of module types in desired order.
        """
        self.module_order = order

    @classmethod
    def get_default_states_for_site_type(cls, site_type: str) -> Dict[str, str]:
        """Get default module states for a site type.
        
        Args:
            site_type: The type of site (band, rolfing, etc.)
            
        Returns:
            Dictionary of module states.
        """
        # Base defaults
        defaults = {
            "hero": "enabled",
            "trust": "enabled",
            "services": "enabled",
            "about": "enabled",
            "repertoire": "available",
            "media": "available",  # Off by default
            "faq": "available",    # Off by default
            "contact": "enabled",
            "footer": "enabled",
        }
        
        # Site-type specific overrides
        if site_type == "band":
            defaults["media"] = "enabled"  # Bands need media
            defaults["faq"] = "available"
            defaults["repertoire"] = "enabled"
        elif site_type == "rolfing":
            defaults["media"] = "available"
            defaults["faq"] = "enabled"  # Rolfing benefits from FAQ
        
        return defaults

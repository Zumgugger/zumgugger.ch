"""Pydantic schemas for WebsiteCMS."""

from app.schemas.content import (
    AboutBlockSchema,
    ContactSchema,
    FAQItemSchema,
    HeroSchema,
    MediaBlockSchema,
    ServiceCardSchema,
    SiteContentSchema,
    SocialLinkSchema,
    CustomerTestimonialSchema,
    TrustImageSchema,
    TrustSchema,
)

__all__ = [
    "HeroSchema",
    "ServiceCardSchema",
    "CustomerTestimonialSchema",
    "TrustImageSchema",
    "AboutBlockSchema",
    "MediaBlockSchema",
    "FAQItemSchema",
    "SocialLinkSchema",
    "ContactSchema",
    "TrustSchema",
    "SiteContentSchema",
]

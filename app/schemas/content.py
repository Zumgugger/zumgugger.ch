"""Pydantic schemas for content validation."""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class HeroSchema(BaseModel):
    """Schema for hero module content."""
    
    headline: str = Field(..., min_length=1, max_length=500)
    cta_text: str = Field(..., min_length=1, max_length=100)
    cta_target: str = Field(default="contact", max_length=50)
    bg_image: Optional[str] = Field(default=None, max_length=500)


class ServiceCardSchema(BaseModel):
    """Schema for a single service card."""
    
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    image: Optional[str] = Field(default=None, max_length=500)
    
    # Optional icon identifier (for icon-based cards)
    icon: Optional[str] = Field(default=None, max_length=50)


class CustomerTestimonialSchema(BaseModel):
    """Schema for a single testimonial."""
    
    quote: str = Field(..., min_length=1, max_length=2000)
    author_name: str = Field(..., min_length=1, max_length=100)
    author_role: Optional[str] = Field(default=None, max_length=200)


class TrustImageSchema(BaseModel):
    """Schema for trust/proof images (logos, badges, etc.)."""
    
    src: str = Field(..., min_length=1, max_length=500)
    alt: str = Field(..., min_length=1, max_length=200)


class AboutBlockSchema(BaseModel):
    """Schema for about module content blocks.
    
    Supports: text, image, gallery blocks.
    """
    
    type: Literal["text", "image", "gallery"] = Field(...)
    
    # For text blocks
    content: Optional[str] = Field(default=None)
    
    # For image blocks
    src: Optional[str] = Field(default=None, max_length=500)
    alt: Optional[str] = Field(default=None, max_length=200)
    
    # For gallery blocks
    images: Optional[List[TrustImageSchema]] = Field(default=None)
    
    @model_validator(mode="after")
    def validate_text_content(self) -> "AboutBlockSchema":
        """Validate that text blocks have content."""
        if self.type == "text" and not self.content:
            raise ValueError("Text blocks must have content")
        return self


class MediaBlockSchema(BaseModel):
    """Schema for media module content blocks.
    
    Supports: text, image, gallery, youtube, audio blocks.
    """
    
    type: Literal["text", "image", "gallery", "youtube", "audio"] = Field(...)
    
    # For text blocks
    content: Optional[str] = Field(default=None)
    
    # For image blocks
    src: Optional[str] = Field(default=None, max_length=500)
    alt: Optional[str] = Field(default=None, max_length=200)
    
    # For gallery blocks
    images: Optional[List[TrustImageSchema]] = Field(default=None)
    
    # For youtube blocks
    youtube_url: Optional[str] = Field(default=None, max_length=500)
    
    # For audio blocks (Spotify, SoundCloud)
    audio_url: Optional[str] = Field(default=None, max_length=500)
    audio_provider: Optional[Literal["spotify", "soundcloud"]] = Field(default=None)


class FAQItemSchema(BaseModel):
    """Schema for a single FAQ item."""
    
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=5000)


class SocialLinkSchema(BaseModel):
    """Schema for a social media link."""
    
    platform: Literal["instagram", "facebook", "youtube", "spotify", "email", "custom"] = Field(...)
    url: str = Field(..., min_length=1, max_length=500)
    label: Optional[str] = Field(default=None, max_length=100)  # For custom links
    
    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: str, info) -> str:
        """Validate URL format based on platform."""
        platform = info.data.get("platform")
        
        if platform == "email":
            # Email should be mailto: or plain email
            if not v.startswith("mailto:") and "@" not in v:
                raise ValueError("Invalid email format")
        elif not v.startswith(("http://", "https://", "mailto:")):
            raise ValueError("URL must start with http://, https://, or mailto:")
        
        return v


class ContactSchema(BaseModel):
    """Schema for contact module content."""
    
    phone: Optional[str] = Field(default=None, max_length=50)  # E.164 format
    email: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=500)
    maps_link: Optional[str] = Field(default=None, max_length=500)
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone is in E.164 format (starts with +)."""
        if v and not v.startswith("+"):
            raise ValueError("Phone must be in E.164 format (starting with +)")
        return v
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation."""
        if v and "@" not in v:
            raise ValueError("Invalid email format")
        return v


class TrustSchema(BaseModel):
    """Schema for trust/proof module content."""
    
    images: List[TrustImageSchema] = Field(default_factory=list)
    testimonials: List[CustomerTestimonialSchema] = Field(default_factory=list)
    review_source_url: Optional[str] = Field(default=None, max_length=500)
    review_source_text: Optional[str] = Field(default=None, max_length=200)


class SiteContentSchema(BaseModel):
    """Full schema for all site content."""
    
    hero: Optional[HeroSchema] = None
    trust: Optional[TrustSchema] = None
    services: List[ServiceCardSchema] = Field(default_factory=list)
    about_blocks: List[AboutBlockSchema] = Field(default_factory=list)
    media_blocks: List[MediaBlockSchema] = Field(default_factory=list)
    faq_items: List[FAQItemSchema] = Field(default_factory=list)
    contact: Optional[ContactSchema] = None
    footer_social_links: List[SocialLinkSchema] = Field(default_factory=list)
    impressum_content: Optional[str] = None
    datenschutz_content: Optional[str] = None

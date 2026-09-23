"""Concert management routes for the public concerts module."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.middleware.auth import require_auth
from app.models.content import SiteContent
from app.models.site import AdminUser, Site
from app.models.site_config import SiteConfig
from app.utils.history import delete_old_changes, record_change

router = APIRouter(tags=["concerts"])
templates = Jinja2Templates(directory="app/templates")


def _clean_text(value: str) -> str:
    """Keep plain text while preserving its user-entered line breaks."""
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(
        re.sub(r"[ \t\f\v]+", " ", line).strip() for line in value.split("\n")
    ).strip()


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _clean_text(value) or None


def _validate_url(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Bitte eine vollständige http(s)-URL angeben")
    return value


class ConcertPayload(BaseModel):
    """Editable fields for one concert."""

    title: str = Field(..., min_length=1, max_length=160)
    description: Optional[str] = Field(None, max_length=3000)
    image: Optional[str] = Field(None, max_length=500)
    image_srcset: Optional[str] = Field(None, max_length=2000)
    date: date
    time: str = Field(..., min_length=1, max_length=100)
    venue: str = Field(..., min_length=1, max_length=250)
    maps_url: Optional[str] = Field(None, max_length=1000)
    external_url: Optional[str] = Field(None, max_length=1000)
    external_text: Optional[str] = Field(None, max_length=160)
    is_public: bool = True

    @field_validator("title", "time", "venue")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = _clean_text(value)
        if not value:
            raise ValueError("Dieses Feld muss ausgefüllt sein")
        return value

    @field_validator("description", "external_text", "image", "image_srcset", mode="before")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _clean_optional_text(value)

    @field_validator("maps_url", "external_url")
    @classmethod
    def validate_optional_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_url(value)

    def to_item(self, concert_id: str) -> dict[str, Any]:
        return {
            "id": concert_id,
            "title": self.title,
            "description": self.description,
            "image": self.image,
            "image_srcset": self.image_srcset,
            "date": self.date.isoformat(),
            "time": self.time,
            "venue": self.venue,
            "maps_url": self.maps_url,
            "external_url": self.external_url,
            "external_text": self.external_text,
            "is_public": self.is_public,
        }


class ConcertSettingsPayload(BaseModel):
    """Public concert-list settings."""

    display_limit: int = Field(..., ge=1, le=24)


def _site_content_config(admin: AdminUser, db: Session) -> tuple[Site, SiteContent, SiteConfig]:
    site = db.query(Site).filter(Site.id == admin.site_id).first()
    content = db.query(SiteContent).filter(SiteContent.site_id == admin.site_id).first()
    config = db.query(SiteConfig).filter(SiteConfig.site_id == admin.site_id).first()
    if not site or not content or not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Website-Konfiguration nicht gefunden"},
        )
    return site, content, config


def _sorted_concerts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("date", ""), reverse=True)


@router.get("/admin/concerts", response_class=HTMLResponse)
async def concerts_page(
    request: Request,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Render the dedicated concert management page."""
    site, content, config = _site_content_config(admin, db)
    return templates.TemplateResponse(
        request,
        "admin_concerts.html",
        {
            "site": site,
            "concerts": _sorted_concerts(content.concerts_items or []),
            "display_limit": config.concerts_display_limit,
        },
    )


@router.post("/api/admin/concerts")
async def create_concert(
    payload: ConcertPayload,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new concert."""
    site, content, _ = _site_content_config(admin, db)
    concerts = list(content.concerts_items or [])
    item = payload.to_item(uuid4().hex)
    concerts.append(item)
    content.concerts_items = concerts
    flag_modified(content, "concerts_items")
    record_change(db, site.id, admin.id, "concerts", "concerts_items", [], concerts, "Konzert erfasst")
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    return {"status": "success", "concert": item}


@router.put("/api/admin/concerts/{concert_id}")
async def update_concert(
    concert_id: str,
    payload: ConcertPayload,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update a concert by its stable identifier."""
    site, content, _ = _site_content_config(admin, db)
    concerts = list(content.concerts_items or [])
    for index, existing in enumerate(concerts):
        if existing.get("id") == concert_id:
            item = payload.to_item(concert_id)
            concerts[index] = item
            content.concerts_items = concerts
            flag_modified(content, "concerts_items")
            record_change(db, site.id, admin.id, "concerts", f"concerts_items.{concert_id}", existing, item, "Konzert bearbeitet")
            delete_old_changes(db, site.id, keep_count=50)
            db.commit()
            return {"status": "success", "concert": item}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "not_found", "message": "Konzert nicht gefunden"})


@router.delete("/api/admin/concerts/{concert_id}")
async def delete_concert(
    concert_id: str,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a concert by its stable identifier."""
    site, content, _ = _site_content_config(admin, db)
    concerts = list(content.concerts_items or [])
    remaining = [item for item in concerts if item.get("id") != concert_id]
    if len(remaining) == len(concerts):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": "not_found", "message": "Konzert nicht gefunden"})
    content.concerts_items = remaining
    flag_modified(content, "concerts_items")
    record_change(db, site.id, admin.id, "concerts", f"concerts_items.{concert_id}", concerts, remaining, "Konzert gelöscht")
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    return {"status": "success"}


@router.put("/api/admin/concerts/settings")
async def update_concert_settings(
    payload: ConcertSettingsPayload,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    """Update the number of upcoming concerts shown publicly."""
    site, _, config = _site_content_config(admin, db)
    old_value = config.concerts_display_limit
    config.concerts_display_limit = payload.display_limit
    record_change(db, site.id, admin.id, "concerts", "concerts_display_limit", old_value, payload.display_limit, "Anzeigegrenze Konzerte geändert")
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    return {"status": "success", "display_limit": payload.display_limit}
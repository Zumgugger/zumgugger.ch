"""Tests for concert management and public concert rendering."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.content import SiteContent
from app.models.site import Site
from app.models.site_config import SiteConfig


def concert_payload(title: str = "Sommerkonzert") -> dict:
    """Return a valid concert payload for API tests."""
    return {
        "title": title,
        "description": "Ein Abend mit Live-Musik.",
        "date": "2099-06-15",
        "time": "20:00 Uhr",
        "venue": "Kulturhaus Zürich",
        "maps_url": "https://maps.google.com/?q=Kulturhaus+Zuerich",
        "external_url": "https://example.com/tickets",
        "external_text": "Tickets",
        "is_public": True,
    }


def test_create_public_concert_is_rendered_on_homepage(
    test_client_with_site: TestClient,
    test_admin_session,
    test_db: Session,
    test_site: Site,
):
    """A public future concert is saved and rendered on the public site."""
    response = test_client_with_site.post(
        "/api/admin/concerts",
        json=concert_payload(),
        cookies={"session_token": test_admin_session.token},
    )

    assert response.status_code == 200
    saved = response.json()["concert"]
    assert saved["title"] == "Sommerkonzert"

    config = test_db.query(SiteConfig).filter_by(site_id=test_site.id).one()
    config.module_states = {**config.module_states, "concerts": "enabled"}
    if "concerts" not in config.module_order:
        config.module_order.insert(-1, "concerts")
    test_db.commit()

    home = test_client_with_site.get("/", params={"site_domain": test_site.domain})

    assert home.status_code == 200
    assert "Sommerkonzert" in home.text
    assert "Tickets" in home.text


def test_private_and_past_concerts_are_not_in_upcoming_list(
    test_client_with_site: TestClient,
    test_admin_session,
    test_db: Session,
    test_site: Site,
):
    """Only public future concerts count toward the public upcoming limit."""
    for title, date, is_public in [
        ("Öffentlich", "2099-06-15", True),
        ("Privat", "2099-06-16", False),
        ("Vergangen", "2000-06-15", True),
    ]:
        payload = concert_payload(title)
        payload["date"] = date
        payload["is_public"] = is_public
        assert test_client_with_site.post(
            "/api/admin/concerts",
            json=payload,
            cookies={"session_token": test_admin_session.token},
        ).status_code == 200

    config = test_db.query(SiteConfig).filter_by(site_id=test_site.id).one()
    config.module_states = {**config.module_states, "concerts": "enabled"}
    config.concerts_display_limit = 1
    if "concerts" not in config.module_order:
        config.module_order.insert(-1, "concerts")
    test_db.commit()

    home = test_client_with_site.get("/", params={"site_domain": test_site.domain})

    assert "Öffentlich" in home.text
    assert "Privat" not in home.text
    assert "Vergangen" in home.text


def test_concert_display_limit_must_be_within_configured_range(
    test_client_with_site: TestClient,
    test_admin_session,
):
    """The public display limit is restricted to one through twenty-four."""
    response = test_client_with_site.put(
        "/api/admin/concerts/settings",
        json={"display_limit": 25},
        cookies={"session_token": test_admin_session.token},
    )

    assert response.status_code == 422
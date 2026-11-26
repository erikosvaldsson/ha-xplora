"""Brand image tests."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.myxplora.const import DOMAIN

BRAND_DIR = Path(__file__).parent.parent / "custom_components" / DOMAIN / "brand"


async def test_brand_images_are_served(hass: HomeAssistant, hass_client) -> None:
    """Home Assistant serves custom integration icons from <domain>/brand/.

    Without them the integration list shows a placeholder, since myxplora is
    not on the central brands CDN.
    """
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()

    for image in ("icon.png", "icon@2x.png", "logo.png", "dark_icon.png"):
        resp = await client.get(f"/api/brands/integration/{DOMAIN}/{image}")
        assert resp.status == HTTPStatus.OK, image
        body = await resp.read()
        assert body.startswith(b"\x89PNG"), image
        # Variants we do not ship fall back to the plain icon.
        expected = image if (BRAND_DIR / image).exists() else "icon.png"
        assert body == (BRAND_DIR / expected).read_bytes(), image

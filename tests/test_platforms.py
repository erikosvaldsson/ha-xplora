"""Every module of the integration imports against the current Home Assistant."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.myxplora import PLATFORMS
from custom_components.myxplora.const import DOMAIN


async def test_integration_and_platforms_import(hass: HomeAssistant) -> None:
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.is_built_in is False
    await integration.async_get_component()
    for platform in (*PLATFORMS, "config_flow"):
        await integration.async_get_platform(str(platform))

"""Data update coordinator — one slow, passive poll for all watches."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WatchData, XploraApi, XploraAuthError
from .const import (
    CONF_COUNTRY_CODE,
    CONF_LANGUAGE,
    CONF_PHONE,
    CONF_SCAN_MINUTES,
    CONF_TIMEZONE,
    DEFAULT_LANGUAGE,
    DEFAULT_SCAN_MINUTES,
    DEFAULT_TIMEZONE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class XploraCoordinator(DataUpdateCoordinator[dict[str, WatchData]]):
    """Coordinates the passive battery/telemetry poll."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        scan_minutes = entry.options.get(
            CONF_SCAN_MINUTES, entry.data.get(CONF_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_minutes),
        )
        self.entry = entry
        self.api = XploraApi(
            country_code=entry.data.get(CONF_COUNTRY_CODE, ""),
            phone=entry.data.get(CONF_PHONE, ""),
            email=entry.data.get(CONF_EMAIL, ""),
            password=entry.data[CONF_PASSWORD],
            language=entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            timezone=entry.data.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> dict[str, WatchData]:
        try:
            return await self.api.async_get_data()
        except XploraAuthError as err:
            # Surfaces as a reauth/repair to the user rather than retry-spamming.
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Error polling Xplora: {err}") from err

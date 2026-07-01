"""Device tracker — the watch's last *reported* location (passive, may be stale)."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import XploraConfigEntry
from .entity import XploraWatchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XploraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a device tracker per watch."""
    coordinator = entry.runtime_data
    async_add_entities(
        XploraDeviceTracker(coordinator, wuid) for wuid in (coordinator.data or {})
    )


class XploraDeviceTracker(XploraWatchEntity, TrackerEntity):
    """Last-known location. Not a live fix (no active locate command is sent)."""

    _attr_translation_key = "location"

    def __init__(self, coordinator, wuid: str) -> None:
        super().__init__(coordinator, wuid, "location")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self.watch.latitude if self.watch else None

    @property
    def longitude(self) -> float | None:
        return self.watch.longitude if self.watch else None

    @property
    def location_accuracy(self) -> int:
        watch = self.watch
        return watch.accuracy if watch and watch.accuracy is not None else 0

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        watch = self.watch
        if watch is None:
            return {}
        return {
            "address": watch.address,
            "place_of_interest": watch.poi,
            "locate_type": watch.locate_type,
            "reported_at": watch.located_at.isoformat() if watch.located_at else None,
        }

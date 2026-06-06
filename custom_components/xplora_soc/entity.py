"""Shared base entity for Xplora watch entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import WatchData
from .const import DOMAIN, MANUFACTURER
from .coordinator import XploraCoordinator


class XploraWatchEntity(CoordinatorEntity[XploraCoordinator]):
    """Base entity bound to a single watch (one HA device per watch)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: XploraCoordinator, wuid: str, key: str) -> None:
        super().__init__(coordinator)
        self._wuid = wuid
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{wuid}_{key}"

    @property
    def watch(self) -> WatchData | None:
        return (self.coordinator.data or {}).get(self._wuid)

    @property
    def available(self) -> bool:
        return super().available and self.watch is not None

    @property
    def device_info(self) -> DeviceInfo:
        watch = self.watch
        base = watch.name if watch else self._wuid
        model = watch.model if watch else None
        # Put the model in the device name so it flows into entity_ids, e.g.
        # "Alex Watch XGO3" -> binary_sensor.alex_watch_xgo3_charging.
        name = f"{base} Watch {model}" if model else base
        return DeviceInfo(
            identifiers={(DOMAIN, self._wuid)},
            manufacturer=(watch.manufacturer if watch else None) or MANUFACTURER,
            name=name,
            model=model or "Xplora Watch",
            sw_version=watch.sw_version if watch else None,
        )

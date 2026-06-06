"""Binary sensor platform — charging / online / safe-zone."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import XploraConfigEntry
from .api import WatchData
from .coordinator import XploraCoordinator
from .entity import XploraWatchEntity


@dataclass(frozen=True, kw_only=True)
class XploraBinaryDescription(BinarySensorEntityDescription):
    """Describes an Xplora binary sensor."""

    value_fn: Callable[[WatchData], bool | None]


BINARY_SENSORS: tuple[XploraBinaryDescription, ...] = (
    XploraBinaryDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda w: w.charging,
    ),
    XploraBinaryDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda w: None if w.online is None else w.online.upper() == "ONLINE",
    ),
    XploraBinaryDescription(
        key="in_safe_zone",
        translation_key="in_safe_zone",
        icon="mdi:shield-home",
        value_fn=lambda w: w.in_safe_zone,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XploraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xplora binary sensors for every watch."""
    coordinator = entry.runtime_data
    async_add_entities(
        XploraBinarySensor(coordinator, wuid, description)
        for wuid in (coordinator.data or {})
        for description in BINARY_SENSORS
    )


class XploraBinarySensor(XploraWatchEntity, BinarySensorEntity):
    """A single passive binary sensor."""

    entity_description: XploraBinaryDescription

    def __init__(
        self,
        coordinator: XploraCoordinator,
        wuid: str,
        description: XploraBinaryDescription,
    ) -> None:
        super().__init__(coordinator, wuid, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        watch = self.watch
        if watch is None:
            return None
        return self.entity_description.value_fn(watch)

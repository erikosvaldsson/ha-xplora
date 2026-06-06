"""Sensor platform — passive WatchLastLocate fields."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import XploraConfigEntry
from .api import WatchData
from .coordinator import XploraCoordinator
from .entity import XploraWatchEntity


@dataclass(frozen=True, kw_only=True)
class XploraSensorDescription(SensorEntityDescription):
    """Describes an Xplora sensor with a value extractor."""

    value_fn: Callable[[WatchData], float | int | str | None]


SENSORS: tuple[XploraSensorDescription, ...] = (
    XploraSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda w: w.battery,
    ),
    XploraSensorDescription(
        key="steps",
        translation_key="steps",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:walk",
        value_fn=lambda w: w.step,
    ),
    XploraSensorDescription(
        key="distance",
        translation_key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda w: w.distance,
    ),
    XploraSensorDescription(
        key="locate_type",
        translation_key="locate_type",
        icon="mdi:crosshairs-gps",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda w: w.locate_type,
    ),
    XploraSensorDescription(
        key="safe_zone",
        translation_key="safe_zone",
        icon="mdi:shield-home",
        value_fn=lambda w: w.safe_zone_label,
    ),
    XploraSensorDescription(
        key="located_at",
        translation_key="located_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda w: w.located_at,
    ),
    XploraSensorDescription(
        key="battery_reported_at",
        translation_key="battery_reported_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda w: w.battery_reported_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XploraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Xplora sensors for every watch."""
    coordinator = entry.runtime_data
    async_add_entities(
        XploraSensor(coordinator, wuid, description)
        for wuid in (coordinator.data or {})
        for description in SENSORS
    )


class XploraSensor(XploraWatchEntity, SensorEntity):
    """A single passive sensor."""

    entity_description: XploraSensorDescription

    def __init__(
        self,
        coordinator: XploraCoordinator,
        wuid: str,
        description: XploraSensorDescription,
    ) -> None:
        super().__init__(coordinator, wuid, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        watch = self.watch
        if watch is None:
            return None
        return self.entity_description.value_fn(watch)

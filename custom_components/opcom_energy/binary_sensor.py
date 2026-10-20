"""Explicit advisory signals; never directly control equipment."""

from datetime import timedelta
from decimal import Decimal

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OpcomConfigEntry
from .entity import OpcomEntity
from .prices import current_slot, day_slots, percentile, price_kwh

PARALLEL_UPDATES = 0
DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="cheap_now", translation_key="cheap_now", icon="mdi:cash-clock"
    ),
    BinarySensorEntityDescription(
        key="below_threshold", translation_key="below_threshold", icon="mdi:arrow-down-bold"
    ),
    BinarySensorEntityDescription(
        key="tomorrow_available", translation_key="tomorrow_available", icon="mdi:calendar-check"
    ),
    BinarySensorEntityDescription(
        key="source_available",
        translation_key="source_available",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-check",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: OpcomConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        OpcomBinarySensor(entry.runtime_data, description) for description in DESCRIPTIONS
    )


class OpcomBinarySensor(OpcomEntity, BinarySensorEntity):
    """Return unknown for missing prices, never a misleading false."""

    def __init__(self, coordinator, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        key = self.entity_description.key
        if key == "source_available":
            return self.coordinator.source_available
        now = dt_util.utcnow()
        today = now.astimezone(self.coordinator.local_tz).date()
        rows = self.coordinator.data or ()
        if key == "tomorrow_available":
            return bool(day_slots(rows, today + timedelta(days=1), self.coordinator.local_tz))
        slot = current_slot(rows, now)
        if slot is None:
            return None
        if key == "below_threshold":
            return price_kwh(slot, self.coordinator.options, "import") <= Decimal(
                str(self.coordinator.options["cheap_threshold"])
            )
        selected = day_slots(rows, today, self.coordinator.local_tz)
        if not selected:
            return None
        return percentile(selected, slot) <= self.coordinator.options["cheap_percentile"]

    @property
    def available(self) -> bool:
        return self.is_on is not None

"""Price, local-day statistics, planning and source diagnostics."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OpcomConfigEntry
from .coordinator import OpcomCoordinator
from .entity import OpcomEntity
from .prices import average_price, cheapest_window, current_slot, day_slots, percentile, price_kwh

PARALLEL_UPDATES = 0

PRICE_KEYS = (
    "spot_price",
    "next_spot_price",
    "import_price",
    "export_price",
    "today_average",
    "today_min",
    "today_max",
    "tomorrow_average",
    "cheapest_window_price",
)
DESCRIPTIONS = tuple(
    SensorEntityDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement="RON/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        icon="mdi:currency-sign",
        entity_registry_enabled_default=key not in ("export_price",),
    )
    for key in PRICE_KEYS
) + (
    SensorEntityDescription(
        key="spot_price_mwh",
        translation_key="spot_price_mwh",
        native_unit_of_measurement="RON/MWh",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="price_percentile",
        translation_key="price_percentile",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="cheapest_window_start",
        translation_key="cheapest_window_start",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="last_successful_fetch",
        translation_key="last_successful_fetch",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: OpcomConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(OpcomSensor(entry.runtime_data, description) for description in DESCRIPTIONS)


@dataclass(frozen=True, slots=True)
class SensorReading:
    """A sensor value and its metadata, resolved from the same intervals and time."""

    value: Decimal | float | datetime | None = None
    attributes: dict[str, Any] | None = None


class OpcomSensor(OpcomEntity, SensorEntity):
    """Availability follows price coverage, including when retrieval fails."""

    def __init__(self, coordinator: OpcomCoordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._reading = SensorReading()

    async def async_added_to_hass(self) -> None:
        self._reading = self._resolve_reading()
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Resolve once per update so properties cannot select different intervals."""
        self._reading = self._resolve_reading()
        super()._handle_coordinator_update()

    def _resolve_reading(self) -> SensorReading:
        """Select intervals and derive their value and attributes together."""
        key = self.entity_description.key
        now = dt_util.utcnow()
        rows = self.coordinator.data or ()
        today = now.astimezone(self.coordinator.local_tz).date()
        options = self.coordinator.options
        if key == "last_successful_fetch":
            return SensorReading(self.coordinator.last_success)
        if key.startswith("cheapest_window"):
            window = cheapest_window(
                rows, now, now + timedelta(hours=48), options["window_minutes"], options, "import"
            )
            if window is None:
                return SensorReading()
            return SensorReading(
                window.start if key.endswith("start") else window.average,
                {
                    "start": window.start.isoformat(),
                    "end": window.end.isoformat(),
                    "average_price": float(window.average),
                    "price_type": "import",
                    "unit": "RON/kWh",
                    "duration_minutes": options["window_minutes"],
                },
            )
        if key.startswith(("today_", "tomorrow_")):
            day = today + timedelta(days=int(key.startswith("tomorrow")))
            selected = day_slots(rows, day, self.coordinator.local_tz)
            if key.endswith("average"):
                return SensorReading(
                    average_price(selected, options) if selected else None,
                    {
                        "date": day.isoformat(),
                        "timezone": self.coordinator.hass.config.time_zone,
                        "complete": bool(selected),
                        "prices": [
                            {
                                "start": s.start.isoformat(),
                                "end": s.end.isoformat(),
                                "price": float(price_kwh(s, options)),
                            }
                            for s in selected
                        ],
                    },
                )
            if not selected:
                return SensorReading()
            slot = (min if key.endswith("min") else max)(selected, key=lambda s: s.price)
            return SensorReading(
                price_kwh(slot, options),
                {"start": slot.start.isoformat(), "end": slot.end.isoformat()},
            )
        slot = current_slot(rows, now)
        if slot is None:
            return SensorReading()
        if key == "price_percentile":
            selected = day_slots(rows, today, self.coordinator.local_tz)
            return SensorReading(percentile(selected, slot) if selected else None)
        if key == "next_spot_price":
            slot = current_slot(rows, slot.end)
            if slot is None:
                return SensorReading()
        attrs = {
            "start": slot.start.isoformat(),
            "end": slot.end.isoformat(),
            "source": "opcom.ro",
            "market_timezone": "Europe/Berlin",
        }
        if key.startswith(("import", "export")):
            kind = key.removesuffix("_price")
            attrs.update(
                {
                    "multiplier": options[f"{kind}_multiplier"],
                    "adder_ron_kwh": options[f"{kind}_adder"],
                    "formula": "spot_ron_kwh * multiplier + adder",
                }
            )
        else:
            kind = "spot"
        value = slot.price if key == "spot_price_mwh" else price_kwh(slot, options, kind)
        return SensorReading(value, attrs)

    @property
    def native_value(self) -> Decimal | float | datetime | None:
        return self._reading.value

    @property
    def available(self) -> bool:
        return self._reading.value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._reading.attributes

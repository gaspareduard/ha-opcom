"""Price, local-day statistics, planning and source diagnostics."""

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OpcomConfigEntry
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


class OpcomSensor(OpcomEntity, SensorEntity):
    """Availability follows price coverage, including when retrieval fails."""

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    def _price_context(self):
        now = dt_util.utcnow()
        rows = self.coordinator.data or ()
        today = now.astimezone(self.coordinator.local_tz).date()
        return now, rows, today

    def _window(self):
        now, rows, _ = self._price_context()
        return cheapest_window(
            rows,
            now,
            now + timedelta(hours=48),
            self.coordinator.options["window_minutes"],
            self.coordinator.options,
            "import",
        )

    @property
    def native_value(self):
        key = self.entity_description.key
        now, rows, today = self._price_context()
        options = self.coordinator.options
        if key == "last_successful_fetch":
            return self.coordinator.last_success
        if key.startswith("cheapest_window"):
            window = self._window()
            if window is None:
                return None
            return window.start if key.endswith("start") else window.average
        if key.startswith(("today_", "tomorrow_")):
            day = today + timedelta(days=int(key.startswith("tomorrow")))
            selected = day_slots(rows, day, self.coordinator.local_tz)
            if not selected:
                return None
            if key.endswith("average"):
                return average_price(selected, options)
            slot = (min if key.endswith("min") else max)(selected, key=lambda s: s.price)
            return price_kwh(slot, options)
        slot = current_slot(rows, now)
        if slot is None:
            return None
        if key == "next_spot_price":
            following = current_slot(rows, slot.end)
            return price_kwh(following, options) if following else None
        if key == "spot_price_mwh":
            return slot.price
        if key == "price_percentile":
            selected = day_slots(rows, today, self.coordinator.local_tz)
            return percentile(selected, slot) if selected else None
        return price_kwh(slot, options, key.removesuffix("_price"))

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def extra_state_attributes(self):
        key = self.entity_description.key
        now, rows, today = self._price_context()
        if key in ("today_average", "tomorrow_average"):
            day = today + timedelta(days=int(key.startswith("tomorrow")))
            selected = day_slots(rows, day, self.coordinator.local_tz)
            return {
                "date": day.isoformat(),
                "timezone": self.coordinator.hass.config.time_zone,
                "complete": bool(selected),
                "prices": [
                    {
                        "start": s.start.isoformat(),
                        "end": s.end.isoformat(),
                        "price": float(s.price / 1000),
                    }
                    for s in selected
                ],
            }
        if key in ("today_min", "today_max"):
            selected = day_slots(rows, today, self.coordinator.local_tz)
            if selected:
                slot = (min if key.endswith("min") else max)(selected, key=lambda s: s.price)
                return {"start": slot.start.isoformat(), "end": slot.end.isoformat()}
        if key.startswith("cheapest_window"):
            window = self._window()
            if window:
                return {
                    "start": window.start.isoformat(),
                    "end": window.end.isoformat(),
                    "average_price": float(window.average),
                    "price_type": "import",
                    "unit": "RON/kWh",
                    "duration_minutes": self.coordinator.options["window_minutes"],
                }
        if key in (
            "spot_price",
            "next_spot_price",
            "import_price",
            "export_price",
            "spot_price_mwh",
        ):
            slot = current_slot(rows, now)
            if slot and key == "next_spot_price":
                slot = current_slot(rows, slot.end)
            if slot:
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
                            "multiplier": self.coordinator.options[f"{kind}_multiplier"],
                            "adder_ron_kwh": self.coordinator.options[f"{kind}_adder"],
                            "formula": "spot_ron_kwh * multiplier + adder",
                        }
                    )
                return attrs
        return None

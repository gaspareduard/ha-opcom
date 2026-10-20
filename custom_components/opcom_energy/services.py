"""Response actions for charts, scripts and external optimisers."""

from datetime import date, timedelta

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .prices import (
    PriceError,
    TariffUnavailable,
    cheapest_window,
    day_bounds,
    day_slots,
    import_breakdown,
    price_kwh,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register read-only response actions after a successful setup."""

    def coordinator():
        entries = hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            if getattr(entry, "runtime_data", None):
                return entry.runtime_data
        raise ServiceValidationError("OPCOM Energy is not loaded")

    async def get_prices(call: ServiceCall) -> dict:
        coord = coordinator()
        now = dt_util.utcnow()
        day = (
            date.fromisoformat(call.data["date"])
            if "date" in call.data
            else now.astimezone(coord.local_tz).date()
        )
        start, end = day_bounds(day, coord.local_tz)
        rows = tuple(s for s in (coord.data or ()) if s.start < end and s.end > start)
        kind = call.data["price_type"]
        prices = []
        covered = True
        for slot in rows:
            record = {"start": slot.start.isoformat(), "end": slot.end.isoformat()}
            try:
                record["price"] = float(price_kwh(slot, coord.options, kind, coord.local_tz))
                if kind == "import" and coord.options.get("pricing_mode") == "components":
                    record["breakdown"] = import_breakdown(
                        slot, coord.options, coord.local_tz
                    ).attributes
            except TariffUnavailable:
                record.update(price=None, unavailable_reason="no_tariff")
                covered = False
            prices.append(record)
        return {
            "date": day.isoformat(),
            "timezone": hass.config.time_zone,
            "currency": "RON",
            "unit": "RON/kWh",
            "price_type": kind,
            "complete": covered and bool(day_slots(coord.data or (), day, coord.local_tz)),
            "prices": prices,
        }

    async def get_cheapest_window(call: ServiceCall) -> dict:
        coord = coordinator()
        now = dt_util.utcnow()
        earliest = (
            dt_util.parse_datetime(call.data["earliest_start"])
            if "earliest_start" in call.data
            else now
        )
        latest = (
            dt_util.parse_datetime(call.data["latest_end"])
            if "latest_end" in call.data
            else now + timedelta(hours=48)
        )
        if earliest is None or latest is None or earliest.tzinfo is None or latest.tzinfo is None:
            raise ServiceValidationError("Use ISO timestamps including a UTC offset")
        if earliest < now or latest <= earliest or latest - earliest > timedelta(hours=72):
            raise ServiceValidationError("Choose a future planning range of at most 72 hours")
        minutes = call.data.get("duration_minutes", coord.options["window_minutes"])
        kind = call.data["price_type"]
        try:
            result = cheapest_window(
                coord.data or (), earliest, latest, minutes, coord.options, kind, coord.local_tz
            )
        except PriceError as err:
            raise ServiceValidationError(str(err)) from err
        if result is None:
            raise ServiceValidationError("No complete published window fits the requested range")
        return {
            "start": result.start.isoformat(),
            "end": result.end.isoformat(),
            "average_price": float(result.average),
            "unit": "RON/kWh",
            "price_type": kind,
            "duration_minutes": minutes,
        }

    price_type = {vol.Optional("price_type", default="spot"): vol.In(("spot", "import", "export"))}
    hass.services.async_register(
        DOMAIN,
        "get_prices",
        get_prices,
        schema=vol.Schema(
            {
                vol.Optional("date"): vol.All(str, cv.date, lambda value: value.isoformat()),
                **price_type,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_cheapest_window",
        get_cheapest_window,
        schema=vol.Schema(
            {
                vol.Optional("earliest_start"): str,
                vol.Optional("latest_end"): str,
                vol.Optional("duration_minutes"): vol.All(
                    vol.Coerce(int), vol.Range(min=15, max=1440)
                ),
                **price_type,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

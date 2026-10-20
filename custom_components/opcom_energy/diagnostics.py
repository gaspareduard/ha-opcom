"""Diagnostics contain public prices and settings; no identifiers or credentials."""

from homeassistant.core import HomeAssistant

from . import OpcomConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: OpcomConfigEntry) -> dict:
    coord = entry.runtime_data
    return {
        "source": "opcom.ro",
        "timezone": hass.config.time_zone,
        "options": coord.options,
        "last_attempt": coord.last_attempt.isoformat() if coord.last_attempt else None,
        "last_success": coord.last_success.isoformat() if coord.last_success else None,
        "source_available": coord.source_available,
        "errors_by_market_day": dict(coord.errors),
        "cached_market_days": {
            key: {"intervals": len(coord.parsed[key]), "fetched_at": record["fetched_at"]}
            for key, record in coord.cache.items()
        },
    }

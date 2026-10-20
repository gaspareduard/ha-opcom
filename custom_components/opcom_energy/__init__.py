"""Open, direct OPCOM day-ahead prices for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import OpcomCoordinator
from .services import async_setup_services

type OpcomConfigEntry = ConfigEntry[OpcomCoordinator]

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: OpcomConfigEntry) -> bool:
    """Restore data before the first network request."""
    coordinator = OpcomCoordinator(hass, entry)
    await coordinator.async_load_cache()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start_clock()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    async_setup_services(hass)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: OpcomConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OpcomConfigEntry) -> bool:
    """Release timers/listeners and remove actions on successful unload."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    for service in ("get_prices", "get_cheapest_window"):
        hass.services.async_remove(DOMAIN, service)
    return True

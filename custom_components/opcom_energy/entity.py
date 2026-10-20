"""Common identity and metadata."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, SOURCE_URL, VERSION
from .coordinator import OpcomCoordinator


class OpcomEntity(CoordinatorEntity[OpcomCoordinator]):
    """Use one service device and stable unique IDs."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OpcomCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name=NAME,
            manufacturer="OPCOM (data source)",
            model="Romania day-ahead market",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=SOURCE_URL,
            sw_version=VERSION,
        )

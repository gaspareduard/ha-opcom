"""UI configuration for OPCOM Energy. No account or API key required."""

from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import CannotConnect, OpcomClient
from .const import DEFAULT_OPTIONS, DOMAIN, MARKET_TZ, NAME
from .prices import PriceError, parse_csv, validate_options


def options_schema(options: dict) -> vol.Schema:
    """Expose contract formulas and planning parameters with typed inputs."""
    defaults = DEFAULT_OPTIONS | options
    return vol.Schema(
        {
            vol.Required(key, default=value): (
                vol.All(vol.Coerce(int), vol.Range(min=15, max=1440))
                if key == "window_minutes"
                else vol.Coerce(float)
            )
            for key, value in defaults.items()
        }
    )


class OpcomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Only one Romanian market feed is needed per HA instance."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            try:
                day = dt_util.utcnow().astimezone(MARKET_TZ).date()
                text = await OpcomClient(async_get_clientsession(self.hass)).async_fetch(day)
                parse_csv(text, day)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except PriceError:
                errors["base"] = "invalid_data"
            else:
                return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OpcomOptionsFlow()


class OpcomOptionsFlow(OptionsFlow):
    """Change tariff formulas without deleting existing entities."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            if validate_options(user_input):
                return self.async_create_entry(title="", data=user_input)
            errors["base"] = "invalid_options"
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )

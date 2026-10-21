"""UI configuration for OPCOM Energy. No account or API key required."""

from copy import deepcopy
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .api import CannotConnect, async_create_client
from .const import DEFAULT_OPTIONS, DOMAIN, MARKET_TZ, NAME
from .prices import (
    PriceError,
    invoice_tariff,
    parse_csv,
    validate_options,
    validate_tariffs,
    yellowgrid_tariff,
)


def select(values):
    return SelectSelector(
        SelectSelectorConfig(
            options=values, mode=SelectSelectorMode.DROPDOWN, translation_key="tariff_options"
        )
    )


def number(low, high):
    return NumberSelector(
        NumberSelectorConfig(min=low, max=high, step="any", mode=NumberSelectorMode.BOX)
    )


def options_schema(options: dict) -> vol.Schema:
    """Expose contract formulas and planning parameters with typed inputs."""
    defaults = {key: options.get(key, value) for key, value in DEFAULT_OPTIONS.items()}
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
            client = async_create_client(self.hass, auto_cleanup=False)
            try:
                day = dt_util.utcnow().astimezone(MARKET_TZ).date()
                text = await client.async_fetch(day)
                parse_csv(text, day)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except PriceError:
                errors["base"] = "invalid_data"
            else:
                return self.async_create_entry(title=NAME, data={})
            finally:
                client.session.detach()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OpcomOptionsFlow()


class OpcomOptionsFlow(OptionsFlow):
    """Edit independent pricing modes and dated tariffs entirely through HA."""

    def __init__(self) -> None:
        self._version: dict = {}
        self._original_date: str | None = None
        self._component_index: int | None = None

    def _options(self) -> dict:
        return DEFAULT_OPTIONS | deepcopy(dict(self.config_entry.options))

    def _save(self, updates: dict) -> ConfigFlowResult:
        options = self._options() | updates
        validate_tariffs(options.get("tariff_versions", []))
        return self.async_create_entry(title="", data=options)

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["simple", "pricing", "tariffs"])

    async def async_step_simple(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            if validate_options(user_input):
                return self._save(user_input)
            errors["base"] = "invalid_options"
        return self.async_show_form(
            step_id="simple",
            data_schema=options_schema(user_input or self._options()),
            errors=errors,
        )

    async def async_step_pricing(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(
            step_id="pricing",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "pricing_mode", default=self._options().get("pricing_mode", "simple")
                    ): select(["simple", "components"]),
                }
            ),
        )

    async def async_step_tariffs(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="tariffs", menu_options=["add_tariff", "edit_tariff", "delete_tariff"]
        )

    async def async_step_add_tariff(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            if any(
                v["effective_from"] == user_input["effective_from"]
                for v in self._options().get("tariff_versions", [])
            ):
                errors["base"] = "duplicate_date"
            else:
                self._original_date = None
                self._version = (
                    yellowgrid_tariff
                    if user_input["template"] == "yellowgrid_chart"
                    else invoice_tariff
                )(user_input["effective_from"], self.hass.config.language)
                if user_input["template"] == "empty":
                    self._version["components"] = []
                return await self.async_step_version()
        return self.async_show_form(
            step_id="add_tariff",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("effective_from"): DateSelector(),
                    vol.Required("template", default="yellowgrid_chart"): select(
                        ["yellowgrid_chart", "empty"]
                    ),
                }
            ),
        )

    async def _choose_version(self, step_id, user_input):
        versions = self._options().get("tariff_versions", [])
        if not versions:
            return self.async_abort(reason="no_tariffs")
        if user_input is not None:
            chosen = user_input["effective_from"]
            if step_id == "delete_tariff":
                return self._save(
                    {"tariff_versions": [v for v in versions if v["effective_from"] != chosen]}
                )
            self._original_date = chosen
            self._version = deepcopy(next(v for v in versions if v["effective_from"] == chosen))
            return await self.async_step_version()
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required("effective_from"): select(
                        sorted(v["effective_from"] for v in versions)
                    ),
                }
            ),
        )

    async def async_step_edit_tariff(self, user_input=None) -> ConfigFlowResult:
        return await self._choose_version("edit_tariff", user_input)

    async def async_step_delete_tariff(self, user_input=None) -> ConfigFlowResult:
        return await self._choose_version("delete_tariff", user_input)

    async def async_step_version(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            version = self._version | user_input
            others = [
                v
                for v in self._options().get("tariff_versions", [])
                if v["effective_from"] != self._original_date
            ]
            try:
                validate_tariffs(others + [version])
            except PriceError:
                errors["base"] = "invalid_tariff"
            else:
                self._version = version
                return await self.async_step_tariff_details()
        defaults = self._version | (user_input or {})
        return self.async_show_form(
            step_id="version",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "effective_from", default=defaults["effective_from"]
                    ): DateSelector(),
                    vol.Required(
                        "energy_multiplier", default=defaults["energy_multiplier"]
                    ): number(0, 100),
                    vol.Required("energy_adder", default=defaults["energy_adder"]): number(
                        -10000, 10000
                    ),
                    vol.Required("energy_vat", default=defaults["energy_vat"]): number(0, 100),
                    **(
                        {
                            vol.Required(key, default=defaults.get(key, 1.31)): number(0, high)
                            for key, high in (
                                ("import_cap", 10000),
                                ("final_import_cap", 10000),
                                ("export_floor", 10000),
                                ("commission", 100),
                            )
                        }
                        if defaults.get("energy_model") == "yellowgrid"
                        else {}
                    ),
                }
            ),
        )

    async def async_step_tariff_details(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="tariff_details",
            menu_options=["add_component", "edit_component", "remove_component", "save_tariff"],
        )

    async def async_step_add_component(self, user_input=None) -> ConfigFlowResult:
        self._component_index = None
        return await self.async_step_component()

    async def _choose_component(self, step_id, user_input):
        components = self._version["components"]
        if not components:
            return self.async_abort(reason="no_components")
        if user_input is not None:
            index = int(user_input["component"])
            if step_id == "remove_component":
                del components[index]
                return await self.async_step_tariff_details()
            self._component_index = index
            return await self.async_step_component()
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required("component"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": str(i), "label": c["name"]}
                                for i, c in enumerate(components)
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_component(self, user_input=None) -> ConfigFlowResult:
        return await self._choose_component("edit_component", user_input)

    async def async_step_remove_component(self, user_input=None) -> ConfigFlowResult:
        return await self._choose_component("remove_component", user_input)

    async def async_step_component(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        defaults = {"name": "", "rate": 0.0, "vat": 21.0, "enabled": True, "vat_verified": False}
        if self._component_index is not None:
            defaults |= self._version["components"][self._component_index]
        if user_input is not None:
            components = deepcopy(self._version["components"])
            if self._component_index is None:
                components.append(user_input)
            else:
                components[self._component_index] = user_input
            try:
                validate_tariffs([self._version | {"components": components}])
            except PriceError:
                errors["base"] = "invalid_tariff"
            else:
                self._version["components"] = components
                return await self.async_step_tariff_details()
        defaults |= user_input or {}
        return self.async_show_form(
            step_id="component",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=defaults["name"]): str,
                    vol.Required("rate", default=defaults["rate"]): number(-10000, 10000),
                    vol.Required("vat", default=defaults["vat"]): number(0, 100),
                    vol.Required("enabled", default=defaults["enabled"]): bool,
                    vol.Required("vat_verified", default=defaults["vat_verified"]): bool,
                }
            ),
        )

    async def async_step_save_tariff(self, user_input=None) -> ConfigFlowResult:
        versions = [
            v
            for v in self._options().get("tariff_versions", [])
            if v["effective_from"] != self._original_date
        ]
        versions.append(self._version)
        return self._save({"tariff_versions": sorted(versions, key=lambda v: v["effective_from"])})

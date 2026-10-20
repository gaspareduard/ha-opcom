"""Exercise the real HA config entry, coordinator, entities and actions."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.opcom_energy.api import CannotConnect
from custom_components.opcom_energy.const import DEFAULT_OPTIONS, DOMAIN
from custom_components.opcom_energy.prices import NotPublished

pytestmark = pytest.mark.usefixtures("freezer")


@pytest.fixture(autouse=True)
async def time_and_zone(hass, freezer):
    freezer.move_to("2026-10-20T12:00:00+00:00")
    await hass.config.async_set_time_zone("Europe/Berlin")


@pytest.fixture
def fetch(csv_text):
    async def load(day):
        try:
            return csv_text(day.isoformat())
        except FileNotFoundError as err:
            raise NotPublished("Not yet published") from err

    with patch(
        "custom_components.opcom_energy.api.OpcomClient.async_fetch", side_effect=load
    ) as mock:
        yield mock


async def setup(hass, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, title="OPCOM Energy", unique_id=DOMAIN, data={}, options=options or {}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def find(hass, suffix):
    states = [
        s
        for s in hass.states.async_all()
        if s.entity_id.split(".", 1)[1] == f"opcom_energy_{suffix}"
    ]
    assert len(states) == 1, [(s.entity_id, s.state) for s in hass.states.async_all()]
    return states[0]


async def test_setup_entities_and_actions(hass, fetch):
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    spot = find(hass, "spot_price")
    assert float(spot.state) > 0
    assert spot.attributes["unit_of_measurement"] == "RON/kWh"
    assert find(hass, "tomorrow_schedule_complete").state == "on"
    response = await hass.services.async_call(
        DOMAIN, "get_prices", {"date": "2026-10-20"}, blocking=True, return_response=True
    )
    assert response["complete"] is True
    assert len(response["prices"]) == 96
    result = await hass.services.async_call(
        DOMAIN,
        "get_cheapest_window",
        {"duration_minutes": 120, "price_type": "import"},
        blocking=True,
        return_response=True,
    )
    assert datetime.fromisoformat(result["end"]) - datetime.fromisoformat(
        result["start"]
    ) == timedelta(hours=2)
    assert datetime.fromisoformat(result["start"]) >= dt_util.utcnow()
    assert result["price_type"] == "import"
    for data in (
        {"duration_minutes": 31},
        {"earliest_start": "2026-10-20T13:00:00"},
        {"earliest_start": "2026-10-19T13:00:00+00:00"},
    ):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, "get_cheapest_window", data, blocking=True, return_response=True
            )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "get_prices")


async def test_clock_updates_without_network(hass, fetch, freezer):
    await setup(hass)
    calls = fetch.call_count
    first = find(hass, "spot_price").attributes["start"]
    freezer.move_to("2026-10-20T12:15:00+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert find(hass, "spot_price").attributes["start"] != first
    assert fetch.call_count == calls


async def test_failure_preserves_price_then_expires(hass, fetch, freezer):
    entry = await setup(hass)
    original = find(hass, "spot_price").state
    fetch.side_effect = CannotConnect("offline")
    entry.runtime_data.cache.clear()  # Force refresh rather than 6h source throttle.
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert find(hass, "spot_price").state == original
    assert find(hass, "source_available").state == "off"
    freezer.move_to("2026-10-22T02:00:00+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert find(hass, "spot_price").state == STATE_UNAVAILABLE


async def test_config_flow_and_duplicate(hass, fetch):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.opcom_energy.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["reason"] == "already_configured"


async def test_config_flow_connection_error(hass):
    with patch(
        "custom_components.opcom_energy.api.OpcomClient.async_fetch", side_effect=CannotConnect
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_validation_and_reload(hass, fetch):
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "simple"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], DEFAULT_OPTIONS | {"window_minutes": 31}
    )
    assert result["errors"] == {"base": "invalid_options"}
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload", return_value=True
    ) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], DEFAULT_OPTIONS | {"import_adder": 0.4}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["import_adder"] == 0.4
    reload.assert_called_once_with(entry.entry_id)


async def test_cached_offline_startup(hass, fetch):
    entry = await setup(hass)
    stored = {"days": dict(entry.runtime_data.cache)}
    assert await hass.config_entries.async_unload(entry.entry_id)
    fetch.side_effect = CannotConnect("offline")
    with patch("homeassistant.helpers.storage.Store.async_load", return_value=stored):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert find(hass, "spot_price").state != STATE_UNAVAILABLE


async def test_unpublished_tomorrow_retains_today(hass, csv_text):
    async def load(day):
        if day == date(2026, 10, 20):
            return csv_text("2026-10-20")
        raise NotPublished("Not yet published")

    with patch("custom_components.opcom_energy.api.OpcomClient.async_fetch", side_effect=load):
        await setup(hass)
    assert find(hass, "tomorrow_schedule_complete").state == "off"
    assert find(hass, "tomorrow_average").state == STATE_UNAVAILABLE
    assert find(hass, "spot_price").state != STATE_UNAVAILABLE


async def test_diagnostics_and_partial_prices(hass, fetch):
    from custom_components.opcom_energy.diagnostics import async_get_config_entry_diagnostics

    entry = await setup(hass)
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["cached_market_days"]["2026-10-20"]["intervals"] == 96
    assert "entry_id" not in data
    response = await hass.services.async_call(
        DOMAIN, "get_prices", {"date": "2026-10-25"}, blocking=True, return_response=True
    )
    assert response["complete"] is False
    assert response["prices"] == []
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_cheapest_window",
            {
                "earliest_start": "2026-10-23T00:00:00+00:00",
                "latest_end": "2026-10-23T01:00:00+00:00",
            },
            blocking=True,
            return_response=True,
        )


async def test_corrupt_cache_is_ignored(hass, fetch):
    stored = {
        "days": {
            "2026-10-20": {"csv": None},
            "bad": {"csv": "bad", "fetched_at": "bad"},
            "2026-10-19": {"csv": "bad", "fetched_at": "bad"},
        }
    }
    with patch("homeassistant.helpers.storage.Store.async_load", return_value=stored):
        await setup(hass)
    assert find(hass, "spot_price").state != STATE_UNAVAILABLE


async def test_first_setup_offline_is_retried(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="OPCOM Energy", unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.opcom_energy.api.OpcomClient.async_fetch", side_effect=CannotConnect
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.services.has_service(DOMAIN, "get_prices")


async def test_no_price_signal_when_schedule_incomplete(hass, fetch):
    entry = await setup(hass)
    rows = entry.runtime_data.data
    entry.runtime_data.async_set_updated_data(rows[1:])
    await hass.async_block_till_done()
    assert find(hass, "cheap_now").state == STATE_UNAVAILABLE
    assert find(hass, "spot_price").state != STATE_UNAVAILABLE


async def test_romanian_calendar_day(hass, fetch, csv_text):
    await hass.config.async_set_time_zone("Europe/Bucharest")
    # The previous market day supplies midnight–01:00 Romania.
    previous = csv_text("2026-10-20").replace("20/10/2026", "19/10/2026")

    async def load(day):
        if day == date(2026, 10, 19):
            return previous
        return csv_text(day.isoformat())

    fetch.side_effect = load
    await setup(hass)
    response = await hass.services.async_call(
        DOMAIN, "get_prices", {"date": "2026-10-20"}, blocking=True, return_response=True
    )
    assert response["complete"] is True
    assert response["prices"][0]["start"] == "2026-10-19T21:00:00+00:00"
    assert response["prices"][-1]["end"] == "2026-10-20T21:00:00+00:00"


@pytest.mark.parametrize(
    ("first", "second", "count"),
    [
        ("2025-10-26T00:15:00+00:00", "2025-10-26T01:15:00+00:00", 100),
        ("2026-03-29T00:45:00+00:00", "2026-03-29T01:00:00+00:00", 92),
    ],
)
async def test_ha_clock_across_dst(hass, fetch, freezer, first, second, count):
    freezer.move_to(first)
    await setup(hass)
    before = find(hass, "spot_price").attributes["start"]
    freezer.move_to(second)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    after = find(hass, "spot_price").attributes["start"]
    assert before == first
    assert after == second
    response = await hass.services.async_call(
        DOMAIN, "get_prices", {}, blocking=True, return_response=True
    )
    assert response["complete"] is True
    assert len(response["prices"]) == count


async def test_schedules_keep_wholesale_units_with_tariff_adjustments(hass, fetch, csv_text):
    async def load(day):
        return csv_text(day.isoformat()).replace('"1565.25"', '"-100.00"')

    fetch.side_effect = load
    await setup(hass, {"import_multiplier": 1.21, "import_adder": 0.35})
    for suffix, day in (("today_average", "2026-10-20"), ("tomorrow_average", "2026-10-21")):
        schedule = find(hass, suffix)
        response = await hass.services.async_call(
            DOMAIN, "get_prices", {"date": day}, blocking=True, return_response=True
        )
        assert schedule.attributes["prices"] == response["prices"]
        assert float(schedule.state) == pytest.approx(
            sum(row["price"] for row in response["prices"]) / len(response["prices"])
        )
    assert find(hass, "today_average").attributes["prices"][0]["price"] == -0.1
    spot = find(hass, "spot_price")
    imported = find(hass, "estimated_import_price")
    assert float(imported.state) == pytest.approx(float(spot.state) * 1.21 + 0.35)
    assert imported.attributes["start"] == spot.attributes["start"]
    assert imported.attributes["end"] == spot.attributes["end"]


@pytest.mark.parametrize(("suffix", "select"), [("today_minimum", min), ("today_maximum", max)])
async def test_extreme_value_matches_interval_metadata(hass, fetch, suffix, select):
    await setup(hass)
    schedule = find(hass, "today_average").attributes["prices"]
    expected = select(schedule, key=lambda row: row["price"])
    extreme = find(hass, suffix)
    assert float(extreme.state) == expected["price"]
    assert extreme.attributes["start"] == expected["start"]
    assert extreme.attributes["end"] == expected["end"]


async def test_next_price_rolls_over_with_its_metadata(hass, fetch, freezer):
    freezer.move_to("2026-10-20T21:45:00+00:00")
    await setup(hass)
    following = find(hass, "next_spot_price")
    first_tomorrow = find(hass, "tomorrow_average").attributes["prices"][0]
    assert float(following.state) == first_tomorrow["price"]
    assert following.attributes["start"] == first_tomorrow["start"]
    assert following.attributes["end"] == first_tomorrow["end"]
    freezer.move_to("2026-10-20T22:00:00+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    current = find(hass, "spot_price")
    assert current.state == following.state
    assert current.attributes["start"] == following.attributes["start"]
    assert current.attributes["end"] == following.attributes["end"]


async def test_sensor_properties_share_a_reading_until_next_update(hass, fetch, freezer):
    from homeassistant.helpers.entity_platform import async_get_platforms

    await setup(hass)
    entity = next(
        entity
        for platform in async_get_platforms(hass, DOMAIN)
        for entity in platform.entities.values()
        if entity.entity_id == "sensor.opcom_energy_spot_price"
    )
    value = entity.native_value
    attrs = dict(entity.extra_state_attributes)
    # A clock crossing between property reads must not mix old and new intervals.
    freezer.move_to("2026-10-20T12:15:00+00:00")
    assert entity.native_value == value
    assert entity.extra_state_attributes == attrs
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert entity.extra_state_attributes["start"] == "2026-10-20T12:15:00+00:00"
    assert float(entity.native_value) == float(find(hass, "spot_price").state)


async def options_step(hass, entry, step):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def submit(hass, result, data):
    return await hass.config_entries.options.async_configure(result["flow_id"], data)


async def test_invoice_components_ui_and_mode_switch_preserve_simple(hass, fetch):
    entry = await setup(hass, {"import_multiplier": 1.21, "import_adder": 0.56})
    original = find(hass, "estimated_import_price").state
    result = await options_step(hass, entry, "tariffs")
    result = await submit(hass, result, {"next_step_id": "add_tariff"})
    result = await submit(
        hass, result, {"effective_from": "2026-09-01", "template": "invoice_2026_09"}
    )
    assert result["step_id"] == "version"
    result = await submit(
        hass,
        result,
        {
            "effective_from": "2026-09-01",
            "energy_multiplier": 1,
            "energy_adder": 0,
            "energy_vat": 21,
        },
    )
    result = await submit(hass, result, {"next_step_id": "edit_component"})
    result = await submit(hass, result, {"component": "8"})
    assert result["step_id"] == "component"
    result = await submit(
        hass,
        result,
        {
            "name": "CfD contribution",
            "rate": 0.000144,
            "vat": 0,
            "enabled": True,
            "vat_verified": True,
        },
    )
    result = await submit(hass, result, {"next_step_id": "save_tariff"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["import_multiplier"] == 1.21
    assert find(hass, "estimated_import_price").state == original
    assert entry.options["tariff_versions"][0]["components"][8]["vat"] == 0
    result = await options_step(hass, entry, "pricing")
    await submit(hass, result, {"pricing_mode": "components"})
    await hass.async_block_till_done()
    spot = float(find(hass, "spot_price").state)
    assert float(find(hass, "estimated_import_price").state) == pytest.approx(
        spot * 1.21 + 0.562478432
    )
    assert float(find(hass, "import_additional_charges_before_vat").state) == 0.4648832
    assert find(hass, "estimated_import_price").attributes["unverified_vat_components"] == []
    # Returning to simple mode restores the same formula without losing tariffs.
    result = await options_step(hass, entry, "pricing")
    await submit(hass, result, {"pricing_mode": "simple"})
    await hass.async_block_till_done()
    assert find(hass, "estimated_import_price").state == original
    assert len(entry.options["tariff_versions"]) == 1


async def test_tariff_ui_custom_components_edit_validation_and_delete(hass, fetch):
    from custom_components.opcom_energy.prices import invoice_tariff

    version = invoice_tariff("2026-09-01")
    version["components"] = []
    entry = await setup(hass, {"tariff_versions": [version]})
    result = await options_step(hass, entry, "tariffs")
    result = await submit(hass, result, {"next_step_id": "add_tariff"})
    result = await submit(hass, result, {"effective_from": "2026-09-01", "template": "empty"})
    assert result["errors"] == {"base": "duplicate_date"}
    result = await submit(hass, result, {"effective_from": "2026-11-01", "template": "empty"})
    base = {
        "effective_from": "2026-11-01",
        "energy_multiplier": 1,
        "energy_adder": 0,
        "energy_vat": 21,
    }
    result = await submit(hass, result, base)
    result = await submit(hass, result, {"next_step_id": "add_component"})
    component = {
        "name": "Custom fee",
        "rate": 0.1,
        "vat": 21,
        "enabled": True,
        "vat_verified": False,
    }
    result = await submit(hass, result, component | {"name": " "})
    assert result["errors"] == {"base": "invalid_tariff"}
    result = await submit(hass, result, component)
    result = await submit(hass, result, {"next_step_id": "add_component"})
    result = await submit(hass, result, component)
    assert result["errors"] == {"base": "invalid_tariff"}
    result = await submit(hass, result, component | {"name": "Second", "enabled": False})
    result = await submit(hass, result, {"next_step_id": "remove_component"})
    result = await submit(hass, result, {"component": "1"})
    result = await submit(hass, result, {"next_step_id": "save_tariff"})
    await hass.async_block_till_done()
    assert len(entry.options["tariff_versions"]) == 2
    assert len(entry.options["tariff_versions"][1]["components"]) == 1
    # Edit date and base energy, then delete the later version without touching the earlier one.
    result = await options_step(hass, entry, "tariffs")
    result = await submit(hass, result, {"next_step_id": "edit_tariff"})
    result = await submit(hass, result, {"effective_from": "2026-11-01"})
    result = await submit(hass, result, base | {"effective_from": "2026-09-01"})
    assert result["errors"] == {"base": "invalid_tariff"}
    result = await submit(hass, result, base | {"energy_adder": 0.2})
    result = await submit(hass, result, {"next_step_id": "save_tariff"})
    await hass.async_block_till_done()
    assert entry.options["tariff_versions"][1]["energy_adder"] == 0.2
    result = await options_step(hass, entry, "tariffs")
    result = await submit(hass, result, {"next_step_id": "delete_tariff"})
    await submit(hass, result, {"effective_from": "2026-11-01"})
    await hass.async_block_till_done()
    assert [v["effective_from"] for v in entry.options["tariff_versions"]] == ["2026-09-01"]


@pytest.mark.parametrize("step", ["edit_tariff", "delete_tariff"])
async def test_empty_tariffs_ui(hass, fetch, step):
    entry = await setup(hass)
    result = await options_step(hass, entry, "tariffs")
    result = await submit(hass, result, {"next_step_id": step})
    assert result["reason"] == "no_tariffs"


@pytest.mark.parametrize("step", ["edit_component", "remove_component"])
async def test_empty_components_ui(hass, fetch, step):
    entry = await setup(hass)
    result = await options_step(hass, entry, "tariffs")
    result = await submit(hass, result, {"next_step_id": "add_tariff"})
    result = await submit(hass, result, {"effective_from": "2026-09-01", "template": "empty"})
    result = await submit(
        hass,
        result,
        {
            "effective_from": "2026-09-01",
            "energy_multiplier": 1,
            "energy_adder": 0,
            "energy_vat": 21,
        },
    )
    result = await submit(hass, result, {"next_step_id": step})
    assert result["reason"] == "no_components"


async def test_no_tariff_coverage_unavailable_total_raw_and_export_unchanged(hass, fetch):
    from custom_components.opcom_energy.prices import invoice_tariff

    entry = await setup(
        hass, {"pricing_mode": "components", "tariff_versions": [invoice_tariff("2026-11-01")]}
    )
    assert find(hass, "estimated_import_price").state == STATE_UNAVAILABLE
    assert find(hass, "import_vat_amount").state == STATE_UNAVAILABLE
    assert find(hass, "import_price_below_threshold").state == STATE_UNAVAILABLE
    assert find(hass, "cheapest_future_window_price").state == STATE_UNAVAILABLE
    assert find(hass, "spot_price").state != STATE_UNAVAILABLE
    imported = await hass.services.async_call(
        DOMAIN, "get_prices", {"price_type": "import"}, blocking=True, return_response=True
    )
    assert imported["complete"] is False
    assert all(
        row["price"] is None and row["unavailable_reason"] == "no_tariff"
        for row in imported["prices"]
    )
    exported = await hass.services.async_call(
        DOMAIN, "get_prices", {"price_type": "export"}, blocking=True, return_response=True
    )
    raw = await hass.services.async_call(
        DOMAIN, "get_prices", {}, blocking=True, return_response=True
    )
    assert exported["prices"] == raw["prices"]
    assert raw["complete"] is True
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_cheapest_window",
            {"price_type": "import"},
            blocking=True,
            return_response=True,
        )
    assert entry.options["pricing_mode"] == "components"


async def test_import_schedule_local_midnight_breakdown_and_offline_restart(hass, fetch):
    from custom_components.opcom_energy.prices import invoice_tariff

    await hass.config.async_set_time_zone("Europe/Bucharest")
    first = invoice_tariff("2026-09-01")
    first.update(components=[], energy_vat=0)
    later = invoice_tariff("2026-10-21")
    later.update(components=[], energy_vat=0, energy_adder=1)
    entry = await setup(hass, {"pricing_mode": "components", "tariff_versions": [first, later]})
    response = await hass.services.async_call(
        DOMAIN,
        "get_prices",
        {"date": "2026-10-21", "price_type": "import"},
        blocking=True,
        return_response=True,
    )
    assert response["complete"] is True
    assert response["prices"][0]["start"] == "2026-10-20T21:00:00+00:00"
    for row in response["prices"]:
        assert row["breakdown"]["tariff_effective_from"] == "2026-10-21"
        assert row["breakdown"]["energy_adder"] == 1
        assert row["price"] == row["breakdown"]["estimated_total"]
    before = find(hass, "estimated_import_price").state
    await entry.runtime_data.store.async_save({"days": entry.runtime_data.cache})
    assert await hass.config_entries.async_unload(entry.entry_id)
    fetch.side_effect = CannotConnect("offline")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert find(hass, "estimated_import_price").state == before
    assert entry.runtime_data.options["tariff_versions"] == [first, later]


async def test_component_sensors_and_threshold_switch_at_ha_local_midnight(hass, fetch, freezer):
    from custom_components.opcom_energy.prices import invoice_tariff

    await hass.config.async_set_time_zone("Europe/Bucharest")
    freezer.move_to("2026-10-20T20:45:00+00:00")
    first = invoice_tariff("2026-09-01")
    first.update(components=[], energy_vat=0)
    later = invoice_tariff("2026-10-21")
    later.update(components=[], energy_vat=100, energy_adder=10)
    await setup(
        hass,
        {"pricing_mode": "components", "tariff_versions": [first, later], "cheap_threshold": 5},
    )
    assert find(hass, "import_price_below_threshold").state == "on"
    assert find(hass, "estimated_import_price").attributes["tariff_effective_from"] == "2026-09-01"
    freezer.move_to("2026-10-20T21:00:00+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    spot = float(find(hass, "spot_price").state)
    assert float(find(hass, "import_base_energy_before_vat").state) == pytest.approx(spot + 10)
    assert float(find(hass, "import_vat_amount").state) == pytest.approx(spot + 10)
    assert float(find(hass, "estimated_import_price").state) == pytest.approx((spot + 10) * 2)
    assert find(hass, "estimated_import_price").attributes["tariff_effective_from"] == "2026-10-21"
    assert find(hass, "import_price_below_threshold").state == "off"


async def test_new_mode_can_save_without_versions_and_reports_missing_coverage(hass, fetch):
    entry = await setup(hass)
    result = await options_step(hass, entry, "pricing")
    await submit(hass, result, {"pricing_mode": "components"})
    await hass.async_block_till_done()
    assert find(hass, "estimated_import_price").state == STATE_UNAVAILABLE
    assert find(hass, "spot_price").state != STATE_UNAVAILABLE


async def test_invalid_restored_tariffs_report_setup_error(hass, fetch):
    from custom_components.opcom_energy.prices import invoice_tariff

    version = invoice_tariff("2026-09-01")
    version["energy_vat"] = float("inf")
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"tariff_versions": [version]})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR

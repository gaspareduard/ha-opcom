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

"""Regression tests for real CSV schemas, DST, price conversion and planning."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.opcom_energy.const import DEFAULT_OPTIONS, MARKET_TZ
from custom_components.opcom_energy.prices import (
    NotPublished,
    PriceError,
    PriceSlot,
    average_price,
    cheapest_window,
    current_slot,
    day_slots,
    parse_csv,
    percentile,
    price_kwh,
    validate_options,
)


@pytest.mark.parametrize(
    ("day", "count"), [("2026-10-20", 96), ("2026-03-29", 92), ("2025-10-26", 100)]
)
def test_real_market_days(csv_text, day, count):
    slots = parse_csv(csv_text(day), date.fromisoformat(day))
    assert len(slots) == count
    assert slots[0].start.astimezone(MARKET_TZ).hour == 0
    assert slots[-1].end.astimezone(MARKET_TZ).date() == date.fromisoformat(day) + timedelta(days=1)
    assert all(s.end - s.start == timedelta(minutes=15) for s in slots)
    assert len({s.start for s in slots}) == count
    assert day_slots(slots, date.fromisoformat(day), MARKET_TZ) == slots


def test_fall_repeated_hour(csv_text):
    slots = parse_csv(csv_text("2025-10-26"), date(2025, 10, 26))
    first = datetime(2025, 10, 26, 0, 15, tzinfo=UTC)
    second = first + timedelta(hours=1)
    assert current_slot(slots, first) == slots[9]
    assert current_slot(slots, second) == slots[13]
    assert first.astimezone(MARKET_TZ).hour == second.astimezone(MARKET_TZ).hour == 2
    assert current_slot(slots, slots[-1].end) is None


def test_reject_corrupt_source(csv_text):
    text = csv_text("2026-10-20")
    day = date(2026, 10, 20)
    for bad in (
        text.replace('"Romania","1",', '"Romania","2",'),
        text.replace('"1565.25"', '"NaN"'),
        text.replace('"PT15M"', '"PT60M"'),
        text.replace('"Romania","96",', '"Missing","96",'),
        "<html>Maintenance</html>",
    ):
        with pytest.raises(PriceError):
            parse_csv(bad, day)
    with pytest.raises(PriceError):
        parse_csv(text, day + timedelta(days=1))
    with pytest.raises(NotPublished):
        parse_csv("", day)


def test_local_today_requires_previous_market_day(csv_text):
    slots = parse_csv(csv_text("2026-10-20"), date(2026, 10, 20))
    ro = ZoneInfo("Europe/Bucharest")
    assert day_slots(slots, date(2026, 10, 20), ro) == ()
    # The previous market day's last hour is needed for Romanian midnight.
    previous = tuple(
        PriceSlot(
            slots[0].start - timedelta(hours=1) + timedelta(minutes=i * 15),
            slots[0].start - timedelta(hours=1) + timedelta(minutes=(i + 1) * 15),
            Decimal(10),
        )
        for i in range(4)
    )
    complete = day_slots(previous + slots, date(2026, 10, 20), ro)
    assert len(complete) == 96
    assert complete[0].start.astimezone(ro).hour == 0
    assert complete[-1].end.astimezone(ro).hour == 0
    assert day_slots(previous + slots[:40] + slots[41:], date(2026, 10, 20), ro) == ()


def test_negative_prices_and_tariffs():
    start = datetime(2026, 10, 20, tzinfo=UTC)
    slot = PriceSlot(start, start + timedelta(minutes=15), Decimal("-100"))
    options = DEFAULT_OPTIONS | {"import_multiplier": 1.21, "import_adder": 0.5}
    assert price_kwh(slot, options) == Decimal("-0.1")
    assert price_kwh(slot, options, "import") == Decimal("0.379")
    assert price_kwh(slot, options, "export") == Decimal("-0.10")


def test_global_window_and_gaps():
    start = datetime(2026, 10, 20, tzinfo=UTC)
    slots = tuple(
        PriceSlot(
            start + timedelta(minutes=15 * i), start + timedelta(minutes=15 * (i + 1)), Decimal(p)
        )
        for i, p in enumerate([200, -100, -100, 200, 200, -300])
    )
    result = cheapest_window(slots, start, slots[-1].end, 30, DEFAULT_OPTIONS)
    assert result.start == slots[1].start
    assert result.average == Decimal("-0.1")
    # An isolated lowest slot must not bridge an unpublished gap.
    assert cheapest_window((slots[0], slots[-1]), start, slots[-1].end, 30, DEFAULT_OPTIONS) is None
    assert (
        cheapest_window(
            slots, slots[-1].start + timedelta(seconds=1), slots[-1].end, 15, DEFAULT_OPTIONS
        )
        is None
    )
    with pytest.raises(PriceError):
        cheapest_window(slots, start, slots[-1].end, 31, DEFAULT_OPTIONS)
    assert average_price(slots, DEFAULT_OPTIONS) == Decimal(100) / 6000
    assert percentile(slots, slots[-1]) == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"import_adder": float("nan")},
        {"window_minutes": 31},
        {"cheap_percentile": 101},
        {"import_multiplier": -1},
    ],
)
def test_invalid_options(bad):
    assert not validate_options(DEFAULT_OPTIONS | bad)


def test_invalid_title_date(csv_text):
    with pytest.raises(PriceError):
        parse_csv(csv_text("2026-10-20").replace("20/10/2026", "99/99/2026"), date(2026, 10, 20))

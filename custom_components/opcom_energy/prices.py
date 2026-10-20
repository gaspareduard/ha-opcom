"""Validated market intervals and planning, independent of Home Assistant."""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .const import MARKET_TZ, SLOT_LENGTH


class PriceError(ValueError):
    """The source did not provide a valid complete market day."""


class NotPublished(PriceError):
    """The source returned an empty, not-yet-published day."""


@dataclass(frozen=True, slots=True)
class PriceSlot:
    """A half-open UTC interval; spot price is always RON/MWh."""

    start: datetime
    end: datetime
    price: Decimal


@dataclass(frozen=True, slots=True)
class Window:
    """A contiguous window, priced in RON/kWh."""

    start: datetime
    end: datetime
    average: Decimal


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Convert local midnights separately, preserving 23/25-hour days."""
    return (
        datetime.combine(day, time.min, tz).astimezone(UTC),
        datetime.combine(day + timedelta(days=1), time.min, tz).astimezone(UTC),
    )


def parse_csv(text: str, day: date) -> tuple[PriceSlot, ...]:
    """Validate date, schema, resolution, sequence, prices and DST row count."""
    if not text.strip():
        raise NotPublished(f"No prices published for {day}")
    title = re.search(r"livrare:\s*(\d{1,2})/(\d{1,2})/(\d{4})", text)
    try:
        title_day = date(*(int(title[i]) for i in (3, 2, 1))) if title else None
    except ValueError as err:
        raise PriceError("Invalid delivery date") from err
    if title_day != day:
        raise PriceError("Missing or mismatched delivery date")
    start, end = day_bounds(day, MARKET_TZ)
    expected = int((end - start) / SLOT_LENGTH)
    values: dict[int, Decimal] = {}
    header: list[str] | None = None
    try:
        for row in csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True):
            row = [cell.strip() for cell in row]
            if row and row[0] == "Zona de tranzactionare":
                header = row
                if not all(
                    column in header
                    for column in (
                        "Interval",
                        "Pret de Inchidere a Pietei [lei/MWh]",
                        "Rezolutie",
                    )
                ):
                    raise PriceError("Unexpected price table header")
                continue
            if not row or row[0] != "Romania":
                continue
            if header is None or len(row) != len(header):
                raise PriceError("Price row has no matching header")
            record = dict(zip(header, row, strict=True))
            if record["Rezolutie"] != "PT15M":
                raise PriceError("Unexpected market resolution")
            number = int(record["Interval"])
            raw = (
                record["Pret de Inchidere a Pietei [lei/MWh]"]
                .replace("\u00a0", "")
                .replace(" ", "")
            )
            if "," in raw:
                raw = raw.replace(".", "").replace(",", ".")
            price = Decimal(raw)
            if not price.is_finite() or number in values or not 1 <= number <= expected:
                raise PriceError("Invalid price or duplicate/out-of-range interval")
            values[number] = price
    except (csv.Error, InvalidOperation, KeyError, ValueError) as err:
        raise PriceError(f"Invalid OPCOM CSV: {err}") from err
    if set(values) != set(range(1, expected + 1)):
        raise PriceError(f"Expected {expected} intervals, got {len(values)}")
    return tuple(
        PriceSlot(start + (i - 1) * SLOT_LENGTH, start + i * SLOT_LENGTH, values[i])
        for i in range(1, expected + 1)
    )


def current_slot(slots: tuple[PriceSlot, ...], now: datetime) -> PriceSlot | None:
    """Never extend an expired price into an uncovered interval."""
    return next((s for s in slots if s.start <= now < s.end), None)


def day_slots(slots: tuple[PriceSlot, ...], day: date, tz: ZoneInfo) -> tuple[PriceSlot, ...]:
    """Return only a completely covered local calendar day."""
    start, end = day_bounds(day, tz)
    selected = tuple(s for s in slots if s.start < end and s.end > start)
    if not selected or selected[0].start > start or selected[-1].end < end:
        return ()
    if any(a.end != b.start for a, b in zip(selected, selected[1:], strict=False)):
        return ()
    return selected


def price_kwh(slot: PriceSlot, options: dict, kind: str = "spot") -> Decimal:
    """Apply explicit contract parameters; no implicit taxes or tariffs."""
    spot = slot.price / 1000
    if kind == "spot":
        return spot
    return spot * Decimal(str(options[f"{kind}_multiplier"])) + Decimal(
        str(options[f"{kind}_adder"])
    )


def average_price(slots: tuple[PriceSlot, ...], options: dict, kind: str = "spot") -> Decimal:
    """Duration-weighted average, including DST days."""
    seconds = sum((s.end - s.start).total_seconds() for s in slots)
    if not seconds:
        raise PriceError("Cannot average an empty schedule")
    return sum(
        (
            price_kwh(s, options, kind) * Decimal(str((s.end - s.start).total_seconds()))
            for s in slots
        ),
        Decimal(0),
    ) / Decimal(str(seconds))


def percentile(slots: tuple[PriceSlot, ...], slot: PriceSlot) -> float:
    """Percentage of intervals strictly cheaper; ties have equal rank."""
    if len(slots) <= 1:
        return 0.0
    return 100 * sum(s.price < slot.price for s in slots) / (len(slots) - 1)


def cheapest_window(
    slots: tuple[PriceSlot, ...],
    earliest: datetime,
    latest: datetime,
    minutes: int,
    options: dict,
    kind: str = "spot",
) -> Window | None:
    """Find the global cheapest contiguous complete window; earliest wins ties."""
    if earliest.tzinfo is None or latest.tzinfo is None:
        raise PriceError("Planning timestamps must include a timezone")
    if not 15 <= minutes <= 1440 or minutes % 15:
        raise PriceError("Duration must be 15–1440 minutes in steps of 15")
    earliest, latest = earliest.astimezone(UTC), latest.astimezone(UTC)
    count = minutes // 15
    candidates = tuple(s for s in slots if s.start >= earliest and s.end <= latest)
    best = None
    for i in range(len(candidates) - count + 1):
        window = candidates[i : i + count]
        if any(a.end != b.start for a, b in zip(window, window[1:], strict=False)):
            continue
        value = average_price(window, options, kind)
        if best is None or value < best.average:
            best = Window(window[0].start, window[-1].end, value)
    return best


def validate_options(options: dict) -> bool:
    """Reject nonfinite tariffs and invalid windows, including direct API input."""
    try:
        numeric = (
            "import_adder",
            "import_multiplier",
            "export_adder",
            "export_multiplier",
            "cheap_threshold",
            "cheap_percentile",
            "window_minutes",
        )
        if any(not math.isfinite(float(options[k])) for k in numeric):
            return False
        return (
            0 <= options["import_multiplier"] <= 100
            and 0 <= options["export_multiplier"] <= 100
            and 0 <= options["cheap_percentile"] <= 100
            and 15 <= options["window_minutes"] <= 1440
            and options["window_minutes"] % 15 == 0
        )
    except (KeyError, TypeError, ValueError):
        return False

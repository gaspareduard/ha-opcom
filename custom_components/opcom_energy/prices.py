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

from .const import INVOICE_COMPONENTS, MARKET_TZ, SLOT_LENGTH


class PriceError(ValueError):
    """The source did not provide a valid complete market day."""


class NotPublished(PriceError):
    """The source returned an empty, not-yet-published day."""


class TariffUnavailable(PriceError):
    """No configured tariff covers an interval."""


def invoice_tariff(effective_from: str, language: str = "en") -> dict:
    """Return independent editable starting values, with no private invoice data."""
    return {
        "effective_from": effective_from,
        "energy_multiplier": 1.0,
        "energy_adder": 0.0,
        "energy_vat": 21.0,
        "components": [
            {
                "name": ro if language == "ro" else en,
                "rate": rate,
                "vat": 21.0,
                "enabled": True,
                "vat_verified": en != "CfD contribution",
            }
            for en, ro, rate in INVOICE_COMPONENTS
        ],
    }


def yellowgrid_tariff(effective_from: str, language: str = "en") -> dict:
    """Editable public-offer model, with the chart-consistent Delgaz example."""
    version = invoice_tariff(effective_from, language)
    version.update(
        energy_model="yellowgrid",
        import_cap=0.55,
        final_import_cap=1.31,
        export_floor=0.5,
        commission=25.0,
    )
    # Public offer combines all distribution voltage levels into one charge.
    version["components"] = [c for i, c in enumerate(version["components"]) if i not in (2, 3, 4)]
    version["components"].insert(
        2,
        {
            "name": "Distribuție Delgaz (estimare grafic)"
            if language == "ro"
            else "Delgaz distribution (chart estimate)",
            "rate": 0.38791,
            "vat": 21.0,
            "enabled": True,
            "vat_verified": True,
        },
    )
    return version


def validate_tariffs(versions: list) -> None:
    """Validate durable user configuration before accepting it."""
    try:
        if not isinstance(versions, list) or len(versions) > 100:
            raise ValueError("Expected at most 100 tariff versions")
        dates = set()
        for version in versions:
            effective = date.fromisoformat(version["effective_from"])
            if version["effective_from"] != effective.isoformat():
                raise ValueError("Use an ISO calendar date YYYY-MM-DD")
            if effective in dates:
                raise ValueError("Tariff effective dates must be distinct")
            dates.add(effective)
            for key, low, high in (
                ("energy_multiplier", 0, 100),
                ("energy_adder", -10000, 10000),
                ("energy_vat", 0, 100),
            ):
                value = Decimal(str(version[key]))
                if not value.is_finite() or not low <= value <= high:
                    raise ValueError("Invalid base energy settings")
            model = version.get("energy_model", "linear")
            if model not in ("linear", "yellowgrid"):
                raise ValueError("Unknown energy model")
            if model == "yellowgrid":
                for key, high in (
                    ("import_cap", 10000),
                    ("export_floor", 10000),
                    ("commission", 100),
                ):
                    value = Decimal(str(version[key]))
                    if not value.is_finite() or not 0 <= value <= high:
                        raise ValueError("Invalid supplier cap, floor or commission")
            if "final_import_cap" in version:
                cap = Decimal(str(version["final_import_cap"]))
                if model != "yellowgrid" or not cap.is_finite() or not 0 <= cap <= 10000:
                    raise ValueError("Invalid final import cap")
            components = version["components"]
            if not isinstance(components, list) or len(components) > 50:
                raise ValueError("Expected at most 50 components")
            names = set()
            for component in components:
                name = component["name"]
                if (
                    not isinstance(name, str)
                    or not name.strip()
                    or len(name) > 80
                    or name.strip().casefold() in names
                ):
                    raise ValueError("Component names must be distinct and nonempty")
                names.add(name.strip().casefold())
                for key, low, high in (("rate", -10000, 10000), ("vat", 0, 100)):
                    value = Decimal(str(component[key]))
                    if not value.is_finite() or not low <= value <= high:
                        raise ValueError("Invalid component rate or VAT")
                if not isinstance(component["enabled"], bool) or not isinstance(
                    component["vat_verified"], bool
                ):
                    raise ValueError("Invalid component flags")
    except (KeyError, TypeError, ValueError, InvalidOperation) as err:
        raise PriceError(f"Invalid tariff configuration: {err}") from err


@dataclass(frozen=True, slots=True)
class ImportBreakdown:
    """One interval's decimal values and explanatory component details."""

    base_energy: Decimal
    charges: Decimal
    vat: Decimal
    total: Decimal
    attributes: dict


def import_breakdown(slot: PriceSlot, options: dict, tz: ZoneInfo) -> ImportBreakdown:
    """Select at interval start in the HA timezone, with no backward fallback."""
    version = tariff_version(slot, options, tz)
    spot = price_kwh(slot, options)
    if version.get("energy_model") == "yellowgrid":
        cap = Decimal(str(version["import_cap"]))
        commission = Decimal(str(version["commission"])) / 100
        spot = min(cap, spot + (cap - spot) * commission)
    base = spot * Decimal(str(version["energy_multiplier"])) + Decimal(str(version["energy_adder"]))
    base_vat = base * Decimal(str(version["energy_vat"])) / 100
    charges = Decimal(0)
    vat = base_vat
    details = []
    for component in version["components"]:
        if not component["enabled"]:
            continue
        rate = Decimal(str(component["rate"]))
        tax = rate * Decimal(str(component["vat"])) / 100
        charges += rate
        vat += tax
        details.append({**component, "vat_amount": float(tax)})
    uncapped_total = base + charges + vat
    total = uncapped_total
    if version.get("energy_model") == "yellowgrid" and "final_import_cap" in version:
        total = min(total, Decimal(str(version["final_import_cap"])))
    return ImportBreakdown(
        base,
        charges,
        vat,
        total,
        {
            "pricing_mode": "components",
            "tariff_effective_from": version["effective_from"],
            "base_energy": float(base),
            "additional_charges": float(charges),
            "vat_amount": float(vat),
            "estimated_total": float(total),
            "uncapped_total": float(uncapped_total),
            "cap_adjustment": float(total - uncapped_total),
            "energy_model": version.get("energy_model", "linear"),
            **{
                k: version[k]
                for k in ("import_cap", "final_import_cap", "commission")
                if k in version
            },
            "energy_multiplier": version["energy_multiplier"],
            "energy_adder": version["energy_adder"],
            "energy_vat_percent": version["energy_vat"],
            "energy_vat_amount": float(base_vat),
            "components": details,
            "unverified_vat_components": [c["name"] for c in details if not c["vat_verified"]],
        },
    )


def tariff_version(slot: PriceSlot, options: dict, tz: ZoneInfo) -> dict:
    """Find the effective version at the interval's local start."""
    local_day = slot.start.astimezone(tz).date()
    version = max(
        (
            v
            for v in options.get("tariff_versions", [])
            if date.fromisoformat(v["effective_from"]) <= local_day
        ),
        key=lambda v: v["effective_from"],
        default=None,
    )
    if version is None:
        raise TariffUnavailable("No tariff version covers this interval")
    return version


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


def price_kwh(
    slot: PriceSlot, options: dict, kind: str = "spot", tz: ZoneInfo | None = None
) -> Decimal:
    """Apply explicit contract parameters; no implicit taxes or tariffs."""
    spot = slot.price / 1000
    if kind == "spot":
        return spot
    if kind == "import" and options.get("pricing_mode", "simple") == "components":
        if tz is None:
            raise PriceError("Component pricing requires the HA timezone")
        return import_breakdown(slot, options, tz).total
    if (
        kind == "export"
        and options.get("pricing_mode", "simple") == "components"
        and any(v.get("energy_model") == "yellowgrid" for v in options.get("tariff_versions", []))
    ):
        if tz is None:
            raise PriceError("Supplier pricing requires the HA timezone")
        version = tariff_version(slot, options, tz)
        if version.get("energy_model") == "yellowgrid":
            floor = Decimal(str(version["export_floor"]))
            retained = 1 - Decimal(str(version["commission"])) / 100
            return max(floor, floor + (spot - floor) * retained)
    return spot * Decimal(str(options[f"{kind}_multiplier"])) + Decimal(
        str(options[f"{kind}_adder"])
    )


def average_price(
    slots: tuple[PriceSlot, ...], options: dict, kind: str = "spot", tz: ZoneInfo | None = None
) -> Decimal:
    """Duration-weighted average, including DST days."""
    seconds = sum((s.end - s.start).total_seconds() for s in slots)
    if not seconds:
        raise PriceError("Cannot average an empty schedule")
    return sum(
        (
            price_kwh(s, options, kind, tz) * Decimal(str((s.end - s.start).total_seconds()))
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
    tz: ZoneInfo | None = None,
) -> Window | None:
    """Find the global cheapest contiguous complete window; earliest wins ties."""
    if earliest.tzinfo is None or latest.tzinfo is None:
        raise PriceError("Planning timestamps must include a timezone")
    if not 15 <= minutes <= 1440 or minutes % 15:
        raise PriceError("Duration must be 15–1440 minutes in steps of 15")
    earliest, latest = earliest.astimezone(UTC), latest.astimezone(UTC)
    count = minutes // 15
    # Resolve each tariff once. Overlapping long windows must not recalculate
    # every component for every interval on Home Assistant's event loop.
    candidates = []
    weighted_totals = [Decimal(0)]
    durations = [Decimal(0)]
    for slot in slots:
        if slot.start < earliest or slot.end > latest:
            continue
        try:
            value = price_kwh(slot, options, kind, tz)
        except TariffUnavailable:
            continue
        seconds = Decimal(str((slot.end - slot.start).total_seconds()))
        candidates.append(slot)
        weighted_totals.append(weighted_totals[-1] + value * seconds)
        durations.append(durations[-1] + seconds)
    best = None
    for i in range(len(candidates) - count + 1):
        window = candidates[i : i + count]
        if any(a.end != b.start for a, b in zip(window, window[1:], strict=False)):
            continue
        end = i + count
        value = (weighted_totals[end] - weighted_totals[i]) / (durations[end] - durations[i])
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

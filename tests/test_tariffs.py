"""Invoice arithmetic and effective dates, with independent expected values."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.opcom_energy.const import DEFAULT_OPTIONS
from custom_components.opcom_energy.prices import (
    PriceError,
    PriceSlot,
    TariffUnavailable,
    cheapest_window,
    import_breakdown,
    invoice_tariff,
    price_kwh,
    validate_tariffs,
)

RO = ZoneInfo("Europe/Bucharest")


def slot(at="2026-10-20T12:00:00+00:00", price="498.8"):
    start = datetime.fromisoformat(at)
    return PriceSlot(start, start + timedelta(minutes=15), Decimal(price))


def options(*versions):
    return DEFAULT_OPTIONS | {"pricing_mode": "components", "tariff_versions": list(versions)}


def test_invoice_arithmetic_and_independent_preset():
    version = invoice_tariff("2026-09-01")
    validate_tariffs([version])
    result = import_breakdown(slot(), options(version), RO)
    assert result.base_energy == Decimal("0.4988")
    assert result.charges == Decimal("0.4648832")
    assert result.vat == Decimal("0.202373472")
    assert result.total == Decimal("1.166056672")
    assert result.attributes["unverified_vat_components"] == ["CfD contribution"]
    version["components"][0]["rate"] = 999
    assert invoice_tariff("2026-09-01")["components"][0]["rate"] == 0.03645


def test_editable_vat_enabled_credits_and_negative_spot():
    version = invoice_tariff("2026-09-01")
    version.update(energy_multiplier=2, energy_adder=0.3, energy_vat=10)
    version["components"] = [
        {"name": "Taxed", "rate": 0.1, "vat": 20, "enabled": True, "vat_verified": True},
        {"name": "Untaxed", "rate": 0.2, "vat": 0, "enabled": True, "vat_verified": True},
        {"name": "Credit", "rate": -0.05, "vat": 0, "enabled": True, "vat_verified": True},
        {"name": "Disabled", "rate": 100, "vat": 100, "enabled": False, "vat_verified": False},
    ]
    result = import_breakdown(slot(price="-100"), options(version), RO)
    assert result.base_energy == Decimal(".1")
    assert result.charges == Decimal(".25")
    assert result.vat == Decimal(".03")
    assert result.total == Decimal(".38")
    assert len(result.attributes["components"]) == 3


@pytest.mark.parametrize(
    ("boundary", "effective"),
    [
        ("2026-10-20T21:00:00+00:00", "2026-10-21"),
        ("2026-03-28T22:00:00+00:00", "2026-03-29"),
        ("2026-10-24T21:00:00+00:00", "2026-10-25"),
    ],
)
def test_ha_local_midnight_including_dst_days(boundary, effective):
    earlier = invoice_tariff("2026-01-01")
    earlier.update(energy_vat=0, components=[])
    later = invoice_tariff(effective)
    later.update(energy_vat=0, components=[], energy_adder=1)
    config = options(later, earlier)  # Selection must not depend on input order.
    at = datetime.fromisoformat(boundary)
    before = PriceSlot(at - timedelta(minutes=15), at, Decimal(500))
    after = PriceSlot(at, at + timedelta(minutes=15), Decimal(500))
    assert price_kwh(before, config, "import", RO) == Decimal(".5")
    assert price_kwh(after, config, "import", RO) == Decimal("1.5")
    assert import_breakdown(after, config, RO).attributes["tariff_effective_from"] == effective


def test_missing_coverage_does_not_affect_raw_export_or_simple():
    config = options(invoice_tariff("2026-11-01"))
    config.update(
        import_multiplier=1.21, import_adder=0.56, export_multiplier=0.8, export_adder=-0.01
    )
    with pytest.raises(TariffUnavailable):
        price_kwh(slot(), config, "import", RO)
    with pytest.raises(PriceError):
        price_kwh(slot(), config, "import")
    assert price_kwh(slot(), config) == Decimal(".4988")
    assert price_kwh(slot(), config, "export", RO) == Decimal(".38904")
    config["pricing_mode"] = "simple"
    assert price_kwh(slot(), config, "import", RO) == Decimal("1.163548")


def test_planning_crosses_rate_change_using_each_intervals_version():
    first = invoice_tariff("2026-01-01")
    first.update(energy_vat=0, components=[])
    second = invoice_tariff("2026-10-21")
    second.update(energy_vat=0, components=[], energy_adder=1)
    at = datetime(2026, 10, 20, 20, 30, tzinfo=UTC)
    rows = tuple(
        PriceSlot(at + i * timedelta(minutes=15), at + (i + 1) * timedelta(minutes=15), Decimal(p))
        for i, p in enumerate([1000, 1000, 0, 0])
    )
    result = cheapest_window(rows, at, rows[-1].end, 30, options(first, second), "import", RO)
    # Actual total prices are all 1, so earliest wins; raw spot would choose midnight.
    assert result.start == at
    assert result.average == 1
    crossing = cheapest_window(
        rows[1:3], rows[1].start, rows[2].end, 30, options(first, second), "import", RO
    )
    assert crossing.average == 1
    no_cover = options(invoice_tariff("2026-10-22"))
    assert cheapest_window(rows, at, rows[-1].end, 30, no_cover, "import", RO) is None
    # An uncovered prefix cannot be silently charged as zero in a longer window.
    assert cheapest_window(rows, at, rows[-1].end, 45, options(second), "import", RO) is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(effective_from="not-a-date"),
        lambda v: v.update(energy_vat=101),
        lambda v: v.update(energy_multiplier=-1),
        lambda v: v.update(energy_adder=float("nan")),
        lambda v: v["components"][0].update(rate=float("inf")),
        lambda v: v["components"][0].update(vat=-1),
        lambda v: v["components"][0].update(name=" "),
        lambda v: v["components"][0].update(enabled="true"),
        lambda v: v["components"].append(deepcopy(v["components"][0])),
    ],
)
def test_invalid_configurations_rejected(mutation):
    version = invoice_tariff("2026-09-01")
    mutation(version)
    with pytest.raises(PriceError):
        validate_tariffs([version])


def test_duplicate_effective_dates_rejected():
    with pytest.raises(PriceError):
        validate_tariffs([invoice_tariff("2026-09-01"), invoice_tariff("2026-09-01")])


def test_noncanonical_effective_date_rejected():
    version = invoice_tariff("20260901")
    with pytest.raises(PriceError):
        validate_tariffs([version])


def test_romanian_invoice_component_names_and_tax_warning():
    version = invoice_tariff("2026-09-01", "ro")
    result = import_breakdown(slot(), options(version), RO)
    assert result.attributes["unverified_vat_components"] == ["Contribuție CfD"]
    assert version["components"][0]["name"] == "Extragere din rețea"

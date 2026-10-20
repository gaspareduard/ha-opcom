# OPCOM Energy

Romanian day-ahead electricity prices and estimates of household import costs and export compensation.

## Language

**Spot price**:
The wholesale OPCOM day-ahead price for a delivery interval, before the household's contract adjustments, network charges and taxes.
_Avoid_: Final price, billed price

**Base energy price**:
The contractual price of active electricity before additional network charges and levies. It may differ from the spot price through a supplier margin, commission, floor or cap.
_Avoid_: Spot price, total import price

**Tariff component**:
A separately identified charge or credit per unit of imported or exported electricity, with its applicable tax treatment and validity period.
_Avoid_: Subscription, monthly fee

**Estimated import price**:
The estimated cost per kWh taken from the grid, including the base energy price, applicable tariff components and VAT.
_Avoid_: Exact invoice price, spot price

**Estimated export price**:
The estimated compensation per kWh supplied to the grid under the export contract's own pricing and tax rules.
_Avoid_: Import price, invoice balance

**Fixed charge**:
A charge per billing period that does not vary directly with the electricity imported or exported.
_Avoid_: Tariff component, per-kWh adder

**Tariff version**:
A set of tariff-component rates and VAT rules applying from an effective date until the next tariff version takes effect.
_Avoid_: Invoice, billing period

**Consumption-weighted energy price**:
The average base energy price weighted by the electricity imported in each delivery interval.
_Avoid_: Arithmetic daily spot average

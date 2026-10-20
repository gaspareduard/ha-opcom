# Configure optional tariff components

Version 1.1 adds an opt-in **Components** import-pricing mode. Existing installations stay in **Simple** mode. All configuration lives in HA config-entry options and survives restarts; no supplier login or invoice upload is required.

## Configure a version

Open the integration's **Configure → Tariff versions and components → Add tariff version**. Choose an effective date. The **Empty** starting configuration contains no additional charges. The **September 2026 invoice (editable)** configuration contains the documented example network charges and levies; choosing it is explicit and never changes other users' settings automatically.

Set the base energy before VAT as `spot × multiplier + adder`. The new fields are independent of the original import multiplier/adder, which may already contain VAT and network fees. Defaults are multiplier 1, adder 0 and energy VAT 21%. VAT fields are percentages: enter 21, not 1.21.

The next menu supports adding a component, editing one by name, removing a component and saving the version. Components have a name, before-VAT RON/kWh rate, VAT percentage, enabled flag and a VAT-treatment verification flag. Disabled components contribute neither their rate nor VAT. Zero VAT and negative rates (credits) are supported when appropriate to the configured contract. All numbers must be finite; VAT and energy multipliers are 0–100, rates/adders are -10000–10000. Dates and component names must be unique within their respective scopes.

Component edits remain in the flow until **Save tariff**. After saving, reopen Configure and select **Import pricing mode → Components**. Switching back to Simple restores its saved formula without deleting tariff versions.

## Dates and changes

Each version applies from its effective date at HA-local midnight until the next version. The interval's start chooses the version, not the current wall clock or OPCOM's market-day date. Future schedules therefore use scheduled future rates. No version applies backward before its date.

Use **Edit tariff version** to change a version, including its date. To introduce a new rate period while preserving earlier rates, add a new version instead of editing the earlier one. **Delete tariff version** saves the deletion immediately after selecting its date; the previous version, if any, then continues until the next one. Deleting the earliest version removes earlier coverage. Stored HA history is not rewritten, and this integration does not provide a historical billing ledger.

No covering tariff means an unavailable import total, unavailable import threshold and unavailable component breakdown. Wholesale data and export prices remain usable. Import planning excludes windows with missing coverage; it never fills such intervals with zero or raw spot.

## Example calculation

With spot/base energy 0.5 RON/kWh, a single charge of 0.1 RON/kWh, and 21% VAT on both:

```text
base energy before VAT = 0.5
additional charges before VAT = 0.1
VAT = 0.105 + 0.021 = 0.126
estimated total = 0.726 RON/kWh
```

If the component is non-taxable, set its VAT to 0: VAT becomes 0.105 and the total becomes 0.705. If the component is disabled, the total becomes 0.605. Decimal precision is retained internally; display and invoice line-item rounding may differ.

The September invoice example adds nine components totalling 0.4648832 RON/kWh before VAT. Its VAT starting assumption is 21%; CfD is explicitly marked unverified. Keep or change this only according to the applicable contract/tax treatment. The invoice's monthly average energy rate is not a fixed replacement for interval spot prices. Exact supplier caps, floors and commission rules are outside this release.

## Read the breakdown

The existing **Estimated import price** remains the total-price entity. The additional sensors are **Import base energy before VAT**, **Import additional charges before VAT** and **Import VAT amount**. They are unavailable in Simple mode because its arbitrary multiplier/adder does not identify a tax breakdown.

Attributes include `tariff_effective_from`, `base_energy`, `additional_charges`, `vat_amount`, `estimated_total`, the energy settings, named enabled components and `unverified_vat_components`. Values are RON/kWh except VAT percentages and the energy multiplier.

`opcom_energy.get_prices` with `price_type: import` returns the same total and `breakdown` per covered interval. An interval without coverage returns `price: null` and `unavailable_reason: no_tariff`, and the overall `complete` flag is false. Consumers must check both completeness and null prices. Simple-mode, spot and export response shapes are preserved.

Raw daily average/min/max and percentile sensors retain their wholesale meaning. Import thresholds and import-price window planning use the selected import-pricing mode. Export pricing never inherits import network charges.

These are marginal price estimates. Fixed subscriptions, meter-energy accounting, monthly invoice totals, supplier-rate discovery and automatic equipment control are outside v1.1. No private invoice PDF, meter identifiers or account details are included in the integration.

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

The September invoice example adds nine components totalling 0.4648832 RON/kWh before VAT. Its VAT starting assumption is 21%; CfD is explicitly marked unverified. Keep or change this only according to the applicable contract/tax treatment. The invoice's monthly average energy rate is not a fixed replacement for interval spot prices. The separate YellowGrid preset below adds supplier caps, floors and commission rules.

## Read the breakdown

The existing **Estimated import price** remains the total-price entity. The additional sensors are **Import base energy before VAT**, **Import additional charges before VAT** and **Import VAT amount**. They are unavailable in Simple mode because its arbitrary multiplier/adder does not identify a tax breakdown.

Attributes include `tariff_effective_from`, `base_energy`, `additional_charges`, `vat_amount`, `estimated_total`, the energy settings, named enabled components and `unverified_vat_components`. Values are RON/kWh except VAT percentages and the energy multiplier.

`opcom_energy.get_prices` with `price_type: import` returns the same total and `breakdown` per covered interval. An interval without coverage returns `price: null` and `unavailable_reason: no_tariff`, and the overall `complete` flag is false. Consumers must check both completeness and null prices. Simple-mode, spot and export response shapes are preserved.

Raw daily average/min/max and percentile sensors retain their wholesale meaning. Import thresholds and import-price window planning use the selected import-pricing mode. Export pricing never inherits import network charges.

These are marginal price estimates. Fixed subscriptions, meter-energy accounting, monthly invoice totals, supplier-rate discovery and automatic equipment control are outside v1.1. No private invoice PDF, meter identifiers or account details are included in the integration.

## YellowGrid chart estimate (v1.2)

Adding a version now offers **YellowGrid — 20 October chart estimate (editable)** as the default starting choice. It still requires saving a dated version and explicitly enabling Components mode. Existing saved versions and Simple mode are unchanged. The invoice-only and empty presets remain available.

The [supplier’s published offer](https://www.yellowgrid.ro/legislatie-si-contracte), “Ofertă de Agregare și Furnizare Preț Dinamic”, valid 1 September–30 November 2026, supplies these editable starting parameters: import active-energy cap **0.55 RON/kWh**, export floor **0.50 RON/kWh**, commission **25%**. With `s = raw OPCOM RON/kWh` and `c = commission / 100`:

```text
import energy = min(cap, s + (cap - s) * c)
base before VAT = import energy * energy_multiplier + energy_adder
import total = base + enabled charges + their configured VAT
export estimate = max(floor, floor + (s - floor) * (1 - c))
```

Export has no import VAT or network fees. The same dated version selects the import cap, export floor, commission and charges at HA-local midnight. In Components mode, once any YellowGrid version is configured, export also requires a covering version; a covered linear version uses the saved simple export formula. Simple mode always uses its original saved import/export formulas. This models marginal displayed prices, not a settlement or benefits ledger.

For the 20 October 2026 chart, all 96 quarter-hours (00:00–23:45 Europe/Bucharest, assembled from the 19 and 20 October OPCOM market-day CSVs) closely follow `0.75*s + 0.125` for export. For example, at 09:00 OPCOM is 2.5 and export is 2.0 RON/kWh. The export root-mean-square discrepancy against chart pixels was approximately 0.004 RON/kWh (maximum 0.009). Raster readings have several thousandths of a RON/kWh uncertainty; exact tooltip values were not available. This supports the export rule but does not test its floor on that high-price day.

Import appears flat around **1.31 RON/kWh**. The invoice charges total **0.4648832** before VAT; using the public 0.55 energy cap and 21% VAT gives **1.228008672**, which does **not** match that chart. The public offer’s Delgaz distribution rate **0.38791**, replacing the invoice’s combined IT/MT/JT **0.31739**, gives charges **0.5354032** and total **1.313337872**. All comparable OPCOM intervals exceed the cap, explaining the flat import bars.

Accordingly, the chart preset uses one explicitly named **Delgaz distribution (chart estimate)** component, instead of inventing a split across voltage levels. Other charges and VAT start from the invoice example. The supplier’s illustrative table independently gives the same Delgaz total. This is evidence for a chart match, **not confirmation that Delgaz is your contracted operator**: your invoice supports a different distribution rate. Check your account’s selected tariff/region or contract before treating the chart preset as a billing estimate. To use your invoice distribution instead, choose the invoice preset, or replace this distribution component with your applicable rates. Every parameter remains editable; CfD VAT stays marked unverified.

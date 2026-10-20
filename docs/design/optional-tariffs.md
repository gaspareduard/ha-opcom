# Optional tariff components for the next release

Status: accepted by the user for v1.1 implementation.

## Confirmed user requirement

The next release should optionally account for additional per-kWh charges so that estimated import prices can more closely resemble a supplier's final price. The specific motivating supplier is YellowGrid. Wholesale OPCOM prices must remain available separately.

The user explicitly confirmed inclusion in v1.1, using their invoice as the starting point, with editable charges and VAT and separately visible raw OPCOM prices.

The user subsequently confirmed:

- v1.1 focuses on editable invoice-based tariffs and the price breakdown.
- The existing energy multiplier/adder formula remains the basis for this release; new supplier commission/cap rules are deferred.
- Tariff and VAT changes have effective dates.
- Dashboard and persistent device plans are deferred to later releases.
- Existing simple mode remains unchanged, including its saved settings and results.
- Component mode uses separate, explicitly before-VAT base-energy multiplier/adder settings so legacy settings cannot cause double taxation.
- A tariff version takes effect at HA-local midnight; each delivery interval uses the version active at the interval's start.
- Without a tariff version covering an interval, the estimated total is unavailable while raw OPCOM prices remain available.

## Confirmed starting charges

The following per-kWh amounts were read from the supplied September 2026 invoice. They are starting values for an optional editable configuration, not a universal YellowGrid tariff or a promise that the rates remain current.

| Component | RON/kWh before VAT |
| --- | ---: |
| Network extraction | 0.03645 |
| System service | 0.0147 |
| Distribution IT | 0.02383 |
| Distribution MT | 0.06836 |
| Distribution JT | 0.2252 |
| Green certificates | 0.0740192 |
| Cogeneration | 0.0145 |
| Excise | 0.00768 |
| CfD contribution | 0.000144 |
| Total additional charges | 0.4648832 |

The invoice states a headline VAT rate of 21%. VAT settings must remain editable; CfD's displayed zero VAT does not resolve its tax treatment. The invoice's monthly average energy price must not be substituted for the changing interval energy price.

## Evidence and boundaries

A privately supplied September 2026 invoice identifies network extraction, system service, distribution at IT/MT/JT, green certificates, cogeneration, excise and a CfD contribution as per-kWh items. No fixed subscription charge was identified on the reviewed invoice. Its base energy line is a monthly average, not evidence that the contractual interval price equals unadjusted OPCOM.

The invoice itself, its images, identifiers, consumption, export amounts and account information are not included in this repository. A displayed zero VAT amount on a very small line does not establish tax exemption because invoice amounts are rounded.

YellowGrid's public dynamic offer also describes a variable supply component and an energy-price cap. Its currently advertised terms do not establish the terms of an individual existing contract. Source: [YellowGrid contractual documents](https://www.yellowgrid.ro/legislatie-si-contracte), dynamic aggregation and supply offer, active-energy formula on page 7.

## Agreed behavior

- Keep the existing simple multiplier/adder mode for compatibility.
- Offer the confirmed optional component-based mode with named per-kWh charges, editable VAT and effective dates.
- Expose the estimated total together with the base energy price, component subtotal and VAT breakdown.
- Apply the selected import pricing method consistently to the current price, price schedules and import-price planning.
- Treat import and export pricing separately. Import network charges must not automatically be subtracted from export compensation.
- Keep fixed charges separate from marginal per-kWh prices used for planning.
- Use editable local settings; an invoice-derived configuration must not become a universal provider tariff or imply automatic updates.
- Defer new contract-specific commissions, floors and caps. Do not label a simple spot-plus-charges estimate as an exact provider price.

## Calculation order

For a delivery interval with spot price S in RON/kWh and an applicable tariff version:

1. Base energy before VAT is S times the component-mode energy multiplier plus the component-mode energy adder.
2. Additional charges before VAT are the sum of the enabled per-kWh components.
3. VAT is calculated separately on base energy and each component using their configured VAT percentages.
4. Estimated total import price is base energy plus additional charges plus VAT.

The proposed initial base-energy multiplier is 1 and adder is 0. The invoice-derived VAT starting value is 21%, editable for base energy and each component; the UI must identify CfD tax treatment as unverified rather than infer an exemption from a rounded zero. The user confirmed these starting values and authorized implementation.

Calculations retain decimal precision. Display rounding is distinct from invoice line-item rounding; the result is a marginal per-kWh estimate, not a full billing reconciliation.

## Effective dates and availability

Each tariff version contains its effective date, base-energy settings, charges and VAT rules. Versions are ordered by distinct effective dates, remain saved across restarts, and apply until superseded by the next version. A future-dated version changes the applicable future price intervals without replacing earlier versions.

Dates use the HA-configured local calendar rather than the OPCOM market-day boundary. No tariff is implicitly extended backward before the earliest version. Current import price, price breakdown, import schedules, threshold signals and import-price planning must use the same applicable version for each interval. Missing tariff coverage must not become a zero charge or an unadjusted spot-price fallback.

The proposed editing surface is the integration's HA configuration UI, with an explicit opt-in invoice-derived starting configuration. Its start date is chosen by the user. Existing simple-mode configurations stay in simple mode unless explicitly changed.

## Release boundaries

- Included: optional component mode, editable invoice-derived charges and VAT, tariff versions with effective dates, consistent price breakdown and import calculations, persistent configuration, English/Romanian labels, migration/regression coverage and documentation.
- Deferred: dashboards, persistent device plans, new supplier caps/floors/commission models, automatic provider-rate updates and equipment control.
- Unchanged: raw OPCOM data and prices, the original simple mode, export-price formula and public HACS installation.
- No private invoice PDF, account identifiers, consumption or export amounts will be published.

## Remaining supplier-specific verification

- Verify the user's applicable supplier formulas and tax treatment, including CfD, before describing any personal configuration as an exact supplier-price match. This does not block a clearly labelled editable estimate.

## Proposed acceptance examples

- With optional components disabled, existing simple-mode prices remain identical.
- With components enabled, the total reconciles with a synthetic line-item example within the documented rounding tolerance.
- Taxable and non-taxable components remain distinguishable, and a rounded zero VAT amount is never used to infer a tax rule.
- Changes in effective dates, negative spot prices and unchanged legacy/export formulas have explicit tests. Supplier-cap behavior is outside v1.1.
- Local midnight is tested independently of the OPCOM market-day boundary, including spring/autumn clock changes and future schedules crossing a rate-change date.
- Uncovered intervals make component-mode totals and dependent threshold signals unavailable and are excluded from valid import planning windows without bridging gaps.
- Existing simple-mode settings are never copied into the before-VAT base-energy settings automatically. Switching modes does not destroy the saved simple-mode configuration.
- Whole-period invoice comparisons use consumption-weighted interval prices and account for line-level rounding; arithmetic daily price averages are not presented as invoice reconciliation.

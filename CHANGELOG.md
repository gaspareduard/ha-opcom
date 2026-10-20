# Changelog

## 1.2.3

- Publish the Romanian README in the release used by HACS, with absolute documentation and image links that also work in the HACS detail view.

- Make Romanian the primary README and tariff-guide language; preserve English documentation and the existing Romanian README URL.
- Document the complete YellowGrid setup, effective dates, final import cap, export floor, editable rates/VAT and unconfirmed distribution assumptions.
- Add a reusable Romanian dashboard example with import/export bars and raw OPCOM as a line, using authoritative backend schedules for today and tomorrow.

## 1.2.2

- Fix HTTP 403 failures after the first public OPCOM CSV download: use a cookie-free HA-managed session with shared connectors, rather than replaying cookies set by the export endpoint. Preserve TLS verification, validation and retry behavior.
- Release temporary config-flow sessions immediately; HA cleans up coordinator sessions on entry unload and shutdown.
- Add a local HTTP regression replay that sets cookies and rejects their reuse, reproducing the multi-download failure before the fix.

## 1.2.1

- Add an editable final import ceiling of 1.31 RON/kWh to newly created YellowGrid presets, following user confirmation that this cap includes charges and VAT. Keep the export floor at 0.50 RON/kWh.
- Expose the uncapped total and explicit cap adjustment without changing the configured charge or VAT breakdown. Existing saved tariffs retain their behavior until edited and saved with a final cap.
- Clarify that a capped chart cannot confirm the distribution operator.

## 1.2.0

- Add an optional editable YellowGrid pricing model: capped import active energy, export floor and supplier commission, all effective-dated in HA local time.
- Default new tariff creation to a clearly labelled YellowGrid chart-estimate preset using public offer parameters and the Delgaz distribution example; retain invoice-only and empty presets and all existing saved settings.
- Explain the 20 October comparison: export closely matches OPCOM after commission; chart import matches 1.31334 RON/kWh with Delgaz distribution, while invoice distribution gives 1.22801. Operator selection remains unconfirmed and editable.
- Apply the shared model to sensors, schedules, thresholds and window planning, with supplier parameters exposed in entity attributes and import breakdowns.
- Preserve raw OPCOM prices, legacy Simple mode and linear tariff versions; add regression coverage for negative prices, caps, floors, commission extremes, effective dates, UI and action responses.

## 1.1.0

- Add an optional component-based import tariff mode, with separate before-VAT energy settings and editable per-component charges and VAT. Existing simple-mode and export formulas remain unchanged.
- Add effective-dated tariff versions, selected at each interval's start using Home Assistant local midnight; versions and configuration persist across restarts.
- Add explicit opt-in September 2026 invoice starting values, with CfD VAT marked unverified. No private invoice or account data is included.
- Add current base-energy, additional-charge and VAT sensors; expose full breakdowns on estimated import prices and import schedule action responses.
- Apply the selected version consistently to import prices, thresholds and cheapest-window planning. Missing tariff coverage is unavailable, never silently zero or raw spot.
- Add English/Romanian UI flows for pricing mode, version management and component add/edit/remove; retain saved simple-mode settings when switching modes.
- Add 30 regression tests for invoice arithmetic, tax edits, local midnight/DST, future changes, missing coverage, configuration flows and offline restart.
- Resolve interval tariffs once when searching overlapping planning windows to reduce work on the HA event loop.

## 1.0.1

- Use the shared price conversion helper for every published daily schedule.
- Resolve each sensor value and its interval metadata together once per coordinator or quarter-hour update.
- Add regression coverage for negative schedule prices, tariff independence, min/max metadata, next-day rollover and consistent property reads.

## 1.0.0

- Direct asynchronous OPCOM PT15M retrieval, with strict complete-day validation.
- UTC interval model with tested 92/96/100-slot market days and HA-local daily summaries.
- Current/next spot prices, configurable import/export estimates, daily statistics and percentile signals.
- Global cheapest contiguous future-window planning, with timestamped structured response actions.
- Persistent validated cache, independent quarter-hour entity updates, per-day retries and source diagnostics.
- UI configuration and options, English/Romanian translations, original brand assets and MIT license.
- Home Assistant test harness, offline real-data regression fixtures, Ruff, Hassfest and HACS validation.

# Changelog

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

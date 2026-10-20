# Changelog

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

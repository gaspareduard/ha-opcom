# Public factual OPCOM CSV fixtures

Fetched directly from OPCOM's public export on 2026-10-20. Files contain wholesale market prices and volumes, not account information. They are test data, not forecasts or sample retail tariffs.

- `2026-10-20.csv`: regular day, 96 PT15M intervals.
- `2026-10-21.csv`: published next market day, 96 intervals.
- `2026-03-29.csv`: spring clock change, 92 intervals.
- `2025-10-26.csv`: autumn clock change, 100 intervals.
- `2026-10-22.csv`: empty response for an unpublished day at collection time.

Source pattern: `https://www.opcom.ro/rapoarte-pzu-raportPIP-export-csv/{day}/{month}/{year}/ro?resolution=PT15M`.

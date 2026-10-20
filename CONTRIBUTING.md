# Contributing

Use Python 3.14.2+ and `uv sync --frozen`. Run Ruff and pytest as described in the README. All integration files must remain inside `custom_components/opcom_energy` so HACS can install them without repository-root dependencies.

Keep unit conversion, timestamps and tariff arithmetic in `prices.py`; keep HTTP in `api.py`. Use Home Assistant's shared session, config-entry APIs and managed storage. Never block the event loop, disable TLS verification, add activation checks or send telemetry.

New source formats need sanitized public fixtures. Test normal days, both DST transitions, missing/duplicate intervals, negative values and failed downloads. Tests must not access OPCOM or a live HA installation. Source smoke checks are separate opt-in commands.

Report issues with HA and integration versions, timezone and diagnostics. Never include HA tokens, supplier credentials or private configuration backups. New device-control features require explicit scope, separate configuration and tests; the pricing integration currently only provides advisory data.

Release procedure: update the version in `manifest.json`, `const.py`, `pyproject.toml` and the changelog; refresh `uv.lock`; pass all CI checks, then publish a GitHub release against that validated commit. Submit HACS default-directory changes only after the public repository validators pass and a full release exists.

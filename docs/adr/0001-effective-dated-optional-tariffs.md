# Keep simple pricing and component-based tariffs as separate modes

Existing multiplier/adder settings may already contain VAT and network charges, so v1.1 adds optional component-based pricing with separate before-VAT energy settings instead of reinterpreting legacy values. Tariff versions take effect at HA-local midnight and are selected at each interval's start; intervals before the earliest version have no estimated total, avoiding both double taxation and silently applying later rates to earlier periods. Raw OPCOM prices remain independent of tariff configuration.


## Extension: YellowGrid model, 20 October 2026

The user subsequently requested defaults matching the YellowGrid chart. v1.2 adds an opt-in supplier model within dated versions. It caps import active energy before VAT and floors export after commission, using the shared resolver for sensors, schedules, thresholds and planning. Existing versions default to linear. Provider parameters are editable and effective-dated. A separate chart-estimate preset uses the published Delgaz distribution example; this is explicitly an inference, while the invoice preset retains its original distribution rates. No invoice/account image is published. This supersedes the earlier deferral of supplier cap/floor support for this authorized scope.

# Keep simple pricing and component-based tariffs as separate modes

Existing multiplier/adder settings may already contain VAT and network charges, so v1.1 adds optional component-based pricing with separate before-VAT energy settings instead of reinterpreting legacy values. Tariff versions take effect at HA-local midnight and are selected at each interval's start; intervals before the earliest version have no estimated total, avoiding both double taxation and silently applying later rates to earlier periods. Raw OPCOM prices remain independent of tariff configuration.

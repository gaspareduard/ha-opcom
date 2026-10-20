"""Constants for OPCOM Energy."""

from datetime import timedelta
from zoneinfo import ZoneInfo

DOMAIN = "opcom_energy"
NAME = "OPCOM Energy"
VERSION = "1.2.1"
MARKET_TZ = ZoneInfo("Europe/Berlin")
SLOT_LENGTH = timedelta(minutes=15)
SOURCE_URL = "https://www.opcom.ro"
CSV_URL = SOURCE_URL + "/rapoarte-pzu-raportPIP-export-csv/{day}/{month}/{year}/ro?resolution=PT15M"
DEFAULT_OPTIONS = {
    "import_adder": 0.0,
    "import_multiplier": 1.0,
    "export_adder": 0.0,
    "export_multiplier": 1.0,
    "cheap_threshold": 0.0,
    "cheap_percentile": 25,
    "window_minutes": 60,
}

# Optional September 2026 invoice starting values, never applied automatically.
INVOICE_COMPONENTS = (
    ("Network extraction", "Extragere din rețea", 0.03645),
    ("System service", "Serviciu de sistem", 0.0147),
    ("Distribution IT", "Distribuție IT", 0.02383),
    ("Distribution MT", "Distribuție MT", 0.06836),
    ("Distribution JT", "Distribuție JT", 0.2252),
    ("Green certificates", "Certificate verzi", 0.0740192),
    ("Cogeneration", "Cogenerare", 0.0145),
    ("Excise", "Acciză", 0.00768),
    ("CfD contribution", "Contribuție CfD", 0.000144),
)

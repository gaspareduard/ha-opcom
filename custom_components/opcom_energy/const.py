"""Constants for OPCOM Energy."""

from datetime import timedelta
from zoneinfo import ZoneInfo

DOMAIN = "opcom_energy"
NAME = "OPCOM Energy"
VERSION = "1.0.1"
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

"""Run the custom integration against Home Assistant, without network access."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def csv_text():
    return lambda day: (FIXTURES / f"{day}.csv").read_text()

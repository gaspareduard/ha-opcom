"""HTTP boundary failures are explicit and never become zero-price schedules."""

from datetime import date

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.opcom_energy.api import CannotConnect, OpcomClient
from custom_components.opcom_energy.const import CSV_URL
from custom_components.opcom_energy.prices import NotPublished, PriceError, parse_csv

DAY = date(2026, 10, 20)
URL = CSV_URL.format(day=20, month=10, year=2026)


async def test_real_csv_via_http(hass, aioclient_mock, csv_text):
    aioclient_mock.get(URL, text=csv_text("2026-10-20"))
    client = OpcomClient(async_get_clientsession(hass))
    assert len(parse_csv(await client.async_fetch(DAY), DAY)) == 96


@pytest.mark.parametrize("status", [403, 404, 429, 500])
async def test_http_errors(hass, aioclient_mock, status):
    aioclient_mock.get(URL, status=status)
    with pytest.raises(CannotConnect):
        await OpcomClient(async_get_clientsession(hass)).async_fetch(DAY)


async def test_timeout(hass, aioclient_mock):
    aioclient_mock.get(URL, exc=TimeoutError)
    with pytest.raises(CannotConnect):
        await OpcomClient(async_get_clientsession(hass)).async_fetch(DAY)


@pytest.mark.parametrize(
    ("body", "error"), [(b"", NotPublished), (b"\xff", PriceError), (b"x" * 512_001, PriceError)]
)
async def test_invalid_body(hass, aioclient_mock, body, error):
    aioclient_mock.get(URL, content=body)
    with pytest.raises(error):
        await OpcomClient(async_get_clientsession(hass)).async_fetch(DAY)


async def test_opcom_cookie_response_does_not_poison_following_downloads(
    hass, monkeypatch, csv_text, socket_enabled
):
    """Replay the real failure: a public export sets cookies rejected on reuse."""
    from aiohttp import web
    from aiohttp.test_utils import TestServer
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.opcom_energy.const import DOMAIN
    from custom_components.opcom_energy.coordinator import OpcomCoordinator

    seen = []

    async def export(request):
        seen.append(bool(request.cookies))
        if request.cookies:
            return web.Response(status=403)
        response = web.Response(text=csv_text("2026-10-20"))
        response.set_cookie("public_export_cookie", "sample")
        return response

    app = web.Application()
    app.router.add_get("/{day}", export)
    server = TestServer(app, host="127.0.0.1")
    await server.start_server()
    monkeypatch.setattr(
        "custom_components.opcom_energy.api.CSV_URL", str(server.make_url("/")) + "{day}"
    )
    entry = MockConfigEntry(domain=DOMAIN)
    client = OpcomCoordinator(hass, entry).client
    shared = async_get_clientsession(hass)
    shared.cookie_jar._unsafe = True  # Accept loopback cookies in this offline replay.
    try:
        for _ in range(3):
            assert len(parse_csv(await client.async_fetch(DAY), DAY)) == 96
        assert seen == [False, False, False]
        assert not shared.closed
    finally:
        client.session.detach()
        await server.close()

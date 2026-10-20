"""Asynchronous client for the public OPCOM day-ahead export."""

from datetime import date

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import CSV_URL, VERSION
from .prices import NotPublished, PriceError


class CannotConnect(Exception):
    """OPCOM could not be reached."""


class OpcomClient:
    """Use HA's shared session and normal TLS verification."""

    def __init__(self, session: ClientSession) -> None:
        self.session = session

    async def async_fetch(self, day: date) -> str:
        """Read a bounded CSV response; an empty export is not yet published."""
        url = CSV_URL.format(day=day.day, month=day.month, year=day.year)
        try:
            async with self.session.get(
                url,
                timeout=ClientTimeout(total=20),
                headers={
                    "User-Agent": f"OPCOMEnergy/{VERSION} (+https://github.com/gaspareduard/ha-opcom)"
                },
            ) as response:
                response.raise_for_status()
                # Bound decompressed bytes as well as Content-Length.
                body = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    body.extend(chunk)
                    if len(body) > 512_000:
                        raise PriceError("OPCOM response exceeds 500 KiB")
                text = body.decode("utf-8-sig")
        except (ClientError, TimeoutError) as err:
            raise CannotConnect("Unable to download OPCOM prices") from err
        except UnicodeDecodeError as err:
            raise PriceError("OPCOM returned an invalid CSV encoding") from err
        if not text.strip():
            raise NotPublished(f"No prices published for {day}")
        return text

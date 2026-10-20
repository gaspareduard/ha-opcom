"""Optional live source smoke check. Never run as part of offline tests."""

import asyncio
from datetime import UTC, datetime

from aiohttp import ClientSession

from custom_components.opcom_energy.api import OpcomClient
from custom_components.opcom_energy.const import MARKET_TZ
from custom_components.opcom_energy.prices import parse_csv


async def main():
    day = datetime.now(UTC).astimezone(MARKET_TZ).date()
    async with ClientSession() as session:
        rows = parse_csv(await OpcomClient(session).async_fetch(day), day)
    print(f"{day}: {len(rows)} validated intervals, {rows[0].start} to {rows[-1].end}")


if __name__ == "__main__":
    asyncio.run(main())

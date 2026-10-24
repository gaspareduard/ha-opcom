"""Shared retrieval, persistent validated cache and independent local ticks."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta, tzinfo

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnect, async_create_client
from .const import DEFAULT_OPTIONS, DOMAIN, MARKET_TZ, NAME
from .prices import (
    NotPublished,
    PriceError,
    PriceSlot,
    current_slot,
    day_bounds,
    parse_csv,
    validate_tariffs,
)

_LOGGER = logging.getLogger(__name__)


class OpcomCoordinator(DataUpdateCoordinator[tuple[PriceSlot, ...]]):
    """Fetch each missing market day independently, retaining valid known days."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass, _LOGGER, name=NAME, config_entry=entry, update_interval=timedelta(minutes=5)
        )
        self.options = DEFAULT_OPTIONS | dict(entry.options)
        try:
            validate_tariffs(self.options.get("tariff_versions", []))
            if self.options.get("pricing_mode", "simple") not in ("simple", "components"):
                raise PriceError("Unknown pricing mode")
        except PriceError as err:
            raise ConfigEntryError(str(err)) from err
        self.client = async_create_client(hass)
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.cache: dict[str, dict] = {}
        self.parsed: dict[str, tuple[PriceSlot, ...]] = {}
        self.retry_at: dict[str, datetime] = {}
        self.failures: dict[str, int] = {}
        self.errors: dict[str, str] = {}
        self.last_success: datetime | None = None
        self.last_attempt: datetime | None = None
        self.source_available = False

    @property
    def local_tz(self) -> tzinfo:
        """Reuse HA's resolved timezone without disk I/O in async callbacks."""
        return dt_util.get_default_time_zone()

    async def async_load_cache(self) -> None:
        """Treat stored data as untrusted; revalidate CSV before exposing prices."""
        stored = await self.store.async_load()
        if not isinstance(stored, dict) or not isinstance(stored.get("days"), dict):
            return
        now = dt_util.utcnow()
        for key, record in stored["days"].items():
            if not isinstance(record, dict) or not all(
                isinstance(record.get(field), str) for field in ("csv", "fetched_at")
            ):
                continue
            try:
                day = date.fromisoformat(key)
                if abs((day - now.astimezone(MARKET_TZ).date()).days) > 2:
                    continue
                slots = parse_csv(record["csv"], day)
                fetched = datetime.fromisoformat(record["fetched_at"])
                if fetched.tzinfo is None or fetched > now:
                    continue
            except (PriceError, ValueError, KeyError, TypeError):
                _LOGGER.debug("Ignoring invalid cached day %s", key)
                continue
            self.cache[key] = record
            self.parsed[key] = slots
            self.last_success = max(self.last_success or fetched, fetched)

    def required_days(self, now: datetime) -> tuple[date, ...]:
        """Fetch all market days intersecting local today and tomorrow."""
        local_day = now.astimezone(self.local_tz).date()
        start, _ = day_bounds(local_day, self.local_tz)
        _, end = day_bounds(local_day + timedelta(days=1), self.local_tz)
        first = start.astimezone(MARKET_TZ).date()
        last = (end - timedelta(microseconds=1)).astimezone(MARKET_TZ).date()
        return tuple(first + timedelta(days=i) for i in range((last - first).days + 1))

    async def _async_update_data(self) -> tuple[PriceSlot, ...]:
        now = dt_util.utcnow()
        required = self.required_days(now)
        changed = False
        for day in required:
            key = day.isoformat()
            if now < self.retry_at.get(key, datetime.min.replace(tzinfo=UTC)):
                continue
            record = self.cache.get(key)
            if record and now - datetime.fromisoformat(record["fetched_at"]) < timedelta(hours=6):
                continue
            self.last_attempt = now
            try:
                text = await self.client.async_fetch(day)
                slots = parse_csv(text, day)
            except (CannotConnect, PriceError) as err:
                self.errors[key] = (
                    "not_published" if isinstance(err, NotPublished) else type(err).__name__
                )
                attempt = self.failures.get(key, 0) + 1
                self.failures[key] = attempt
                self.retry_at[key] = now + timedelta(minutes=min(5 * 2 ** min(attempt - 1, 4), 60))
                _LOGGER.debug("Unable to refresh %s: %s", key, err)
                continue
            self.errors.pop(key, None)
            self.failures.pop(key, None)
            self.retry_at.pop(key, None)
            self.parsed[key] = slots
            self.cache[key] = {"csv": text, "fetched_at": now.isoformat()}
            self.last_success = now
            changed = True

        keep = {d.isoformat() for d in required}
        for mapping in (self.cache, self.parsed, self.errors, self.retry_at, self.failures):
            for key in set(mapping) - keep:
                del mapping[key]
        if changed:
            self.store.async_delay_save(lambda: {"days": self.cache}, 1)
        slots = tuple(
            sorted((s for rows in self.parsed.values() for s in rows), key=lambda s: s.start)
        )
        current_market = now.astimezone(MARKET_TZ).date().isoformat()
        self.source_available = current_market in self.cache and current_market not in self.errors
        if current_slot(slots, now) is None:
            raise UpdateFailed("No validated OPCOM price covers the current interval")
        return slots

    @callback
    def async_start_clock(self) -> None:
        """Notify entities on boundaries without fetching or resetting the poll timer."""
        self.config_entry.async_on_unload(
            async_track_utc_time_change(self.hass, self._tick, minute=[0, 15, 30, 45], second=0)
        )

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_update_listeners()

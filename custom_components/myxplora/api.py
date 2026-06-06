"""Thin async wrapper around pyxplora-api for *passive* WatchLastLocate reads.

Only passive calls are used: the watch's last self-reported snapshot
(`loadWatchLocation(with_ask=False)`) plus the passive `watches` online field.
No `askWatchLocate`/tracking commands are ever sent. See FINDINGS.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from aiohttp import ClientSession
from pyxplora_api.pyxplora_api_async import PyXploraApi

from . import _v2

_LOGGER = logging.getLogger(__name__)


class XploraAuthError(Exception):
    """Login failed (bad credentials or a rejected app key)."""


@dataclass
class WatchData:
    """One passive snapshot for a single watch."""

    wuid: str
    name: str
    online: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    sw_version: str | None = None
    battery: int | None = None
    charging: bool = False
    step: int | None = None
    distance: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    accuracy: int | None = None
    address: str | None = None
    poi: str | None = None
    locate_type: str | None = None
    in_safe_zone: bool = False
    safe_zone_label: str | None = None
    located_at: datetime | None = None
    battery_reported_at: datetime | None = None


def _as_float(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f


def _as_dt(value: object) -> datetime | None:
    try:
        epoch = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if epoch <= 0:
        return None
    return datetime.fromtimestamp(epoch, tz=UTC)


class XploraApi:
    """Login once, then read each watch passively."""

    def __init__(
        self,
        *,
        country_code: str,
        phone: str,
        email: str,
        password: str,
        language: str,
        timezone: str,
        session: ClientSession,
    ) -> None:
        _v2.apply()
        self._client = PyXploraApi(
            countrycode=country_code,
            phoneNumber=phone,
            password=password,
            userLang=language,
            timeZone=timezone,
            email=email or None,
            session=session,
        )
        # Never hammer the login surface (default 3 -> 5 attempts).
        self._client.maxRetries = 0
        self._client.retryDelay = 1
        self._logged_in = False

    async def async_login(self) -> None:
        """Authenticate. Raises XploraAuthError on failure."""
        from pyxplora_api.exception_classes import LoginError

        try:
            await self._client.init(forceLogin=True)
        except LoginError as err:
            raise XploraAuthError(str(err)) from err
        self._logged_in = True

    async def async_get_data(self) -> dict[str, WatchData]:
        """Return a passive snapshot for every watch on the account."""
        if not self._logged_in:
            await self.async_login()

        result: dict[str, WatchData] = {}
        wuids = self._client.getWatchUserIDs()
        for wuid in wuids:
            result[wuid] = await self._read_watch(wuid)

        # Self-heal: if every watch came back empty the token likely expired.
        if wuids and all(w.battery is None for w in result.values()):
            _LOGGER.debug("Empty read for all watches; re-authenticating once")
            await self.async_login()
            for wuid in wuids:
                result[wuid] = await self._read_watch(wuid)
        return result

    async def _read_watch(self, wuid: str) -> WatchData:
        name = str(self._client.getWatchUserNames(wuid))
        info = await self._watch_info(wuid)  # passive `watches` record
        loc = await self._client.loadWatchLocation(wuid, with_ask=False)  # passive
        raw = (loc or {}).get("watch_last_location", {}) or {}

        lat = _as_float(raw.get("lat"))
        lng = _as_float(raw.get("lng"))
        # The API returns 0.0/0.0 when it has never had a fix.
        if lat == 0.0 and lng == 0.0:
            lat = lng = None

        battery = raw.get("battery")
        return WatchData(
            wuid=wuid,
            name=name,
            online=str(info.get("onlineStatus")) if info.get("onlineStatus") else None,
            model=info.get("groupName") or None,
            manufacturer=(info.get("brand") or "").title() or None,
            sw_version=info.get("osVersion") or None,
            battery=int(battery) if battery is not None else None,
            charging=bool(raw.get("isCharging")),
            step=raw.get("step"),
            distance=_as_float(raw.get("distance")),
            latitude=lat,
            longitude=lng,
            accuracy=raw.get("rad") if isinstance(raw.get("rad"), int) else None,
            address=raw.get("addr") or None,
            poi=raw.get("poi") or None,
            locate_type=raw.get("locateType") or None,
            in_safe_zone=bool(raw.get("isInSafeZone")),
            safe_zone_label=raw.get("safeZoneLabel") or None,
            located_at=_as_dt(raw.get("tm")),
            battery_reported_at=_as_dt(raw.get("batteryTm")),
        )

    async def _watch_info(self, wuid: str) -> dict:
        """The passive `watches` record (online status, model, brand, firmware).

        No locate command — same query we already need for online status.
        """
        try:
            data = await self._client._gql_handler.getWatches_a(wuid)
            watches = data.get("watches", [])
            if watches:
                return watches[0]
        except Exception:  # noqa: BLE001 - best-effort, never fail the whole poll
            _LOGGER.debug("watch info read failed for %s", wuid, exc_info=True)
        return {}

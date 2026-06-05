"""Poll battery SoC for every watch on an Xplora account.

This is a thin evaluation harness around `pyxplora-api`. It logs in once,
enumerates all watches on the account, and prints the data points a Home
Assistant battery-supervision integration would need: name, battery %,
charging flag, and online status.

Credentials are read from environment variables (a local .env is supported):

    XPLORA_COUNTRYCODE   e.g. "+46"
    XPLORA_PHONE         phone number without country code (optional if email)
    XPLORA_EMAIL         email login (takes precedence over phone)
    XPLORA_PASSWORD      account password
    XPLORA_LANG          e.g. "en-US"
    XPLORA_TIMEZONE      e.g. "Europe/Stockholm"

Run:  uv run xplora-soc-eval
      uv run xplora-soc-eval --watch 5   # repoll every 5s
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from pyxplora_api.pyxplora_api_async import PyXploraApi


@dataclass
class WatchReading:
    wuid: str
    name: str
    battery: int
    is_charging: bool
    online: str

    def format(self) -> str:
        bar = self._bar(self.battery)
        charge = "⚡charging" if self.is_charging else "         "
        return (
            f"  {self.name:<20} {bar} {self.battery:>3}%  "
            f"{charge}  [{self.online}]  ({self.wuid})"
        )

    @staticmethod
    def _bar(pct: int, width: int = 10) -> str:
        filled = round(max(0, min(100, pct)) / 100 * width)
        return "[" + "#" * filled + "-" * (width - filled) + "]"


def _load_credentials() -> dict[str, str]:
    load_dotenv()
    creds = {
        "countrycode": os.environ.get("XPLORA_COUNTRYCODE", ""),
        "phoneNumber": os.environ.get("XPLORA_PHONE", ""),
        "password": os.environ.get("XPLORA_PASSWORD", ""),
        "userLang": os.environ.get("XPLORA_LANG", "en-US"),
        "timeZone": os.environ.get("XPLORA_TIMEZONE", "Europe/Stockholm"),
        "email": os.environ.get("XPLORA_EMAIL", ""),
    }
    if not creds["password"]:
        raise SystemExit(
            "Missing credentials. Copy .env.example to .env and fill it in."
        )
    if not creds["email"] and not creds["phoneNumber"]:
        raise SystemExit("Provide either XPLORA_EMAIL or XPLORA_PHONE.")
    return creds


async def _build_client(creds: dict[str, str], session=None) -> PyXploraApi:
    from . import v2

    v2.apply()  # o2o app key is dead; target the V2 app (see v2.py / FINDINGS.md)
    client = PyXploraApi(
        countrycode=creds["countrycode"],
        phoneNumber=creds["phoneNumber"],
        password=creds["password"],
        userLang=creds["userLang"],
        timeZone=creds["timeZone"],
        email=creds["email"] or None,
        session=session,
    )
    # Cap login hammering: default maxRetries=3 means 5 login attempts, and on a
    # genuine auth failure retrying never helps — it just burns login attempts
    # (loginFailCount) and risks a lockout. See INVESTIGATION.md WS3.
    client.maxRetries = 0  # -> 2 attempts
    client.retryDelay = 1
    await client.init(forceLogin=True)
    return client


async def _online_passive(client: PyXploraApi, wuid: str) -> str:
    """Online status from the passive `watches` query — no active locate."""
    try:
        data = await client._gql_handler.getWatches_a(wuid)
        watches = data.get("watches", [])
        if watches:
            return str(watches[0].get("onlineStatus", "UNKNOWN"))
    except Exception:  # noqa: BLE001
        pass
    return "UNKNOWN"


async def _read_all(client: PyXploraApi) -> list[WatchReading]:
    # Passive only: read the last *reported* battery (with_ask=False) and the
    # onlineStatus field. We never send askWatchLocate — see INVESTIGATION.md.
    wuids = client.getWatchUserIDs()  # sync, returns list[str]
    readings: list[WatchReading] = []
    for wuid in wuids:
        name = client.getWatchUserNames(wuid)  # sync
        loc = await client.loadWatchLocation(wuid, with_ask=False)
        battery = (loc or {}).get("watch_battery")
        readings.append(
            WatchReading(
                wuid=wuid,
                name=str(name),
                battery=int(battery) if battery is not None else -1,
                is_charging=bool((loc or {}).get("watch_charging")),
                online=await _online_passive(client, wuid),
            )
        )
    return readings


def _print_report(readings: list[WatchReading]) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nXplora battery report @ {stamp}  ({len(readings)} watch(es))")
    print("-" * 78)
    if not readings:
        print("  No watches found on this account.")
    for r in sorted(readings, key=lambda x: x.battery):
        print(r.format())
    print("-" * 78)


async def _run(poll_interval: float | None) -> None:
    creds = _load_credentials()
    print("Logging in to Xplora cloud ...")
    client = await _build_client(creds)
    print("Login OK.")
    try:
        while True:
            t0 = time.monotonic()
            readings = await _read_all(client)
            elapsed = time.monotonic() - t0
            _print_report(readings)
            print(f"  (poll took {elapsed:.2f}s)")
            if poll_interval is None:
                break
            await asyncio.sleep(poll_interval)
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Repoll every SECONDS instead of running once.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.watch))


if __name__ == "__main__":
    main()

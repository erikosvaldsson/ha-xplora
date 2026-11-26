"""Instrumented, *passive* battery probe — Phase 1 of INVESTIGATION.md.

Differences from main.py:
- Reads battery/charging from the **last reported** location
  (`loadWatchLocation(wuid, with_ask=False)`), so it never sends an active
  `askWatchLocate` command to the watch. Online status comes from the passive
  `watches` query. Footprint per poll: 1 `watches` call + 1 `watchLastLocate`
  per watch, no active locates.
- Instruments every GraphQL operation (name, HTTP status, latency, errors) so
  we can see exactly how many requests a poll costs and recognize a ban
  signature if one ever appears (WS1).
- Reports `batteryTm` staleness so we know how old a passive reading is.

This makes a single login + one passive read per watch and stops. It does NOT
loop. Run:  uv run xplora-probe
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time

import aiohttp
from pyxplora_api import graphql_client as _gc
from pyxplora_api.pyxplora_api_async import PyXploraApi

from .main import _build_client, _load_credentials


@dataclass
class RequestLog:
    """Captures every GraphQL operation the library issues."""

    entries: list[dict] = field(default_factory=list)

    def install(self) -> None:
        """Monkeypatch GraphqlClient so each operation is timed and recorded."""
        orig_ha = _gc.GraphqlClient.ha_execute_async
        orig_async = _gc.GraphqlClient.execute_async
        log = self.entries

        async def _wrap(orig, this, *args, **kwargs):
            op = kwargs.get("operation_name") or (args[2] if len(args) > 2 else "?")
            t0 = time.monotonic()
            status = "ok"
            try:
                return await orig(this, *args, **kwargs)
            except Exception as err:  # noqa: BLE001 - we want the ban signature
                status = f"{type(err).__name__}: {err}"
                raise
            finally:
                log.append(
                    {"op": op, "ms": round((time.monotonic() - t0) * 1000), "status": status}
                )

        async def ha(this, *a, **k):
            return await _wrap(orig_ha, this, *a, **k)

        async def ex(this, *a, **k):
            return await _wrap(orig_async, this, *a, **k)

        _gc.GraphqlClient.ha_execute_async = ha
        _gc.GraphqlClient.execute_async = ex

    def summary(self) -> str:
        lines = [f"  {e['op']:<24} {e['ms']:>5}ms  {e['status']}" for e in self.entries]
        bad = [e for e in self.entries if e["status"] != "ok"]
        head = f"GraphQL operations this run: {len(self.entries)} ({len(bad)} error(s))"
        return head + "\n" + "\n".join(lines)


@dataclass
class PassiveReading:
    wuid: str
    name: str
    battery: int | None
    is_charging: bool
    battery_age: str  # human-readable staleness of the reading

    def format(self) -> str:
        b = "—" if self.battery is None else f"{self.battery}%"
        chg = "⚡" if self.is_charging else " "
        return f"  {self.name:<20} {b:>4} {chg}  reported {self.battery_age} ago  ({self.wuid})"


def _age(tm_seconds: float | None) -> str:
    if not tm_seconds:
        return "unknown time"
    delta = max(0, time.time() - float(tm_seconds))
    if delta < 90:
        return f"{int(delta)}s"
    if delta < 5400:
        return f"{int(delta / 60)}m"
    return f"{delta / 3600:.1f}h"


async def _passive_read(client: PyXploraApi, wuid: str) -> PassiveReading:
    # with_ask=False -> read last reported location/battery, no active locate.
    loc = await client.loadWatchLocation(wuid, with_ask=False)
    raw = loc.get("watch_last_location", {}) if loc else {}
    name = str(client.getWatchUserNames(wuid))
    return PassiveReading(
        wuid=wuid,
        name=name,
        battery=loc.get("watch_battery") if loc else None,
        is_charging=bool(loc.get("watch_charging")) if loc else False,
        battery_age=_age(raw.get("batteryTm") or raw.get("tm")),
    )


async def _run() -> None:
    creds = _load_credentials()
    reqlog = RequestLog()
    reqlog.install()

    # Pass our own session with a trace hook so we also see raw HTTP status codes.
    trace = aiohttp.TraceConfig()

    async def on_end(session, ctx, params):  # noqa: ANN001
        print(f"    HTTP {params.response.status} {params.method} {params.url.host}")

    trace.on_request_end.append(on_end)
    session = aiohttp.ClientSession(trace_configs=[trace])

    try:
        print("Logging in (one login, token reused for the reads) ...")
        client = await _build_client(creds, session=session)

        token = getattr(client, "_issueToken", None) or {}
        print(f"Login OK. token expireDate={token.get('expireDate')} (epoch ms) — "
              "informs how rarely we must re-login (WS3).")

        wuids = client.getWatchUserIDs()
        print(f"\nPassive battery read for {len(wuids)} watch(es) — NO active locate:")
        print("-" * 78)
        for wuid in wuids:
            r = await _passive_read(client, wuid)
            print(r.format())
        print("-" * 78)
    finally:
        print("\n" + reqlog.summary())
        await session.close()


def main() -> None:
    # An explicit parser so that `--help` (or any flag) does NOT fall through and
    # silently fire a live login. Each run logs in once against the real account.
    import argparse

    argparse.ArgumentParser(
        description="Single passive battery probe (one login + last-reported "
        "battery per watch, no active locate). Reads creds from .env."
    ).parse_args()
    asyncio.run(_run())


if __name__ == "__main__":
    main()

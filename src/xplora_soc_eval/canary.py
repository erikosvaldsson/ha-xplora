"""Phase 3 canary: does V2 tolerate slow passive polling without a ban?

Logs in once (reusing a saved token across restarts), then reads battery SoC
*passively* every ~interval with jitter. It watches every GraphQL op for error
codes / bad HTTP / exceptions, re-logs-in once if the token expires, and backs
off exponentially on anything that looks like a block — never hammering. One
JSONL record per cycle goes to canary.jsonl for multi-day review.

Run (default 90 min cadence):     uv run xplora-canary
Quick self-test (3 fast cycles):  uv run xplora-canary --interval 5 --cycles 3
Long run in background:           nohup uv run xplora-canary >/dev/null 2>&1 &
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from pyxplora_api import graphql_client as _gc
from pyxplora_api.exception_classes import LoginError

from . import tokens
from .main import _load_credentials, _new_client, _read_all

LOG = Path("canary.jsonl")
MAX_BACKOFF = 6 * 3600  # 6 h cap


class RequestMonitor:
    """Records every GraphQL op's timing, GraphQL error codes, and HTTP status
    so a cycle can be classified healthy vs (possibly) blocked."""

    def __init__(self) -> None:
        self.records: list[dict] = []
        self.statuses: list[int] = []

    def install(self) -> None:
        orig_ha = _gc.GraphqlClient.ha_execute_async
        orig_ex = _gc.GraphqlClient.execute_async
        recs = self.records

        async def wrap(orig, this, *a, **k):
            op = k.get("operation_name") or (a[2] if len(a) > 2 else "?")
            t0 = time.monotonic()
            codes: list = []
            err = None
            try:
                res = await orig(this, *a, **k)
                if isinstance(res, dict):
                    codes.extend(e.get("code") or e.get("message") for e in (res.get("errors") or []))
                return res
            except Exception as ex:  # noqa: BLE001 - capture ban/transport signatures
                err = repr(ex)
                raise
            finally:
                recs.append({"op": op, "ms": round((time.monotonic() - t0) * 1000), "codes": codes, "err": err})

        async def ha(this, *a, **k):
            return await wrap(orig_ha, this, *a, **k)

        async def ex(this, *a, **k):
            return await wrap(orig_ex, this, *a, **k)

        _gc.GraphqlClient.ha_execute_async = ha
        _gc.GraphqlClient.execute_async = ex

    def trace_config(self) -> aiohttp.TraceConfig:
        tc = aiohttp.TraceConfig()

        async def on_end(session, ctx, params):  # noqa: ANN001
            self.statuses.append(params.response.status)

        tc.on_request_end.append(on_end)
        return tc

    def reset(self) -> None:
        self.records.clear()
        self.statuses.clear()

    def error_codes(self) -> list:
        return [c for r in self.records for c in r["codes"] if c]

    def exceptions(self) -> list:
        return [r["err"] for r in self.records if r["err"]]

    def bad_status(self) -> list[int]:
        return [s for s in self.statuses if s != 200]


def _log(record: dict) -> None:
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")
    print(json.dumps(record))


async def _ensure_client(creds, session):
    """Return a logged-in client, reusing a saved token when still valid."""
    client = _new_client(creds, session)
    if tokens.restore(client):
        _log({"event": "token_restored", "expireDate": (client._issueToken or {}).get("expireDate")})
        return client
    await client.init(forceLogin=True)
    tokens.save(client)
    _log({"event": "login", "expireDate": (client._issueToken or {}).get("expireDate")})
    return client


def _is_auth_failure(mon: RequestMonitor) -> bool:
    return any(str(c) == "E000004" or "Authentication failed" in str(c) for c in mon.error_codes())


async def _run(interval: float, jitter: float, max_cycles: int) -> None:
    creds = _load_credentials()
    mon = RequestMonitor()
    mon.install()
    session = aiohttp.ClientSession(trace_configs=[mon.trace_config()])

    consecutive_failures = 0
    cycle = 0
    try:
        client = await _ensure_client(creds, session)
        relogged = False
        while True:
            cycle += 1
            mon.reset()
            t0 = time.monotonic()
            readings = None
            fatal = None
            try:
                readings = await _read_all(client)
            except Exception as ex:  # noqa: BLE001
                fatal = repr(ex)

            errs = mon.error_codes()
            bad_http = mon.bad_status()
            auth_fail = _is_auth_failure(mon)
            healthy = readings is not None and not errs and not bad_http and fatal is None

            # Token expiry: try exactly one re-login, then retry the cycle soon.
            if auth_fail and not relogged:
                _log({"event": "reauth", "reason": "auth_failure_during_poll"})
                try:
                    await client.init(forceLogin=True)
                    tokens.save(client)
                    relogged = True
                    await asyncio.sleep(5)
                    cycle -= 1
                    continue
                except LoginError as e:
                    _log({"event": "reauth_failed", "error": str(e), "note": "possible ban/lockout"})

            record = {
                "event": "poll",
                "cycle": cycle,
                "healthy": healthy,
                "ms": round((time.monotonic() - t0) * 1000),
                "requests": len(mon.records),
                "watches": [
                    {"name": r.name, "battery": r.battery, "charging": r.is_charging, "online": r.online}
                    for r in (readings or [])
                ],
            }
            if not healthy:
                record.update({"error_codes": errs, "bad_http": bad_http, "exception": fatal})

            if healthy:
                consecutive_failures = 0
                relogged = False
                _log(record)
                sleep = interval * (1 + random.uniform(-jitter, jitter))
            else:
                consecutive_failures += 1
                record["consecutive_failures"] = consecutive_failures
                # Hard exponential backoff — never hammer into a block.
                sleep = min(MAX_BACKOFF, 600 * (2 ** (consecutive_failures - 1)))
                record["backoff_s"] = round(sleep)
                _log(record)

            if max_cycles and cycle >= max_cycles:
                break
            await asyncio.sleep(sleep)
    finally:
        await session.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--interval", type=float, default=5400, help="base seconds between polls (default 5400 = 90 min)")
    p.add_argument("--jitter", type=float, default=0.15, help="± fraction randomization of interval (default 0.15)")
    p.add_argument("--cycles", type=int, default=0, help="stop after N cycles (0 = run forever)")
    args = p.parse_args()
    asyncio.run(_run(args.interval, args.jitter, args.cycles))


if __name__ == "__main__":
    main()

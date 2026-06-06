# xplora-eval

A small [uv](https://docs.astral.sh/uv/) project that evaluates
[`pyxplora-api`](https://pypi.org/project/pyxplora-api/) as a foundation for a
Home Assistant integration that supervises **battery state-of-charge (SoC)**
across multiple Xplora® watches.

## Quick start

```bash
uv sync
cp .env.example .env      # then fill in your Xplora credentials
uv run xplora-eval            # poll once
uv run xplora-eval --watch 3600   # repoll every hour (see ban note below)
```

Example output:

```
Xplora battery report @ 2026-06-04 09:40:11  (2 watch(es))
------------------------------------------------------------------------------
  Kid A                [#---------]   8%  ⚡charging  [ONLINE]  (abc123)
  Kid B                [#######---]  72%             [ONLINE]  (def456)
------------------------------------------------------------------------------
```

## What it exercises

The harness logs in once and, per watch, reads exactly the data points a
battery-supervision integration needs:

| Data point     | `pyxplora-api` method (async client)        | Type   |
| -------------- | ------------------------------------------- | ------ |
| Watch IDs      | `getWatchUserIDs()`                          | sync   |
| Display name   | `getWatchUserNames(wuid)`                    | sync   |
| Battery %      | `await getWatchBattery(wuid)`                | async  |
| Charging flag  | `await getWatchIsCharging(wuid)`             | async  |
| Online status  | `await getWatchOnlineStatus(wuid)`           | async  |

Async client: `from pyxplora_api.pyxplora_api_async import PyXploraApi`.
Note the mixed sync/async surface — ID/name lookups are synchronous, the
live telemetry calls are coroutines. The harness fans the three per-watch
telemetry calls out with `asyncio.gather`.

## API evaluation notes

- **Version tested:** `pyxplora-api` 2.12.9 (PyPI), Python ≥ 3.9. Library repo
  last released v2.12.10 (Feb 2025).
- **Auth:** email *or* phone+country code + password. Email wins if both set.
  `init(forceLogin=True)` performs a real cloud login each start.
- **Multi-watch:** `getWatchUserIDs()` returns every watch on the account, so
  supervising "a number of watches" from one account is straightforward.
- **No public/official API** — this is a reverse-engineered cloud client.
  Behaviour can change without notice.

## ⚠️ Feasibility risk before you build a successor

The existing integration, [`Ludy87/xplora_watch`](https://github.com/Ludy87/xplora_watch),
was **archived (read-only) on 2025-11-11**. The maintainer's stated reason:

> "Due to blocking by Xplora® through IP-ban, the application will not be
> developed further."

This is the single most important thing to validate first. The shutdown was
**not** loss of interest — Xplora actively IP-bans the polling clients.

### The slow-poll hypothesis

The plan for a successor is to **avoid the ban by polling rarely — once every
1–2 hours** rather than at HA's typical sub-minute cadence. This is plausible
and worth testing, but treat it as a hypothesis, not a guarantee:

- For battery supervision specifically, hourly resolution is plenty — SoC does
  not move fast enough to need minute-level polling. The use case and the
  mitigation line up well.
- **Unknowns to validate:** whether the ban is rate-based (calls/hour) or
  triggered by *any* automated login pattern; whether each poll's
  `init(forceLogin=True)` login is itself a trigger (re-authenticating every
  hour may look worse than the data fetch). Investigate session reuse /
  token persistence so a slow poller logs in once and refreshes rather than
  re-authing every cycle.
- Add jitter and exponential backoff on errors; one 429/ban response should
  back off hard, not keep hammering.
- The archived author was banned despite presumably knowing the API best, so
  budget for the possibility that even slow polling eventually trips it.

Use this harness to probe tolerance empirically: run `--watch 3600` against
your own account for a few days and watch for failures before committing to a
full HACS integration.

## Does a successor already exist?  (checked 2026-06-04)

No. Findings:

- The [`xplora-watch` GitHub topic](https://github.com/topics/xplora-watch)
  lists **only** `Ludy87/xplora_watch` — no maintained forks or alternatives.
- The underlying library [`Ludy87/pyxplora_api`](https://github.com/Ludy87/pyxplora_api)
  is by the same author and is the only Python client on PyPI; no fork has
  taken over.
- Community threads point people toward unrelated SEtracker2-based watches, not
  an Xplora successor.

So building one would **not** be redundant — but the archived original's
IP-ban is why nobody has picked it up. That's the problem to solve, not the
HA glue code (which already exists in the archived repo as a reference you can
fork from, license permitting).

## Layout

```
src/xplora_eval/
  __init__.py   # exports main
  main.py       # login + per-watch SoC report
.env.example    # credential template (.env is gitignored)
pyproject.toml  # uv project, pins pyxplora-api + python-dotenv
```

# IP-ban workaround investigation plan

Goal: determine whether a Home Assistant integration can poll Xplora battery SoC
for several watches **without** triggering the IP-ban that killed
[`Ludy87/xplora_watch`](https://github.com/Ludy87/xplora_watch) (archived
2025-11-11). Decide go/no-go before building the HACS integration.

## Success criteria

A configuration that runs for **≥ 2 weeks** polling all watches on a real
account without a ban or auth lockout, at a cadence good enough for battery
supervision (hourly is fine). If no such configuration exists, fail fast and
document why.

## What we already know (from reading pyxplora-api 2.12.9 source)

These facts shape every experiment below.

1. **Single endpoint.** All traffic is GraphQL `POST https://api.myxplora.com/api`
   (`const.py`). The ban is whatever that host decides to do about your IP.
2. **Battery read is NOT passive.** `getWatchBattery`, `getWatchIsCharging`,
   `getWatchOnlineStatus` all route through `loadWatchLocation()` →
   `askWatchLocate()`, which sends an **active locate command to the watch**.
   My eval harness fans these out with `asyncio.gather`, so it can fire *three*
   locate cycles per watch per poll. This is the loudest, most flaggable,
   battery-draining call pattern possible — and we don't even need location.
   **First question: is there a passive query that returns battery without
   asking the watch to locate?** (`watchesQ` / track queries are candidates.)
3. **Tokens are reusable.** Login (`signInWithEmailOrPhone`) returns `token`,
   `refreshToken`, `expireDate`, and a `w360 {token, secret}` pair. Requests
   authorize via a `H-BackDoor-Authorization: Bearer <token>:<secret>` header.
   There is a `refreshToken` mutation (`refresh_token_a`). So re-login every
   poll is avoidable — but the library re-logs-in readily.
4. **The client has retry storms.** `pyxplora_api_async` wraps most calls in
   `while retry_counter < maxRetries + 2: ... asyncio.sleep(retryDelay)` loops,
   and `init()` can recursively re-login. A single ban/error can therefore turn
   into a burst of retries + re-logins — the opposite of what we want. Any
   integration MUST cap/disable this.
5. **Fingerprint headers.** Fixed desktop-Chrome `User-Agent`, plus custom
   `H-Date`, `H-Tid` (unix ts), and `client: APP`. The UA does not match the
   real Xplora mobile app, which is itself a possible detection signal.
6. **Login is the sensitive surface.** The schema exposes `loginFailCount` —
   auth attempts are counted server-side. Minimizing logins likely matters more
   than minimizing data reads.

> Net: the original ban was probably driven by **active-locate volume and/or
> repeated logins**, not by reading a battery number. That is good news — both
> are things we can cut dramatically.

## Workstreams

Run them roughly in this order; each gates the next.

### WS1 — Characterize the ban signature (must do first)

We can't avoid what we can't recognize. **Characterize the ban from
documentation, not by provoking it** — we never deliberately trip the ban to
study it; that is the exact harassment that got the original banned.
- Learn the ban's shape from existing reports: is it `403`/`429`/connection
  reset, or a GraphQL error like `AUTH_FAIL`? Account-level lockout vs
  IP-level block? Temporary vs permanent? How long until it lifts?
- Primary source: the archived repo's issues + commit history almost certainly
  describe what the ban looked like. Read those first — zero API traffic.
- Instrument every request (HTTP status, GraphQL `errors[]`, latency, headers)
  so that *if* a ban ever happens during normal low-rate use, we recognize it —
  passive observation, not active probing.
- **Deliverable:** a documented "ban detector" predicate + known recovery time.

### WS2 — Minimize per-poll footprint

- Confirm finding #2: does a passive battery query exist? Trace `watchesQ` and
  the track/locate queries; capture raw responses to see which fields
  (`battery`, `isCharging`/`Charging`, `onlineStatus`) come back **without**
  `askWatchLocate`. If yes, bypass `loadWatchLocation` entirely.
- Collapse to **one request per watch per poll** (or one for all watches if a
  batch query exists). Stop calling the three getters separately.
- **Deliverable:** lowest possible request count per cycle, location-free.

### WS3 — Eliminate redundant logins

- Persist `token` / `refreshToken` / `w360` + `expireDate` to disk; reuse across
  polls and across HA restarts.
- Refresh via the `refreshToken` mutation only when near expiry; full
  `signInWithEmailOrPhone` only when refresh fails.
- Disable the library's recursive re-login / retry loops (`maxRetries`,
  `retryDelay`); replace with our own single-shot + hard backoff.
- **Deliverable:** a steady state of ~0 logins/day, N small reads/day.

### WS4 — Cadence & jitter tuning (the user's core hypothesis)

- Default to 1–2 h intervals; add ±random jitter so polls aren't a clockwork
  signature. Skip polls while a watch is `charging` or offline (no SoC news).
- Hard exponential backoff on any WS1 ban signal; never retry into a ban.
- Use `--watch <seconds>` here as the probe rig. Start conservative (e.g.
  7200s), only tighten if stable.
- **Deliverable:** the slowest acceptable cadence that still supervises battery.

### WS5 — Reduce fingerprintability (only if WS1–4 insufficient)

- Test whether matching the real app's User-Agent/headers changes ban behavior,
  or whether it's purely volume/IP. Change one variable at a time.
- Note: altering client identity is itself reverse-engineering and could *trip*
  detection — treat as a later, low-priority lever.

### WS6 — IP-level mitigations (last resort)

The ban is on IP, so these are the nuclear options if behavior alone fails:
- Home/residential dynamic IP (router reconnect to rotate) vs the more-blocked
  datacenter ranges.
- Egress via VPN / residential proxy; per-account separate egress.
- Weigh cost/complexity — if it needs a proxy to work, the integration is
  fragile by design and that should inform go/no-go.

## Phased execution & go/no-go gates

| Phase | Work | Gate to proceed |
| ----- | ---- | --------------- |
| 0 | Read archived repo issues/commits for ban history (WS1 desk research) | Understand prior ban triggers |
| 1 | Instrument harness; one passive, location-free read per watch (WS1–2) | Battery readable without `askWatchLocate` |
| 2 | Token persistence + refresh, retries disabled (WS3) | Steady state ~0 logins/day |
| 3 | 2-week canary at 1–2 h + jitter + backoff (WS4) | No ban for 14 days |
| 4 | Only if Phase 3 fails: WS5/WS6 | A stable config found, or documented no-go |

Do **not** start the HACS integration until Phase 3 passes.

## Risks / ethics

- **Account/IP burn.** Experiments can get the test account or home IP banned.
  Use a dedicated test account; know the recovery time (WS1) before probing
  aggressively; one canary at a time.
- **It may just not be possible.** The original author knew this API best and
  still got banned. Budget for a documented "no" as a valid outcome.
- **ToS.** This is an unofficial, reverse-engineered client. Stay within
  personal use of your own watches/account; don't scale or redistribute keys.

## Immediate next actions

1. Read `Ludy87/xplora_watch` issues/releases for the ban post-mortem (Phase 0).
2. Add request-level logging to the harness and dump raw `watchesQ` /
   track-query responses to find a passive battery field (Phase 1 / WS2).
3. Decide test-account + egress setup before any multi-day run.

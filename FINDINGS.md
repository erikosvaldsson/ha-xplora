# Findings — executing the IP-ban investigation plan

Results of running Phase 0–1 of [INVESTIGATION.md](INVESTIGATION.md). No ban was
provoked; all live traffic was one login attempt's worth.

## Phase 0 — ban post-mortem (zero API traffic)

- The original integration was archived 2025-11-11; maintainer cited Xplora
  IP-banning the clients.
- Issue [#498](https://github.com/Ludy87/xplora_watch/issues/498) (2025-03-31,
  integration v2.14.2): a user running **just two watches** had their IP
  *blacklisted* — badly enough they could no longer configure watches on their
  local WiFi. Confirmed by the Xplora team. Full comment thread wasn't
  retrievable headless; worth reading manually for the exact trigger/recovery.
- Takeaway: the ban triggered at a low watch count under the **stock polling
  behaviour** (frequent, active-locate-driven). That behaviour is what we
  change below.

## Phase 1 — minimize footprint (static analysis, code-grounded)

The decisive finding: **battery can be read passively.**

- `getWatchBattery` / `getWatchIsCharging` / `getWatchOnlineStatus` all funnel
  through `loadWatchLocation(wuid, with_ask=True)`, which sends an **active
  `askWatchLocate` command** to the watch (GPS ping) before reading.
- But `loadWatchLocation(wuid, with_ask=False)` skips `askWatchLocate` and reads
  the **last reported** values from the `watchLastLocate` query
  (`gql_queries.py: locateQ`). That fragment includes `battery`, `isCharging`,
  and **`batteryTm`** (timestamp of the reading) — everything SoC supervision
  needs, with no command sent to the device.
- Online status is available passively too: the `watches` query (`watchesQ`)
  returns `onlineStatus` per watch, for all watches in one call.

### Footprint per poll

| Approach | Requests / poll (N watches) | Active locates |
| -------- | --------------------------- | -------------- |
| Stock getters (what main.py did originally) | ~4–7 × N + login | yes, several per watch |
| **Passive (now implemented)** | **1 `watches` + 1 `watchLastLocate`×N**, login amortized | **none** |

## Phase 1 — instrumentation (one live login's worth of traffic)

`src/xplora_soc_eval/probe.py` wraps every GraphQL operation (name, HTTP status,
latency, errors) and adds an aiohttp trace hook for raw HTTP status.

Observed signatures so far:
- **Auth failure** = HTTP `200` + GraphQL error `"Authentication failed."`
  (the server answers normally; it is *not* a transport-level block). This is
  our baseline for telling a bad-credential error apart from a future ban.
- **Ban signature** = still unknown, and we deliberately have not provoked one.
- The stock library retries a failed **login** up to 5× (`maxRetries=3` → loop
  `maxRetries+2`). That is dangerous on the login surface, so `_build_client`
  now sets `maxRetries=0` (2 attempts) and won't keep hammering on auth failure.

## Code changes made

- `probe.py` — new `xplora-probe` entry point: instrumented, passive,
  single-shot battery read. Closes its session even on error.
- `main.py` — `_read_all` rewritten to the **passive** path
  (`loadWatchLocation(with_ask=False)` + passive `onlineStatus`); no more active
  locates. `_build_client` accepts a session and caps login retries.

## ⚠️ Pivotal finding — the library's app key is rejected, not the account

The auth failure is **server-side rejection of the library itself**, not bad
user credentials. Evidence:

1. `xplora-diag` runs `checkEmailOrPhoneExist`, a pre-registration lookup that
   authenticates with **only** the library's hardcoded `Open API_KEY:API_SECRET`
   (`const.py`) — it never sends the user's email/password. It returns
   HTTP 200 with `errors: [{code: "E000004", message: "Authentication failed."}]`
   and `data.checkEmailOrPhoneExist = null`.
2. The user confirms **login works in the official Xplora app** with the same
   account — so the account/password are valid.

Therefore the rejected element is the library's shared bootstrap app key/secret
(value `fc45d503…` / `1e9b6fe0…`) and/or its plaintext `Open`/`H-BackDoor`
auth scheme. This is a *global* block (the key is shared by all pyxplora-api
users), which is almost certainly the real reason `Ludy87/xplora_watch` and
`pyxplora_api` were archived — "blocked by Xplora" was the app key being killed,
not (only) per-user IP bans.

**Consequence:** the slow-poll plan is moot until authentication is possible at
all. The project's blocker has moved from *"avoid the IP ban"* to *"obtain
working app credentials."* `pyxplora-api` as shipped cannot authenticate.

## ✅ RESOLVED — the V2 app key works (verified end-to-end)

Decompiled the current app `com.xplora.xplorav2` (jadx) and found it speaks the
**same GraphQL API** (`signInWithEmailOrPhone`, `askWatchLocate`,
`checkEmailOrPhoneExist`, `H-BackDoor-Authorization`) — only the host and key
changed:

- endpoint `https://api.prod.myxplora.com/api/` (from `MyApp`/`y00.d`)
- key/secret are returned by `NativeLib.getM1()/getM2()`, implemented in
  `lib/arm64-v8a/libandroidx.widget.so` (a deliberately misnamed native lib).
  They were stored as **plaintext** 32-hex strings — native hiding only defeats
  a *dex* grep, not `strings` on the `.so`. Working assignment:
  `API_KEY=98fa41bc50c84e2f833e3997aedfe1cf`,
  `API_SECRET=6d129c656ef64bf0becd3a370bbe068d`.

Verified against the user's real account:
- non-login `checkEmailOrPhoneExist` → `{"data":{"checkEmailOrPhoneExist":true}}`
  (no `E000004`).
- full login + passive battery read: `LOGIN OK`, 2 watches, real SoC
  (e.g. 84% / 100%), `batteryTm` ~16–34 min old (fine for hourly supervision).
- Footprint per poll confirmed: **1 login + 1 `WatchLastLocate` per watch, 0
  active locates** (3 GraphQL ops for 2 watches).

Wired into the code as `xplora_soc_eval/v2.py` (`apply()` patches the library's
host+key); `xplora-probe` / `xplora-diag` now target V2 automatically. The o2o
check confirmed o2o ships the same dead key, so V2 is the only live path.

**The blocker is cleared.** The original IP-ban concern (slow-poll plan, passive
reads, token reuse) is now the relevant work again — see Next.

## Options from here (historical — see RESOLVED above)

1. **Supply current app credentials.** The official app authenticates fine, so
   a valid `apiKey`/`apiSecret` exists. The library already accepts them:
   `init(forceLogin, signup, key=<apiKey>, sec=<apiSecret>)` →
   `login_a(key, sec)`. Obtaining them means capturing the app's own traffic
   (e.g. mitmproxy + an Android emulator/Frida) to read the current key, the
   auth header format, and User-Agent. Legality/ToS and effort caveats apply;
   this is reverse-engineering the app, and Xplora may rotate or pin the key.
2. ~~**Check for a newer key** in pyxplora_api git history / any active fork.~~
   Checked: the archived upstream's latest `main` `const.py` ships the
   *identical* key (`fc45d503…`). No newer key exists upstream — dead end.
3. **Reassess feasibility.** If the bootstrap key must be extracted from the app
   and can be rotated/pinned at will, an HA integration built on it is fragile
   by construction. This may be a go/no-go moment.

## Q: do we need an app key *in addition* to the login? — Yes

Auth is two independent layers:
- **App key/secret** authenticates the *client application* via
  `H-BackDoor-Authorization: Open <KEY>:<SECRET>`. It is required on **every**
  request, including the very first `signInWithEmailOrPhone` call (both libs
  hard-throw if the key is empty). There is no key-less login path.
- **User login** (email/phone + password) authenticates the *person* and
  returns an access token used as `Bearer <token>:<secret>` thereafter.

So the user login alone is not enough — without a valid app key you cannot even
reach the login. Notably the login response *returns* the app's own key in
`signInWithEmailOrPhone { app { apiKey apiSecret } }`, and the hardcoded key is
only a **bootstrap** to get that far. The JS lib's own comment says its key was
"taken from a public GraphQL response." Both unofficial libraries
(`pyxplora_api`, `xplora-api.js`) ship the **identical** revoked key.

## Q: can we request an *official* key? — No realistic path found

No public Xplora developer API or key-request program turned up. (Beware
`apidoc.myxplor.com` / "Xplor Enterprise APIs" — that's a *different* company,
Xplor childcare at `myxplor.com`, not Xplora watches at `myxplora.com`.) Xplora
runs a retail "Partner Program," not an API program. The only legitimate route
is emailing `support@xplora.com` to ask for API access — low odds for a hobby
integration, but it's the clean, ToS-safe option and worth one email.

## Capture plan (to get a working key) — see `capture/`

Can't run it in this headless sandbox (no adb/jadx/mitmproxy/emulator/JRE
installed, and the proprietary app isn't here), but the rig is written and ready
in [capture/CAPTURE.md](capture/CAPTURE.md) + `capture/mitm_extract.py`:
- **Path A (try first):** pull the APK from your device, `jadx`-decompile, grep
  for the 32-hex key near `H-BackDoor`. No device-proxying/TLS needed.
- **Path B:** `mitmdump -s capture/mitm_extract.py`, proxy the app (CA-trust +
  pinning bypass via emulator/`apk-mitm`), log in, read the key off the wire.
- Inject the captured key by overwriting the `API_KEY`/`API_SECRET` module
  globals before building the client, then `uv run xplora-diag` to confirm a
  clean `True/False` instead of `E000004`.

## Earlier blocker note (superseded)

Initially looked like a credential/identifier mismatch in `.env` (email vs
phone). The non-login diagnostic ruled that out — see above.

## Next

1. Decide whether to pursue option 1 (capture a working app key). If yes, that
   becomes a new workstream ahead of any polling work.
2. Only once authentication works do the passive read + WS3 token reuse +
   Phase 3 canary become relevant.

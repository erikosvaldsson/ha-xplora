# Capturing a working Xplora app key

Why: `pyxplora-api`'s hardcoded bootstrap key is rejected (`E000004`, see
[../FINDINGS.md](../FINDINGS.md)). The official app still works, so a valid key
exists — we read it off the app rather than guess it. Goal: obtain a current
`API_KEY` / `API_SECRET` (and User-Agent) and feed them back into the library.

> ⚠️ This reverse-engineers the official app for personal interoperability with
> your own account/watches. Check Xplora's ToS. Don't redistribute extracted
> keys — they're shared and Xplora revokes them (that's the whole problem).

## Background (what we're looking for)

Every request needs an **app key**; the user login is a *second*, separate
layer. Bootstrap auth is the header:

```
H-BackDoor-Authorization: Open <API_KEY>:<API_SECRET>
```

After login the server even returns the app's own key in
`signInWithEmailOrPhone { app { apiKey apiSecret packageName } }`. So either the
request header (bootstrap) or that response field gives us a usable key. The
addon `mitm_extract.py` grabs both.

## Which APK — important

The library identifies as **`Xplorao2o`** and targets package
**`com.xplora.xplorao2o`** (endpoint `api.myxplora.com`). That app was
**unpublished from Google Play 2025-06-02**; the current Play app is a different
package, **`com.xplora.xplorav2`**. The o2o sunset is a plausible cause of the
`E000004` rejection, so:
- Pull the **latest `com.xplora.xplorao2o`** build (in case its key rotated to a
  still-valid one before sunset) — cheap to test, but it may be the same dead
  key both libs already ship. Manage expectations.
- If o2o is fully dead, the live key belongs to `com.xplora.xplorav2`, which
  likely speaks a *different* API — a much larger porting effort than swapping a
  key. Decompile v2 to see if it still uses `api.myxplora.com` + the
  `H-BackDoor`/`Open` scheme before investing.

## Path A — static APK extraction (try first; no device proxying, no TLS)

The bootstrap key is a static credential, so it may be embedded in the APK.

1. Get the APK. Cleanest from your own device (if the o2o app is still
   installed): `adb shell pm list packages | grep -i xplora`, then
   `adb shell pm path com.xplora.xplorao2o` and `adb pull <path>`. Otherwise a
   reputable mirror that verifies signatures (APKMirror); avoid random APK sites
   (malware) and verify the signing cert.
2. Decompile: `jadx -d out app.apk` (or `apktool d app.apk`).
3. Grep for the key / scheme:
   ```
   grep -rniE "[0-9a-f]{32}|H-BackDoor|apiKey|apiSecret|myxplora" out/ | less
   ```
   A 32-hex string near `H-BackDoor`/`Open ` is the bootstrap key.
4. If it's obfuscated, in a native `.so`, or fetched at runtime → use Path B.

Tooling needed (none currently installed here): `jadx` or `apktool` (+ a JRE),
`adb`.

## Path B — dynamic MITM capture (if static fails)

1. Install the proxy:  `uv tool install mitmproxy`
2. Start it with the extractor:  `mitmdump -s capture/mitm_extract.py`
   (listens on :8080; this host's IP is the proxy address for the phone).
3. Trust mitmproxy's CA on the client. **Modern Android won't trust user CAs and
   the app may cert-pin**, so pick one:
   - Android emulator (`-writable-system`) or rooted device → install the CA as
     a *system* cert; or
   - Patch the APK to trust user CAs and strip pinning: `npx apk-mitm app.apk`,
     install the patched APK, then proxy it.
   - iOS: install + fully trust the profile; pinning still needs a jailbroken
     device or app patch.
4. Open the official Xplora app and log in. Watch `mitmdump`'s output — the
   addon prints `API_KEY` / `API_SECRET` / `User-Agent` from the bootstrap
   header and the `app.apiKey` from the login response.

## Feeding the captured key into pyxplora-api

The library compares `self._API_KEY == const.API_KEY` to decide whether to send
the `Open` bootstrap header, so passing `init(key=, sec=)` alone routes it down
the wrong (`Bearer`) branch. Instead overwrite the module globals **before**
constructing the client:

```python
import pyxplora_api.const as const
import pyxplora_api.handler_gql as hg
import pyxplora_api.gql_handler_async as ga

CAPTURED_KEY = "..."      # from the capture above
CAPTURED_SECRET = "..."
for m in (const, hg, ga):          # these imported the values by reference
    m.API_KEY = CAPTURED_KEY
    m.API_SECRET = CAPTURED_SECRET

# also match the app's User-Agent if it differs:
# const.DEFAULT_USER_AGENT = "<captured UA>"
```

Then run `uv run xplora-diag` — a clean `True/False` (instead of `E000004`)
means the captured key is accepted and we're unblocked. After that, `xplora-probe`
and the slow-poll plan become relevant again.

## Reality check

A captured key is the *same kind* of shared credential Xplora already revoked
once. If they rotate or cert-pin aggressively, any integration built on it
breaks again. Treat a successful capture as a spike that proves feasibility, not
a stable foundation — see the go/no-go note in FINDINGS.md.

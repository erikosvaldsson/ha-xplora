"""Point pyxplora-api at the Xplora **V2** app instead of the dead o2o app.

The library ships the o2o app key (`fc45d503…`), which Xplora revoked
(`E000004`). The current `com.xplora.xplorav2` app uses a different host and a
different key/secret, which DO still work (verified end-to-end: login + passive
battery read). This module swaps the library over to them.

Provenance (so it can be re-extracted when Xplora rotates it):
- endpoint: `MyApp`/`y00.d` in the decompiled v2 apk -> `api.prod.myxplora.com`,
  GraphQL path `/api/`.
- key/secret: `NativeLib.getM1()`/`getM2()`, i.e. two plaintext 32-hex strings
  in `lib/arm64-v8a/libandroidx.widget.so` (a deliberately misnamed lib).
  Auth header is `Open <KEY>:<SECRET>`; the working assignment is below.
See ../../FINDINGS.md and ../../capture/CAPTURE.md.

⚠️ This is a shared app key extracted from a public APK (same kind of credential
the libraries hardcode). Publishing it widely may hasten revocation; if it dies,
re-extract per CAPTURE.md.
"""

from __future__ import annotations

API_KEY = "98fa41bc50c84e2f833e3997aedfe1cf"     # NativeLib getM2
API_SECRET = "6d129c656ef64bf0becd3a370bbe068d"  # NativeLib getM1
ENDPOINT = "https://api.prod.myxplora.com/api/"


def apply() -> None:
    """Patch the library's module-level constants to the V2 app in-process."""
    import pyxplora_api.const as const
    import pyxplora_api.gql_handler as g
    import pyxplora_api.gql_handler_async as ga
    import pyxplora_api.handler_gql as hg

    for m in (const, hg, ga, g):
        if hasattr(m, "API_KEY"):
            m.API_KEY = API_KEY
        if hasattr(m, "API_SECRET"):
            m.API_SECRET = API_SECRET
    for m in (const, ga, g):
        if hasattr(m, "ENDPOINT"):
            m.ENDPOINT = ENDPOINT

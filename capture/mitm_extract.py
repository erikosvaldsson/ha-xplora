"""mitmproxy addon: extract the Xplora app's bootstrap key from live traffic.

This is how we get a *working* app key/secret to replace the dead hardcoded one
(`fc45d503…`), since the official app authenticates fine. It reads the key off
the app's own requests — we never guess or brute-force.

Run:
    uv tool install mitmproxy        # or: pipx install mitmproxy
    mitmdump -s capture/mitm_extract.py

Then route a phone/emulator running the official Xplora app through this proxy
with its CA cert trusted (see CAPTURE.md for the pinning/CA details), and open
the app / log in. The addon prints:
  - the bootstrap key from `H-BackDoor-Authorization: Open <KEY>:<SECRET>`
    (this is what you feed back into pyxplora-api), plus the User-Agent
  - any `app { apiKey, apiSecret, packageName }` returned in the login response
"""

from __future__ import annotations

import json

from mitmproxy import http

HOST = "api.myxplora.com"


class XploraKeyExtractor:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def request(self, flow: http.HTTPFlow) -> None:
        if HOST not in flow.request.pretty_host:
            return
        auth = flow.request.headers.get("H-BackDoor-Authorization", "")
        ua = flow.request.headers.get("User-Agent", "")
        if auth.startswith("Open ") and auth not in self._seen:
            self._seen.add(auth)
            key, _, secret = auth[len("Open "):].partition(":")
            print("\n=== Xplora BOOTSTRAP app key (feed this to pyxplora-api) ===")
            print(f"  API_KEY    = {key!r}")
            print(f"  API_SECRET = {secret!r}")
            print(f"  User-Agent = {ua!r}")

    def response(self, flow: http.HTTPFlow) -> None:
        if HOST not in flow.request.pretty_host:
            return
        try:
            data = json.loads(flow.response.get_text() or "{}")
        except (ValueError, TypeError):
            return
        d = data.get("data") or {}
        signin = d.get("signInWithEmailOrPhone") or d.get("issueToken") or {}
        app = (signin or {}).get("app") or {}
        if app.get("apiKey"):
            print("\n=== app.apiKey/apiSecret returned AFTER login ===")
            print(f"  apiKey      = {app.get('apiKey')!r}")
            print(f"  apiSecret   = {app.get('apiSecret')!r}")
            print(f"  packageName = {app.get('packageName')!r}")


addons = [XploraKeyExtractor()]

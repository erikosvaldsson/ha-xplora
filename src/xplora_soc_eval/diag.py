"""Discriminator: is the auth failure *credentials* or a *remote/library block*?

`checkEmailOrPhoneExist` is a lookup, NOT a sign-in — it does not touch
loginFailCount — but it travels with the same hardcoded app key, the library's
User-Agent, and your IP, using the pre-login "Open" authorization. So:

  - a clean boolean result  -> the app key + library fingerprint + your IP are
    accepted by Xplora right now; the login failure is therefore a credential
    problem. The boolean also says whether that identifier is even registered.
  - transport error / 403 / empty body -> evidence the library itself (key or
    fingerprint) or your IP is being blocked.

Single run, 1-2 lookup requests, no sign-in. Run: uv run xplora-diag
"""

from __future__ import annotations

import asyncio

import aiohttp
from pyxplora_api.gql_handler_async import GQLHandler
from pyxplora_api.status import UserContactType

from .main import _load_credentials


async def _run() -> None:
    from . import v2

    v2.apply()  # target the V2 app (the o2o app key is dead)
    c = _load_credentials()

    trace = aiohttp.TraceConfig()

    async def on_end(session, ctx, params):  # noqa: ANN001
        print(f"  HTTP {params.response.status} {params.method} {params.url.host}")

    trace.on_request_end.append(on_end)
    session = aiohttp.ClientSession(trace_configs=[trace])

    handler = GQLHandler(
        c["countrycode"], c["phoneNumber"], c["password"],
        c["userLang"], c["timeZone"], c["email"] or None, True, session,
    )

    print("Lookup (NOT a login) — checks app-key/library acceptance + identifier:")
    try:
        if c["email"]:
            r = await handler.checkEmailOrPhoneExist_a(UserContactType.EMAIL, email=c["email"])
            print(f"  email registered? -> {r}")
        if c["phoneNumber"]:
            r = await handler.checkEmailOrPhoneExist_a(
                UserContactType.PHONE, countryCode=c["countrycode"], phoneNumber=c["phoneNumber"]
            )
            print(f"  phone registered? -> {r}")
    finally:
        await session.close()

    print(
        "\nReading it: a True/False above means the library is NOT blocked "
        "(key+UA+IP accepted) -> login failure is credentials. A registered "
        "identifier that still fails login points at the password; an "
        "unregistered one means use the other identifier."
    )


def main() -> None:
    import argparse

    argparse.ArgumentParser(
        description="Non-login diagnostic: credentials vs remote/library block."
    ).parse_args()
    asyncio.run(_run())


if __name__ == "__main__":
    main()

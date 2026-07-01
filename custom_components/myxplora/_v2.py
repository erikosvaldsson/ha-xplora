"""Point pyxplora-api at the Xplora **V2** app (the bundled o2o key is dead).

pyxplora-api ships the retired o2o app key, which Xplora rejects (`E000004`).
The current `com.xplora.xplorav2` app speaks the same GraphQL API on a different
host with a different key/secret, which still work. This patches the library's
module-level constants in-process before any client is built.

If Xplora rotates the key, it can be re-extracted from the current
`com.xplora.xplorav2` Android app (the 32-hex `API_KEY`/`API_SECRET` used in the
`H-BackDoor-Authorization` header) and updated below.
"""

from __future__ import annotations

API_KEY = "98fa41bc50c84e2f833e3997aedfe1cf"
API_SECRET = "6d129c656ef64bf0becd3a370bbe068d"
ENDPOINT = "https://api.prod.myxplora.com/api/"


def apply() -> None:
    """Swap the library over to the V2 app. Idempotent."""
    import pyxplora_api.const as const
    import pyxplora_api.gql_handler as g
    import pyxplora_api.gql_handler_async as ga
    import pyxplora_api.handler_gql as hg

    for module in (const, hg, ga, g):
        if hasattr(module, "API_KEY"):
            module.API_KEY = API_KEY
        if hasattr(module, "API_SECRET"):
            module.API_SECRET = API_SECRET
    for module in (const, ga, g):
        if hasattr(module, "ENDPOINT"):
            module.ENDPOINT = ENDPOINT

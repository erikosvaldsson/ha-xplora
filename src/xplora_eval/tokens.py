"""Persist/restore the V2 access token so restarts don't re-login (WS3).

The login response carries a long-lived token (observed `expireDate` ~35 days
out) *and* the watch list, so once saved we can resume passive polling across
restarts with zero logins until it actually expires. This matters because the
login surface is the most monitored one (`loginFailCount`, brute-force checks),
so fewer logins = lower ban risk.

Self-healing: `restore()` only primes the client; the caller validates with its
first real read and logs in fresh if the token is rejected. The cache holds an
access token (a credential) so the file is written 0600 and must stay gitignored.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from pyxplora_api.pyxplora_api_async import PyXploraApi

DEFAULT_PATH = Path(".xplora_token.json")


def save(client: PyXploraApi, path: Path = DEFAULT_PATH) -> None:
    tok = getattr(client, "_issueToken", None)
    if not tok:
        return
    path.write_text(
        json.dumps(
            {
                "issueToken": tok,
                "refresh_token": getattr(client, "_refresh_token", None),
                "saved_at": int(time.time()),
            }
        )
    )
    path.chmod(0o600)


def expire_epoch(issue_token: dict) -> int:
    """`expireDate` is observed in epoch seconds."""
    try:
        return int(issue_token.get("expireDate") or 0)
    except (TypeError, ValueError):
        return 0


def restore(client: PyXploraApi, path: Path = DEFAULT_PATH, margin_s: int = 3600) -> bool:
    """Prime `client` from a saved token. Returns True if a still-valid token
    was loaded (caller should skip login but still validate with a real read)."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError):
        return False
    tok = data.get("issueToken") or {}
    user = tok.get("user")
    if not user or expire_epoch(tok) - margin_s <= int(time.time()):
        return False  # missing, expired, or about to expire

    h = client._gql_handler
    h.issueToken = tok
    h.accessToken = tok.get("token")
    h.sessionId = tok.get("id")
    h.userId = user.get("id")
    h.refreshToken = data.get("refresh_token")
    client._issueToken = tok
    client._refresh_token = data.get("refresh_token")
    client.dtIssueToken = int(time.time())
    client.watchs = user.get("children", [])
    client.user = user
    return True

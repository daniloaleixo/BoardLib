"""Read-only client for the post-Aurora Kilter stack (Keycloak + PowerSync).

Kilter split from Aurora in March 2026; kilterboardapp.com is gone. The new app
authenticates against Keycloak and syncs rows over PowerSync. This pulls the
sync stream once and reports what came back -- nothing is ever uploaded.
"""
import contextlib
import json
import os
import sys
import uuid

import requests

AUTH_URL = "https://idp.kiltergrips.com/realms/kilter/protocol/openid-connect/token"
SYNC_URL = "https://sync1.kiltergrips.com/sync/stream"
CLIENT_ID = "kilter"
SCOPE = "openid offline_access"


def login(username, password):
    r = requests.post(
        AUTH_URL,
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": password,
            "scope": SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"login failed: HTTP {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def stream(token, timeout=180):
    """Pull one full sync checkpoint. Returns {table_name: [row, ...]}."""
    body = {
        "buckets": [],
        "include_checksum": True,
        "raw_data": True,
        "client_id": str(uuid.uuid4()),
        "parameters": {},
    }
    tables, lines, done = {}, 0, False
    with requests.post(
        SYNC_URL,
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        stream=True,
        timeout=timeout,
    ) as r:
        if r.status_code != 200:
            raise SystemExit(f"sync failed: HTTP {r.status_code} {r.text[:300]}")
        for raw in r.iter_lines(decode_unicode=True):
            if not raw:
                continue
            lines += 1
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "data" in msg:
                for op in msg["data"].get("data", []):
                    t = op.get("object_type") or "(unknown)"
                    d = op.get("data")
                    if isinstance(d, str):
                        with contextlib.suppress(json.JSONDecodeError):
                            d = json.loads(d)
                    tables.setdefault(t, []).append(
                        {"op": op.get("op"), "id": op.get("object_id"), "row": d}
                    )
            elif "checkpoint_complete" in msg:
                done = True
                break
    print(f"stream lines: {lines}  checkpoint_complete: {done}", file=sys.stderr)
    return tables


def main():
    user = os.environ.get("KILTER_USERNAME")
    pw = os.environ.get("KILTER_PASSWORD")
    if not user or not pw:
        raise SystemExit("set KILTER_USERNAME and KILTER_PASSWORD")
    tables = stream(login(user, pw))
    if not tables:
        print("No rows returned.")
        return
    print(f"\n{'table':38} {'rows':>7}")
    print("-" * 48)
    for t, rows in sorted(tables.items(), key=lambda kv: -len(kv[1])):
        print(f"{t:38} {len(rows):>7}")
    out = os.environ.get("KILTER_DUMP")
    if out:
        with open(out, "w") as f:
            json.dump(tables, f, indent=1, default=str)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()

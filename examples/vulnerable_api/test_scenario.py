"""
Automated test scenario for the vulnerable API.

Exercises all endpoints through a proxy to generate a comprehensive
idotaku report covering: IDOR detection, risk scoring (CRITICAL/HIGH/
MEDIUM/LOW), parameter chains, and cross-user access patterns.

Usage:
    # Terminal 1: Start the vulnerable API
    python server.py

    # Terminal 2: Start idotaku proxy
    idotaku --port 8080 -o test_report.json -c idotaku.yaml

    # Terminal 3: Run this script
    python test_scenario.py
"""

from __future__ import annotations

import argparse
import sys

import requests

# Known seed-data IDs (from server.py) that will NOT appear in any
# response unless we explicitly call GET endpoints that echo them.
# Using them only via "non-echoing" endpoints makes them IDOR candidates.
CHARLIE_USER_ID = 1003
BOB_PROFILE_UUID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
CHARLIE_PROFILE_UUID = "c3d4e5f6-a7b8-9012-cdef-234567890123"
BOB_DOC_TOKEN = "doc_YzAbCdEfGhIjKlMnOpQrStUv"


def run_scenario(api_base: str, proxy_url: str | None) -> None:
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    def _get(path: str, **kw):  # noqa: ANN003
        return requests.get(f"{api_base}{path}", proxies=proxies, **kw)

    def _post(path: str, **kw):  # noqa: ANN003
        return requests.post(f"{api_base}{path}", proxies=proxies, **kw)

    def _put(path: str, **kw):  # noqa: ANN003
        return requests.put(f"{api_base}{path}", proxies=proxies, **kw)

    def _patch(path: str, **kw):  # noqa: ANN003
        return requests.patch(f"{api_base}{path}", proxies=proxies, **kw)

    def _delete(path: str, **kw):  # noqa: ANN003
        return requests.delete(f"{api_base}{path}", proxies=proxies, **kw)

    # ------------------------------------------------------------------
    # Phase 1: Alice login  (producer: user_id=1001, access_token)
    # ------------------------------------------------------------------
    print("[Phase 1] Alice login")
    r = _post("/api/auth/login", json={"username": "alice", "password": "alice123"})
    r.raise_for_status()
    alice_token = r.json()["access_token"]
    alice_h = {"Authorization": f"Bearer {alice_token}"}

    # ------------------------------------------------------------------
    # Phase 2: Alice accesses her own data  (sets origin for 1001)
    # ------------------------------------------------------------------
    print("[Phase 2] Alice accesses own data")
    _get("/api/users/1001", headers=alice_h)
    _get("/api/me", headers=alice_h)

    # ------------------------------------------------------------------
    # Phase 3: CRITICAL IDOR  (ID 1003, admin endpoints, no echo)
    #   DELETE(30) + url_path(20) + numeric(15) + usage=3(15) + endpoints=3(9) = 89
    # ------------------------------------------------------------------
    print("[Phase 3] CRITICAL IDOR - Alice attacks Charlie (1003) via admin endpoints")
    _delete(f"/api/admin/users/{CHARLIE_USER_ID}", headers=alice_h)
    _put(
        f"/api/admin/users/{CHARLIE_USER_ID}/role",
        headers=alice_h,
        json={"role": "suspended"},
    )
    _post(
        "/api/admin/action",
        headers=alice_h,
        json={"target_user_id": CHARLIE_USER_ID, "action": "suspend"},
    )

    # ------------------------------------------------------------------
    # Phase 4: HIGH IDOR  (ID 1002, PUT /api/users, no echo)
    #   PUT(25) + url_path(20) + numeric(15) + usage=1(5) = 65
    # ------------------------------------------------------------------
    print("[Phase 4] HIGH IDOR - Alice updates Bob's user via PUT")
    _put(
        "/api/users/1002",
        headers=alice_h,
        json={"email": "hacked@evil.com"},
    )

    # ------------------------------------------------------------------
    # Phase 5: MEDIUM IDOR  (UUID in body, profiles/update, no echo)
    #   POST(15) + body(10) + uuid(5) + usage=2(10) + endpoints=2(6) = 46
    # ------------------------------------------------------------------
    print("[Phase 5] MEDIUM IDOR - Alice accesses Bob's profile via UUID in body")
    _post(
        "/api/profiles/view",
        headers=alice_h,
        json={"profile_id": BOB_PROFILE_UUID},
    )
    _post(
        "/api/profiles/update",
        headers=alice_h,
        json={"profile_id": BOB_PROFILE_UUID, "bio": "hacked by Alice"},
    )

    # ------------------------------------------------------------------
    # Phase 6: LOW IDOR  (token via header, no echo)
    #   GET(5) + header(5) + token(3) + usage=1(5) = 18
    # ------------------------------------------------------------------
    print("[Phase 6] LOW IDOR - Alice accesses Bob's document via header token")
    _get(
        "/api/documents/by-header",
        headers={**alice_h, "X-Document-Token": BOB_DOC_TOKEN},
    )

    # ------------------------------------------------------------------
    # Phase 7: Parameter chain  (create -> get -> patch -> delete)
    # ------------------------------------------------------------------
    print("[Phase 7] Parameter chain - Order CRUD")
    r = _post(
        "/api/orders",
        headers=alice_h,
        json={"user_id": 1001, "items": [{"product_id": 5001, "quantity": 2}]},
    )
    r.raise_for_status()
    new_order_id = r.json()["order_id"]

    _get(f"/api/orders/{new_order_id}", headers=alice_h)
    _patch(
        f"/api/orders/{new_order_id}",
        headers=alice_h,
        json={"status": "processing"},
    )
    _delete(f"/api/orders/{new_order_id}", headers=alice_h)

    # ------------------------------------------------------------------
    # Phase 8: Bob login  (different auth context)
    # ------------------------------------------------------------------
    print("[Phase 8] Bob login")
    r = _post("/api/auth/login", json={"username": "bob", "password": "bob123"})
    r.raise_for_status()
    bob_token = r.json()["access_token"]
    bob_h = {"Authorization": f"Bearer {bob_token}"}

    # ------------------------------------------------------------------
    # Phase 9: Cross-user detection
    #   Bob accesses Alice's user (same ID 1001, different auth hash)
    # ------------------------------------------------------------------
    print("[Phase 9] Cross-user detection - Bob accesses Alice's data")
    _get("/api/users/1001", headers=bob_h)
    _get(f"/api/orders?user_id=1001", headers=bob_h)

    # ------------------------------------------------------------------
    # Phase 10: Alice's profile listing  (producer for her UUID)
    # ------------------------------------------------------------------
    print("[Phase 10] Alice lists her own profiles (producer)")
    _get("/api/profiles", headers=alice_h)

    # ------------------------------------------------------------------
    # Phase 11: Alice's document listing  (producer for her doc_token)
    # ------------------------------------------------------------------
    print("[Phase 11] Alice lists her own documents (producer)")
    _get("/api/documents", headers=alice_h)

    print()
    print("=" * 60)
    print("Test scenario complete!")
    print("Analyze the report with:")
    print("  idotaku report <report_file>")
    print("  idotaku score <report_file>")
    print("  idotaku chain <report_file>")
    print("  idotaku auth <report_file>")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IDOR test scenario against vulnerable API")
    parser.add_argument("--api", default="http://localhost:3000", help="API base URL")
    parser.add_argument("--proxy", default="http://localhost:8080", help="Proxy URL (set to 'none' to skip)")
    args = parser.parse_args()

    proxy = None if args.proxy.lower() == "none" else args.proxy

    # Quick health check
    try:
        r = requests.get(f"{args.api}/api/health", timeout=3)
        r.raise_for_status()
    except requests.ConnectionError:
        print(f"ERROR: Cannot connect to API at {args.api}", file=sys.stderr)
        print("Start the server first: python server.py", file=sys.stderr)
        sys.exit(1)

    run_scenario(args.api, proxy)


if __name__ == "__main__":
    main()

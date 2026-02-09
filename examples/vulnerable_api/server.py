"""
Vulnerable API server for testing idotaku IDOR detection.

This server intentionally contains IDOR vulnerabilities for educational
and testing purposes. DO NOT deploy this in production.

Usage:
    pip install fastapi uvicorn
    python server.py                # Default: http://127.0.0.1:3000
    python server.py --port 4000    # Custom port
"""

from __future__ import annotations

import argparse
import os
import secrets
import string
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    email: str


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None


class ProfileViewRequest(BaseModel):
    profile_id: str


class ProfileUpdateRequest(BaseModel):
    profile_id: str
    bio: str | None = None
    avatar_url: str | None = None


class OrderCreate(BaseModel):
    user_id: int
    items: list[dict]


class OrderUpdate(BaseModel):
    status: str | None = None
    items: list[dict] | None = None


class AdminAction(BaseModel):
    target_user_id: int
    action: str  # "suspend", "delete", "promote"


class RoleUpdate(BaseModel):
    role: str


# ---------------------------------------------------------------------------
# In-memory data store (seeded on startup)
# ---------------------------------------------------------------------------

USERS: dict[int, dict] = {}
PROFILES: dict[str, dict] = {}  # key: UUID string
ORDERS: dict[int, dict] = {}
DOCUMENTS: dict[str, dict] = {}  # key: token string
AUTH_TOKENS: dict[str, int] = {}  # token -> user_id

_next_user_id = 1004
_next_order_id = 9003


def _generate_token(prefix: str = "tok") -> str:
    """Generate a 30+ char alphanumeric token that matches idotaku's token pattern."""
    chars = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(28))
    return f"{prefix}_{random_part}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_data() -> None:
    """Populate initial data."""
    global _next_user_id, _next_order_id

    # Users
    USERS.update(
        {
            1001: {
                "id": 1001,
                "username": "alice",
                "email": "alice@example.com",
                "password": "alice123",
                "role": "user",
                "created_at": _now(),
            },
            1002: {
                "id": 1002,
                "username": "bob",
                "email": "bob@example.com",
                "password": "bob123",
                "role": "user",
                "created_at": _now(),
            },
            1003: {
                "id": 1003,
                "username": "charlie",
                "email": "charlie@example.com",
                "password": "charlie123",
                "role": "admin",
                "created_at": _now(),
            },
        }
    )

    # Profiles (UUIDs)
    PROFILES.update(
        {
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
                "profile_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "user_id": 1001,
                "bio": "Hi, I'm Alice!",
                "avatar_url": "https://example.com/avatars/alice.png",
            },
            "b2c3d4e5-f6a7-8901-bcde-f12345678901": {
                "profile_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "user_id": 1002,
                "bio": "Bob here.",
                "avatar_url": "https://example.com/avatars/bob.png",
            },
            "c3d4e5f6-a7b8-9012-cdef-234567890123": {
                "profile_id": "c3d4e5f6-a7b8-9012-cdef-234567890123",
                "user_id": 1003,
                "bio": "Charlie admin.",
                "avatar_url": "https://example.com/avatars/charlie.png",
            },
        }
    )

    # Orders
    ORDERS.update(
        {
            9001: {
                "order_id": 9001,
                "user_id": 1001,
                "items": [{"product_id": 5001, "quantity": 2}],
                "status": "pending",
                "total": 99.99,
                "created_at": _now(),
            },
            9002: {
                "order_id": 9002,
                "user_id": 1002,
                "items": [{"product_id": 5002, "quantity": 1}],
                "status": "shipped",
                "total": 149.99,
                "created_at": _now(),
            },
        }
    )

    # Documents (token-based access, 24+ chars)
    DOCUMENTS.update(
        {
            "doc_AbCdEfGhIjKlMnOpQrStUvWx": {
                "doc_token": "doc_AbCdEfGhIjKlMnOpQrStUvWx",
                "title": "Alice's Secret Report",
                "content": "Confidential data belonging to Alice.",
                "owner_id": 1001,
            },
            "doc_YzAbCdEfGhIjKlMnOpQrStUv": {
                "doc_token": "doc_YzAbCdEfGhIjKlMnOpQrStUv",
                "title": "Bob's Financial Data",
                "content": "Confidential data belonging to Bob.",
                "owner_id": 1002,
            },
        }
    )

    _next_user_id = 1004
    _next_order_id = 9003


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    seed_data()
    yield


app = FastAPI(
    title="Vulnerable API (idotaku testing)",
    description="Intentionally vulnerable API for IDOR detection testing. DO NOT use in production.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """Resolve current user from Bearer token or session cookie."""
    if credentials and credentials.credentials in AUTH_TOKENS:
        uid = AUTH_TOKENS[credentials.credentials]
        return USERS.get(uid)
    session = request.cookies.get("session")
    if session and session in AUTH_TOKENS:
        uid = AUTH_TOKENS[session]
        return USERS.get(uid)
    return None


def require_auth(user: dict | None = Depends(get_current_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@app.post("/api/auth/login")
def login(body: LoginRequest):
    """Login and receive a bearer token.

    Producer: emits user_id (numeric) and access_token (token pattern) in response.
    """
    for user in USERS.values():
        if user["username"] == body.username and user["password"] == body.password:
            token = _generate_token("tok")
            AUTH_TOKENS[token] = user["id"]
            return {
                "access_token": token,
                "user_id": user["id"],
                "token_type": "bearer",
            }
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ---------------------------------------------------------------------------
# User endpoints  (numeric ID in url_path)
# ---------------------------------------------------------------------------


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate):
    """Create a new user. Producer: returns the new user_id in response."""
    global _next_user_id
    uid = _next_user_id
    _next_user_id += 1
    USERS[uid] = {
        "id": uid,
        "username": body.username,
        "email": body.email,
        "password": "default",
        "role": "user",
        "created_at": _now(),
    }
    return {"id": uid, "username": body.username, "email": body.email}


@app.get("/api/users/{user_id}")
def get_user(user_id: int, _user: dict = Depends(require_auth)):
    """Get user by ID. Returns user data (sets origin for this ID).

    VULN: No ownership check -- any authenticated user can read any user.
    """
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    u = USERS[user_id]
    return {"id": u["id"], "username": u["username"], "email": u["email"]}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, _user: dict = Depends(require_auth)):
    """Update user. Response does NOT echo user_id -> IDOR candidate.

    VULN: No ownership check.
    """
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    if body.username is not None:
        USERS[user_id]["username"] = body.username
    if body.email is not None:
        USERS[user_id]["email"] = body.email
    return {"status": "updated"}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, _user: dict = Depends(require_auth)):
    """Delete user. Response does NOT echo user_id -> IDOR candidate.

    VULN: No ownership check.
    """
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    del USERS[user_id]
    return {"status": "deleted"}


@app.get("/api/me")
def get_me(user: dict = Depends(require_auth)):
    """Return current user info. Producer: emits user_id in response."""
    return {"id": user["id"], "username": user["username"], "email": user["email"]}


# ---------------------------------------------------------------------------
# Profile endpoints  (UUID in request body)
# ---------------------------------------------------------------------------


@app.get("/api/profiles")
def list_profiles(user: dict = Depends(require_auth)):
    """List current user's profiles. Producer: emits profile_id (UUID) in response."""
    result = []
    for p in PROFILES.values():
        if p["user_id"] == user["id"]:
            result.append(p)
    return result


@app.post("/api/profiles/view")
def view_profile(body: ProfileViewRequest, _user: dict = Depends(require_auth)):
    """View a profile by UUID in request body.

    Response intentionally omits profile_id -> IDOR candidate.
    VULN: No ownership check.
    """
    if body.profile_id not in PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    p = PROFILES[body.profile_id]
    return {"bio": p["bio"], "avatar_url": p["avatar_url"], "user_id": p["user_id"]}


@app.post("/api/profiles/update")
def update_profile(body: ProfileUpdateRequest, _user: dict = Depends(require_auth)):
    """Update a profile by UUID in request body.

    Response does NOT echo profile_id -> IDOR candidate.
    VULN: No ownership check.
    """
    if body.profile_id not in PROFILES:
        raise HTTPException(status_code=404, detail="Profile not found")
    if body.bio is not None:
        PROFILES[body.profile_id]["bio"] = body.bio
    if body.avatar_url is not None:
        PROFILES[body.profile_id]["avatar_url"] = body.avatar_url
    return {"status": "updated"}


# ---------------------------------------------------------------------------
# Order endpoints  (numeric ID, full CRUD -> parameter chain)
# ---------------------------------------------------------------------------


@app.post("/api/orders", status_code=201)
def create_order(body: OrderCreate, _user: dict = Depends(require_auth)):
    """Create an order. Producer: returns order_id and user_id.

    Chain root: POST /api/orders -> produces order_id.
    """
    global _next_order_id
    oid = _next_order_id
    _next_order_id += 1
    total = sum(item.get("quantity", 1) * 49.99 for item in body.items)
    ORDERS[oid] = {
        "order_id": oid,
        "user_id": body.user_id,
        "items": body.items,
        "status": "pending",
        "total": round(total, 2),
        "created_at": _now(),
    }
    return ORDERS[oid]


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, _user: dict = Depends(require_auth)):
    """Get order by ID. Returns full order data (sets origin).

    VULN: No ownership check.
    """
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")
    return ORDERS[order_id]


@app.get("/api/orders")
def list_orders(user_id: int | None = None, _user: dict = Depends(require_auth)):
    """List orders, optionally filtered by user_id query param.

    VULN: No ownership check -- can list any user's orders.
    """
    result = list(ORDERS.values())
    if user_id is not None:
        result = [o for o in result if o["user_id"] == user_id]
    return result


@app.patch("/api/orders/{order_id}")
def update_order(order_id: int, body: OrderUpdate, _user: dict = Depends(require_auth)):
    """Update order. Response does NOT echo order_id -> IDOR candidate.

    VULN: No ownership check.
    """
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")
    if body.status is not None:
        ORDERS[order_id]["status"] = body.status
    if body.items is not None:
        ORDERS[order_id]["items"] = body.items
    return {"status": "updated"}


@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int, _user: dict = Depends(require_auth)):
    """Delete order. Response does NOT echo order_id -> IDOR candidate.

    VULN: No ownership check.
    """
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="Order not found")
    del ORDERS[order_id]
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Document endpoints  (token-based ID)
# ---------------------------------------------------------------------------


@app.get("/api/documents")
def list_documents(user: dict = Depends(require_auth)):
    """List current user's documents. Producer: emits doc_token in response."""
    return [d for d in DOCUMENTS.values() if d["owner_id"] == user["id"]]


@app.get("/api/documents/by-header")
def get_document_by_header(request: Request, _user: dict = Depends(require_auth)):
    """Access document via X-Document-Token header.

    Response intentionally omits doc_token -> IDOR candidate (LOW risk).
    VULN: No ownership check.
    """
    token = request.headers.get("x-document-token")
    if not token or token not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")
    d = DOCUMENTS[token]
    return {"title": d["title"], "content": d["content"]}


@app.get("/api/documents/{doc_token}")
def get_document(doc_token: str, _user: dict = Depends(require_auth)):
    """Get document by token in URL path. Returns full data (sets origin).

    VULN: No ownership check.
    """
    if doc_token not in DOCUMENTS:
        raise HTTPException(status_code=404, detail="Document not found")
    return DOCUMENTS[doc_token]


# ---------------------------------------------------------------------------
# Admin endpoints  (high-severity IDOR targets)
# ---------------------------------------------------------------------------


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, _user: dict = Depends(require_auth)):
    """Admin delete user. Response does NOT echo user_id -> IDOR candidate.

    VULN: No role check -- any authenticated user can call this.
    """
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    del USERS[user_id]
    return {"status": "deleted"}


@app.put("/api/admin/users/{user_id}/role")
def admin_change_role(user_id: int, body: RoleUpdate, _user: dict = Depends(require_auth)):
    """Change user role. Response does NOT echo user_id -> IDOR candidate.

    VULN: No role check.
    """
    if user_id not in USERS:
        raise HTTPException(status_code=404, detail="User not found")
    USERS[user_id]["role"] = body.role
    return {"status": "updated"}


@app.post("/api/admin/action")
def admin_action(body: AdminAction, _user: dict = Depends(require_auth)):
    """Perform admin action on target user.

    target_user_id in request body, NOT echoed in response -> IDOR candidate.
    VULN: No role check.
    """
    if body.target_user_id not in USERS:
        raise HTTPException(status_code=404, detail="Target user not found")
    if body.action == "suspend":
        USERS[body.target_user_id]["role"] = "suspended"
    elif body.action == "promote":
        USERS[body.target_user_id]["role"] = "admin"
    return {"status": "completed", "action": body.action}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": _now()}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vulnerable API for idotaku testing")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "3000")))
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)

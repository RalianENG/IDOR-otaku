# Vulnerable API for idotaku Testing

> **WARNING**: This server intentionally contains IDOR vulnerabilities.
> For educational and testing purposes only. DO NOT deploy in production.

## Overview

A FastAPI server designed to exercise every detection capability of idotaku:

- **IDOR detection** (IDs in requests that never appear in responses)
- **Risk scoring** at all 4 levels (CRITICAL / HIGH / MEDIUM / LOW)
- **Parameter chain analysis** (producer → consumer endpoint flows)
- **Cross-user access detection** (same resource, different auth tokens)
- **Multiple ID types**: numeric, UUID, token

## Prerequisites

```bash
pip install -r requirements.txt
```

## Quick Start

### One-Command Demo

```bash
# Linux/macOS
bash run_demo.sh

# Windows / cross-platform
python run_demo.py
```

This automatically starts the server, runs the attack scenario through a proxy,
and generates all analysis reports including interactive HTML exports.

### Manual Setup (3 Terminals)

```bash
# Terminal 1: Start vulnerable API
python server.py

# Terminal 2: Start idotaku proxy (config filters to localhost only)
idotaku --port 8080 -o test_report.json -c idotaku.yaml

# Terminal 3: Run automated test scenario
python test_scenario.py
```

Then analyze the results:

```bash
idotaku report test_report.json
idotaku score test_report.json
idotaku chain test_report.json
idotaku auth test_report.json
```

## Endpoints

### Auth

| Method | Path              | Description                          |
|--------|-------------------|--------------------------------------|
| POST   | `/api/auth/login` | Login, returns `user_id` + `access_token` |

### Users (numeric ID in URL path)

| Method | Path                  | Echoes ID? | IDOR? |
|--------|-----------------------|------------|-------|
| POST   | `/api/users`          | Yes        | -     |
| GET    | `/api/users/{id}`     | Yes        | -     |
| PUT    | `/api/users/{id}`     | No         | Yes   |
| DELETE | `/api/users/{id}`     | No         | Yes   |
| GET    | `/api/me`             | Yes        | -     |

### Profiles (UUID in request body)

| Method | Path                    | Echoes ID? | IDOR? |
|--------|-------------------------|------------|-------|
| GET    | `/api/profiles`         | Yes        | -     |
| POST   | `/api/profiles/view`    | No         | Yes   |
| POST   | `/api/profiles/update`  | No         | Yes   |

### Orders (numeric ID, full CRUD chain)

| Method | Path                          | Echoes ID? | IDOR? |
|--------|-------------------------------|------------|-------|
| POST   | `/api/orders`                 | Yes        | -     |
| GET    | `/api/orders/{id}`            | Yes        | -     |
| GET    | `/api/orders?user_id={id}`    | Yes        | -     |
| PATCH  | `/api/orders/{id}`            | No         | Yes   |
| DELETE | `/api/orders/{id}`            | No         | Yes   |

### Documents (token-based ID)

| Method | Path                       | Echoes ID? | IDOR? |
|--------|----------------------------|------------|-------|
| GET    | `/api/documents`           | Yes        | -     |
| GET    | `/api/documents/{token}`   | Yes        | -     |
| GET    | `/api/documents/by-header` | No         | Yes   |

### Admin (high-severity targets)

| Method | Path                          | Echoes ID? | IDOR? |
|--------|-------------------------------|------------|-------|
| DELETE | `/api/admin/users/{id}`       | No         | Yes   |
| PUT    | `/api/admin/users/{id}/role`  | No         | Yes   |
| POST   | `/api/admin/action`           | No         | Yes   |

## Expected Risk Scores

The test scenario is designed to trigger each risk level:

| Level    | Score | ID         | How                                                    |
|----------|-------|------------|--------------------------------------------------------|
| CRITICAL | 89    | `1003`     | DELETE + PUT + POST across 3 admin endpoints (numeric, url_path) |
| HIGH     | 65    | `1002`     | PUT /api/users/1002 (numeric, url_path)                |
| MEDIUM   | 46    | Bob's UUID | POST profiles/view + profiles/update (uuid, body)      |
| LOW      | 18    | Bob's doc  | GET documents/by-header (token, header)                |

## Seed Data

| Resource  | ID                                     | Owner   |
|-----------|----------------------------------------|---------|
| User 1001 | `1001`                                 | alice   |
| User 1002 | `1002`                                 | bob     |
| User 1003 | `1003`                                 | charlie |
| Profile   | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` | alice   |
| Profile   | `b2c3d4e5-f6a7-8901-bcde-f12345678901` | bob     |
| Profile   | `c3d4e5f6-a7b8-9012-cdef-234567890123` | charlie |
| Order     | `9001`                                 | alice   |
| Order     | `9002`                                 | bob     |
| Document  | `doc_AbCdEfGhIjKlMnOpQrStUvWx`        | alice   |
| Document  | `doc_YzAbCdEfGhIjKlMnOpQrStUv`        | bob     |

Login credentials: `alice/alice123`, `bob/bob123`, `charlie/charlie123`

## How IDOR Detection Works

idotaku flags an ID as a **potential IDOR** when:
1. The ID appears in HTTP **requests** (URL path, query, body, or header)
2. The ID **never** appears in any HTTP **response** body or header

This is why some endpoints intentionally omit the target ID from their
response (`{"status": "updated"}` instead of `{"id": 1002, "status": "updated"}`).

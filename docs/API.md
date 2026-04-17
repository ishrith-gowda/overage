# Overage API

Reference for **Story 7** (five-minute onboarding) and integration. For product rules, see [PRD.md](../PRD.md).

## Base URL

- **Local:** `http://localhost:8000` (uvicorn default).
- **Deployed:** set per [DEPLOYMENT.md](./DEPLOYMENT.md).

Versioned routes use the `/v1` prefix. Health is unversioned: `GET /health`.

## Authentication

Protected routes require an **Overage** API key:

```http
X-API-Key: ovg_live_...
```

Provider credentials (OpenAI, Anthropic) are passed through in the same way as when calling the provider directly; see proxy routes below.

### Register (creates user + first API key)

`POST /v1/auth/register` — **no payment**, returns the **raw API key once** in the JSON body.

**Request body (JSON):**

| Field | Type | Rules |
|-------|------|--------|
| `email` | string | Unique, 3–255 chars |
| `name` | string | 1–255 chars |
| `password` | string | 8–128 chars |

**Response `201`:** user fields (`id`, `email`, `name`, `created_at`) plus **`api_key`** (string, prefix `ovg_live_`). Store it immediately; it is not shown again.

**Response `409`:** email already registered (`DUPLICATE_EMAIL`).

**Example:**

```bash
curl -sS -X POST "http://localhost:8000/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","name":"You","password":"your-secure-pass"}'
```

### Generate another API key

`POST /v1/auth/apikey` — requires **`X-API-Key`** (any valid key for the account).

**Request body (JSON):**

| Field | Type | Default |
|-------|------|---------|
| `name` | string | `"Default Key"`, max 255 |

**Response `201`:** `{ "key": "ovg_live_...", "name": "...", "created_at": "..." }` — raw `key` shown **once**.

**Example:**

```bash
curl -sS -X POST "http://localhost:8000/v1/auth/apikey" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $OVERAGE_API_KEY" \
  -d '{"name":"laptop"}'
```

## Endpoints (overview)

| Method | Path | Auth | Summary |
|--------|------|------|---------|
| `GET` | `/health` | No | Liveness / readiness |
| `POST` | `/v1/auth/register` | No | Register; returns first `api_key` |
| `POST` | `/v1/auth/apikey` | Yes | Create additional API key |
| `POST` | `/v1/proxy/{provider}` | Yes | Forward LLM request (see routes module for path variants) |
| `GET` | `/v1/calls` | Yes | List proxied calls |
| `GET` | `/v1/calls/{call_id}` | Yes | Call detail + estimation |
| `GET` | `/v1/summary` | Yes | Aggregate discrepancy stats |
| `GET` | `/v1/summary/timeseries` | Yes | Daily buckets |
| `GET` | `/v1/report` | Yes | PDF audit (date range query params) |
| `GET` | `/v1/alerts` | Yes | List discrepancy alerts |
| `POST` | `/v1/alerts/{id}/acknowledge` | Yes | Acknowledge alert |

## Client headers

- **Overage:** `X-API-Key` for all `/v1/*` routes except `POST /v1/auth/register`.
- **Providers:** unchanged from direct provider usage (e.g. `Authorization: Bearer sk-...` for OpenAI when proxied).

## Limits

Pilot defaults are suitable for development; production caps will be documented when finalized.

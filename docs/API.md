# Overage API

This page is a **stub**. For request/response schemas, authentication, and behavioral contracts, see **[PRD.md](../PRD.md)** (especially the API contract section).

## Base URL

- **Production:** configure per your deployment (see [DEPLOYMENT.md](./DEPLOYMENT.md)).
- **Local:** typically `http://localhost:8000` when running the proxy dev server.

All versioned routes are under the `/v1` prefix unless noted.

## Endpoints (overview)

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/health` | Liveness / readiness probe |
| `POST` | `/v1/proxy/{provider_name}` | Forward an LLM request via the Overage proxy |
| `GET` | `/v1/calls` | List proxied calls |
| `GET` | `/v1/calls/{call_id}` | Call detail including estimation |
| `GET` | `/v1/summary` | Aggregate discrepancy statistics |
| `GET` | `/v1/summary/timeseries` | Daily time-series discrepancy data |
| `POST` | `/v1/auth/register` | Register a user |
| `POST` | `/v1/auth/apikey` | Create an API key |

Authentication for protected routes uses the API key mechanism described in **PRD.md** and implemented in `proxy/api/auth.py`.

## Versioning

Breaking changes to `/v1` will be announced with migration notes. New capabilities may appear as additional fields or optional query parameters first.

## Client headers

Send the Overage API key on requests that require it (exact header name and format match **PRD.md** and the FastAPI dependency in `validate_api_key`). Provider credentials (OpenAI, Anthropic) travel in the same way as when calling the provider directly.

## Limits

Rate limits and payload caps will be documented here once finalized for production; until then, treat defaults as suitable for pilot workloads only.

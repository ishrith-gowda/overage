# Deployment

Stub guide for running Overage in development and in the cloud. Expand this document as runbooks and infrastructure mature.

## Local Development

1. Clone the repository and create a Python environment (see the root **README.md**).
2. Copy `.env.example` to `.env` and fill in database URL, secrets, and provider-related settings.
3. Run database migrations as documented in the main README (or project scripts).
4. Start the proxy (e.g. FastAPI app entrypoint under `proxy/`) and optional dashboard.

Use `GET /health` to confirm the service is up before integrating clients.

## Container image security

CI builds the production **Dockerfile** (see `.github/workflows/ci.yml` → **Docker Build** + **Trivy**). Scan results are uploaded as SARIF to **GitHub Code Scanning**; a **new critical** finding can surface on PRs as a failing **`CodeQL`** check from **GitHub Advanced Security** (separate from the **`CodeQL Analysis`** workflow job).

- The runtime image avoids **`curl`** (reduces `libcurl` / `libssh2` exposure); **`HEALTHCHECK`** uses Python’s **`urllib.request`**.
- Accepted-but-unpatched distro CVEs are listed in **`.trivyignore`** with rationale — remove entries when Debian security updates ship fixed packages and CI’s Trivy step passes without them (the Trivy action is wired with **`trivyignores: .trivyignore`**).

## DigitalOcean

The MVP targets a simple VM or App Platform–style deployment on **DigitalOcean** (or similar): container or process manager, HTTPS termination, and managed PostgreSQL compatible with the app’s SQLAlchemy configuration.

- Provision Postgres and note the connection string for `DATABASE_URL` (or equivalent).
- Set environment variables from the section below; avoid committing secrets.
- Run migrations on deploy; pin the Overage version (image tag or git SHA) for traceability.

Document Droplet sizing, firewall rules, and backup policy here as you finalize them.

## Environment Variables

Configure at minimum (names may match `.env.example`):

- **Database:** URL for async SQLAlchemy / Supabase-compatible Postgres.
- **Auth / API keys:** secrets used to mint and validate customer API keys.
- **CORS / dashboard:** allowed origins if the dashboard calls the API from a browser.
- **Observability:** optional Sentry DSN, log level, and metrics endpoints.

Never commit `.env`; use your host’s secret store or encrypted env files in CI.

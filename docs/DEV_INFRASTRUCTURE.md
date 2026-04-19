# Overage — developer infrastructure (phased)

This document tracks **infrastructure setup** for the Overage project: accounts, secrets, domains, and integrations. It is the canonical place to see **which phase we are in** and **what comes next**. It does **not** replace [DEPLOYMENT.md](./DEPLOYMENT.md) for runtime runbooks or [INSTRUCTIONS.md](../INSTRUCTIONS.md) for code standards.

**Rules**

- Never commit API keys, tokens, or connection strings. Use **Doppler** and/or **1Password** (both available on your stack) plus GitHub **Actions secrets** for CI.
- If a secret is ever pasted into chat, email, or a screenshot shared publicly, **rotate it immediately** in the provider’s dashboard.

---

## Phase overview

| Phase | Name | Goal | Status |
|-------|------|------|--------|
| **1** | Accounts & platforms | Register tools, credits, student/education plans | **Largely complete** (inventory below) |
| **2** | Secrets & environment | Single source of truth for env vars; `.env` derived from vault; CI secrets | **Substantially complete** — Doppler `overage`/`dev` populated; `doppler.yaml` + Makefile; 1Password backup script (run `op signin` then `scripts/backup_doppler_env_to_1password.sh`) |
| **3** | Domains & DNS | Canonical hostnames (API, dashboard, docs); Cloudflare routing | **Pending** |
| **4** | Observability & product analytics | Sentry, PostHog, optional Datadog/New Relic — wired to non-prod first | **Pending** |
| **5** | Data plane choice | Supabase Postgres (or other) for `DATABASE_URL`; align with PRD | **Pending** (CLI linking deferred until this phase) |
| **6** | Deploy & CI alignment | DigitalOcean / Heroku / Vercel roles; staging vs prod; Codecov + GitHub Actions | **In progress** (Codecov, CI already in repo) |
| **7** | MVP feature work | Resume product backlog per PRD | **Blocked** until phases 2–6 exit criteria are met |

---

## Phase 1 — Account inventory (sanitized)

Use this as a checklist only. **Do not** store secrets here.

| Area | Platform / plan | Notes |
|------|-------------------|--------|
| IDE / AI | GitHub Copilot Pro, GitHub Pro (Student) | Confirmed |
| Cloud credits | DigitalOcean ($200 GitHub Student Pack) | Until Apr 2027 |
| Cloud credits | Azure for Startups (target: up to $5k) | Enrollment in progress; resolve with Microsoft Support |
| PaaS | Heroku ($13/mo × 24 mo credits) | Billing screenshot on file |
| Domains | `overage.dev` (name.com + Wix bundle), `overage.me` (Namecheap), `overage.tech` (.tech promo) | Pick **one canonical** public hostname in Phase 3 |
| Errors / perf | Sentry (sponsored / education Team) | Plan change scheduled Apr 2027 — note renewal |
| Payments | Stripe (waived fees on first $1k revenue) | |
| Database | MongoDB Atlas ($50 promo credits) | Optional; **product DB in repo targets Postgres** — see Phase 5 |
| APM | Datadog Pro (student), New Relic (student) | Optional overlap; choose **one** primary for MVP to avoid noise |
| Secrets | Doppler (Team via Student), 1Password (1y dev bundle) | Phase 2: standardize on one **primary** vault |
| Coverage | Codecov (Developer plan) | `CODECOV_TOKEN` in GitHub secrets only |
| Backend services | Appwrite (Student), Supabase (project exists) | Phase 5: map to Overage needs (Postgres, auth) |
| CI | Travis CI (Education), GitHub Actions (repo) | **Primary CI is GitHub Actions**; avoid duplicating pipelines without reason |
| Local cloud emulation | LocalStack | Dev/test only |
| Misc dev | Termius, PopSQL, Loom, Calendly, Granola, Notion AI | Collaboration / ops |
| Colab / research | Colab Pro, Chameleon Cloud | Model training / research compute |
| Edge / front | Cloudflare (Workers credit), Vercel / v0 (student) | Phase 3–6 for dashboard or marketing sites |
| LLM providers | OpenAI, Anthropic (console) | Keys only in vault + `.env` (never in git) |

---

## Phase 2 — Secrets & environment (status)

Step-by-step: **[DOPPLER_1PASSWORD_SETUP.md](./DOPPLER_1PASSWORD_SETUP.md)**.

**Done in repo:** committed **`doppler.yaml`** (`overage` / `dev`); **`Makefile`** targets `secrets-verify`, `check-doppler`, `run-doppler`, `sync-env-to-doppler`; **`scripts/backup_doppler_env_to_1password.sh`** for a 1Password document snapshot.

**Your remaining manual steps:**

1. **1Password backup:** `eval $(op signin)` then `export OP_VAULT=…` and run `./scripts/backup_doppler_env_to_1password.sh` (or mirror secrets manually in the app).
2. **GitHub Actions:** ensure **`CODECOV_TOKEN`** (and any deploy tokens) exist under **Repository → Settings → Secrets**.
3. Optional: document in 1Password (not in git) which credentials are **shared with research** vs **Overage-only**.

### OpenAI key usage (policy)

- You **may** use one OpenAI API key for both research and Overage **development** if you accept shared quota and shared blast radius.
- **Best practice** for a professional project: create **two keys** in the OpenAI dashboard (e.g. `overage-dev`, `research`) so you can rotate or disable one without affecting the other. Costs accrue to the **same** billing account unless you use separate orgs/projects.
- Never paste keys into issues, PRs, Cursor chat, or Slack; load from environment only.

---

## Phase 3 — Domains & DNS (after Phase 2)

1. Choose **canonical** root for the product (e.g. `overage.dev` for marketing, `api.overage.dev` for API) — decision recorded in this section when made.
2. Point DNS at Cloudflare (or registrar DNS) and configure TLS.
3. Add allowed origins (`CORS_ORIGINS`) to match real dashboard URLs.

---

## Phase 4 — Observability

1. Create **non-production** Sentry project → set `SENTRY_DSN` in dev/staging only first.
2. PostHog: create project → `POSTHOG_API_KEY` (and host if self-hosted or EU).
3. Defer Datadog vs New Relic deep integration until one primary APM is chosen (avoid double-instrumenting everything pre-MVP).

---

## Phase 5 — Database (Supabase / Postgres)

1. Align with PRD: **PostgreSQL**-compatible `DATABASE_URL` for the app.
2. Export connection string from Supabase (or chosen host) into vault; never commit.
3. Later: Supabase CLI workflows for migrations vs Alembic (document choice in [DEPLOYMENT.md](./DEPLOYMENT.md)).

---

## Phase 6 — Deploy & CI

1. Keep **GitHub Actions** as the single source of truth for PR checks.
2. Decide: **DigitalOcean** vs **Heroku** vs other for first **staging** deployment (cost, Postgres addon, regions).
3. Ensure production secrets are **only** on the host / Doppler / GitHub environments — not in repo.

---

## Exit criteria before MVP (Phase 7)

- [ ] All secrets in vault + GitHub Actions; no keys in git history for current keys.
- [ ] Canonical domain and HTTPS path documented.
- [ ] `DATABASE_URL` for shared dev/staging decided and working with migrations.
- [ ] Sentry (min.) and PostHog wired for at least one non-prod environment.
- [ ] Deployment target chosen (DO or Heroku or other) with a smoke-tested URL.

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-17 | Initial phased inventory and next-step gates |

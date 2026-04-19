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
| **2** | Secrets & environment | Single source of truth for env vars; `.env` derived from vault; CI secrets | **Complete** (see § Phase 2 exit criteria) |
| **3** | Domains & DNS | Canonical hostnames (API, dashboard, docs); Cloudflare routing | **Current** — start with § Phase 3 playbook |
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

## Phase 2 — Secrets & environment (**complete**)

Procedure reference: **[DOPPLER_1PASSWORD_SETUP.md](./DOPPLER_1PASSWORD_SETUP.md)**.

### Phase 2 exit criteria (all satisfied)

| Criterion | Evidence |
|-----------|----------|
| Doppler project + `dev` config holds app secrets | `overage` / `dev`; upload via `doppler secrets upload` / `make sync-env-to-doppler` |
| Repo declares Doppler linkage | Committed **`doppler.yaml`** (no secrets) |
| Local/dev commands can run with injected env | **`make secrets-verify`**, **`make check-doppler`**, **`make run-doppler`** |
| 1Password backup of Doppler snapshot | Document **“Overage — Doppler dev snapshot”** in vault **Personal** (confirmed) |
| CI upload token (verify in GitHub UI) | Repository → **Settings → Secrets and variables → Actions** — **`CODECOV_TOKEN`** present for Codecov uploads (add if missing; value lives only in GitHub) |

Optional (nice-to-have): note in 1Password (not in git) which credentials are **shared with research** vs **Overage-only**.

### OpenAI key usage (policy)

- You **may** use one OpenAI API key for both research and Overage **development** if you accept shared quota and shared blast radius.
- **Best practice** for a professional project: create **two keys** in the OpenAI dashboard (e.g. `overage-dev`, `research`) so you can rotate or disable one without affecting the other. Costs accrue to the **same** billing account unless you use separate orgs/projects.
- Never paste keys into issues, PRs, Cursor chat, or Slack; load from environment only.

---

## Phase 3 — Domains & DNS (**current**)

**Goal:** one **canonical** public identity (apex + subdomains), DNS and TLS under control, and `CORS_ORIGINS` / future deploy URLs aligned.

### Recommended shape (decide explicitly; edit this table when chosen)

| Role | Example hostname | Notes |
|------|------------------|--------|
| **Apex / marketing** | `overage.dev` | Strong match to product; you already own it. |
| **API (HTTPS)** | `api.overage.dev` | Reverse proxy / FastAPI later; not required for Phase 3 DNS-only. |
| **Dashboard (optional)** | `app.overage.dev` or path on apex | Streamlit or static front later. |
| **Docs / marketing** | `www.overage.dev` or apex | Optional; avoid duplicate content (pick apex **or** `www`). |

You also own **`overage.me`** and **`overage.tech`** — use for **redirects** or **staging** later, or park until needed; **one** apex should be canonical for the product to avoid SEO and CORS sprawl.

### Playbook (Cloudflare — you have an account)

1. **Add the site** in [Cloudflare](https://dash.cloudflare.com) for the domain you will use first (e.g. `overage.dev`).
2. **Nameservers:** At the registrar (name.com / Namecheap), replace the default NS with the **two Cloudflare nameservers** shown in the setup wizard. Wait for status **Active** (often minutes to a few hours).
3. **DNS records (minimal):**
   - **Apex:** `A` or **CNAME** to a placeholder (e.g. `192.0.2.1` or a parking target) until you have a real host; or use **CNAME flattening** per Cloudflare docs.
   - **`api`:** add when you have a deployment target (Phase 6); can be a **CNAME** to your PaaS hostname later.
4. **TLS:** Enable **Full (strict)** once origin has a valid certificate; until then **Flexible** is common for static-only origins (document what you chose).
5. **Doppler:** When you have real HTTPS URLs, set `CORS_ORIGINS` / related env in **`dev`** (comma-separated origins, e.g. `https://app.overage.dev,https://overage.dev`).

### Phase 3 exit criteria (before Phase 4)

- [ ] **Canonical apex** chosen and written in this doc (table above filled).
- [ ] **Cloudflare** active for that domain (nameservers delegated).
- [ ] **DNS** documented (screenshot or export in `docs/` optional — **no** secrets).
- [ ] **`CORS_ORIGINS`** updated in Doppler when first HTTPS origins exist.

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
| 2026-04-19 | Phase 2 marked complete; Phase 3 playbook expanded |

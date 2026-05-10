# Overage — developer infrastructure inventory

This document is the **canonical account / platform / vendor inventory** for the Overage project: which credits, plans, vaults, and integrations the project leans on, and the Phase-2 Doppler / 1Password secret-management exit criteria. It does **not** track delivery phases — that lives in **[`docs/ROADMAP.md`](./ROADMAP.md)**, which is the single source of truth for what Overage is building, has built, and plans to build.

> **Phase numbering note.** Earlier versions of this file carried its own `Phase 1` … `Phase 7` numbering for infrastructure work. That conflicted with the PR-title-driven `phase 0` … `phase 6` delivery numbering and the `Phase 7` quality-hardening track. Both numbering schemes (and the PRD user-story numbering, and the standalone product-only roadmap) were consolidated into `docs/ROADMAP.md` on 2026-05-10. The infra work that previously called itself "Phase 3 — Domains & DNS" is now **`docs/ROADMAP.md` §5 Phase 8 — Domains & DNS**; "Phase 4 — Observability" is **Phase 9**; "Phase 5 — Database" is **Phase 10**; "Phase 6 — Deploy & CI" is **Phase 11**. This file no longer carries phase tables — it only carries the inventory and the Doppler exit criteria.

**Rules**

- Never commit API keys, tokens, or connection strings. Use **Doppler** and/or **1Password** (both available on this stack) plus GitHub **Actions secrets** for CI.
- If a secret is ever pasted into chat, email, or a screenshot shared publicly, **rotate it immediately** in the provider's dashboard.

---

## Account inventory (sanitised)

Use this as a checklist only. **Do not** store secrets here.

| Area | Platform / plan | Notes |
|------|-------------------|--------|
| IDE / AI | GitHub Copilot Pro, GitHub Pro (Student) | Confirmed |
| Cloud credits | DigitalOcean ($200 GitHub Student Pack) | Until Apr 2027 |
| Cloud credits | Azure for Startups (target: up to $5k) | Enrollment in progress; resolve with Microsoft Support |
| PaaS | Heroku ($13/mo × 24 mo credits) | Billing screenshot on file |
| Domains | `overage.dev` (name.com + Wix bundle), `overage.me` (Namecheap), `overage.tech` (.tech promo) | Pick **one canonical** public hostname in `docs/ROADMAP.md` Phase 8 |
| Errors / perf | Sentry (sponsored / education Team) | Plan change scheduled Apr 2027 — note renewal |
| Payments | Stripe (waived fees on first $1k revenue) | |
| Database | MongoDB Atlas ($50 promo credits) | Optional; **product DB in repo targets Postgres** — see `docs/ROADMAP.md` Phase 10 |
| APM | Datadog Pro (student), New Relic (student) | Optional overlap; choose **one** primary for MVP to avoid noise |
| Secrets | Doppler (Team via Student), 1Password (1y dev bundle) | Standardised on **Doppler** as primary vault; 1Password holds the human-readable backup |
| Coverage | Codecov (Developer plan) | `CODECOV_TOKEN` in GitHub secrets only |
| Backend services | Appwrite (Student), Supabase (project exists) | `docs/ROADMAP.md` Phase 10 maps Supabase Postgres for the production DB |
| CI | Travis CI (Education), GitHub Actions (repo) | **Primary CI is GitHub Actions**; avoid duplicating pipelines without reason |
| Local cloud emulation | LocalStack | Dev/test only |
| Misc dev | Termius, PopSQL, Loom, Calendly, Granola, Notion AI | Collaboration / ops |
| Colab / research | Colab Pro, Chameleon Cloud | Model training / research compute (`docs/ROADMAP.md` Phase 12) |
| Edge / front | Cloudflare (Workers credit), Vercel / v0 (student) | `docs/ROADMAP.md` Phase 8 (DNS) and Phase 11 (deploy) |
| LLM providers | OpenAI, Anthropic (console) | Keys only in vault + `.env` (never in git) |

---

## Secrets & environment (Doppler / 1Password)

Procedure reference: **[DOPPLER_1PASSWORD_SETUP.md](./DOPPLER_1PASSWORD_SETUP.md)**.

### Exit criteria (all currently satisfied)

| Criterion | Evidence |
|-----------|----------|
| Doppler project + `dev` config holds app secrets | `overage` / `dev`; upload via `doppler secrets upload` / `make sync-env-to-doppler` |
| Repo declares Doppler linkage | Committed **`doppler.yaml`** (no secrets) |
| Local/dev commands can run with injected env | **`make secrets-verify`**, **`make check-doppler`**, **`make run-doppler`** |
| 1Password backup of Doppler snapshot | Document **"Overage — Doppler dev snapshot"** in vault **Personal** (confirmed) |
| CI upload token | **`CODECOV_TOKEN`** under **Repository secrets** (see **[CODECOV.md](./CODECOV.md)** — activate repo in Codecov if **Deactivated**) |

Optional (nice-to-have): note in 1Password (not in git) which credentials are **shared with research** vs **Overage-only**.

### OpenAI key usage (policy)

- You **may** use one OpenAI API key for both research and Overage **development** if you accept shared quota and shared blast radius.
- **Best practice** for a professional project: create **two keys** in the OpenAI dashboard (e.g. `overage-dev`, `research`) so you can rotate or disable one without affecting the other. Costs accrue to the **same** billing account unless you use separate orgs/projects.
- Never paste keys into issues, PRs, Cursor chat, or Slack; load from environment only.

---

## Where infrastructure work is tracked

Infrastructure phases (DNS, observability, production database, staging deploy, on-prem packaging) live in **[`docs/ROADMAP.md`](./ROADMAP.md)** §5:

- **Phase 8 — Domains & DNS** (Cloudflare apex, subdomain reservations, `CORS_ORIGINS`)
- **Phase 9 — Observability backbone** (Sentry, Datadog, PostHog, structured logs, health checks)
- **Phase 10 — Production database and migrations** (Supabase Postgres, Alembic, partitioning)
- **Phase 11 — Staging environment and continuous deploy** (DigitalOcean App Platform, CD via GitHub Actions, rollback runbook)
- **Phase 16 — On-prem deployment package** (air-gapped Docker / Helm / Terraform bundle)

Each phase in `docs/ROADMAP.md` has full subtasks, acceptance criteria, test plan, definition of done, rollback plan, related files, and risks. This document does not duplicate that material — when the infra inventory above changes (e.g., a new vendor is added, a credit expires, a vault decision is revisited), update the relevant table here and link to the `docs/ROADMAP.md` phase that owns the change.

---

## Revision history

| Date | Change |
|------|--------|
| 2026-05-10 | Phase tables removed; pointers added to `docs/ROADMAP.md` for the consolidated phase ledger. Account inventory and Doppler exit criteria preserved. |
| 2026-04-19 | Phase 2 marked complete; Phase 3 playbook expanded (predecessor doc — content folded into `docs/ROADMAP.md` Phase 8). |
| 2026-04-17 | Initial phased inventory and next-step gates (predecessor doc). |

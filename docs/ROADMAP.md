# ROADMAP — Overage delivery phases

This is the **single source of truth** for what phase Overage is in, what's done, and what's next.

- **PRD-defined product phases (0 → 6)** delivered the MVP and immediate post-MVP. Each was a single PR; the PR # is shown.
- **Phase 7 (Quality Hardening)** is the current ongoing post-MVP track. Subtasks are tracked here, not in PRD.md.
- New top-level phases append after Phase 7 and reference `PRD.md` stories where applicable.

When in doubt, ask "which phase / subtask are we in?" and check this file. The agent is expected to update the **Status** column and the **Active phase** pointer the moment a subtask lands on `main`.

---

## Active phase

**Phase 7 — Quality Hardening / GitHub Hygiene** (started 2026-04-15, ongoing).

Most recent landed subtask: **7.5 — rewrite dirty commit history on `main`** (force-push 2026-05-10, safety tag `pre-rewrite-2026-05-10`).

Next planned subtask: **7.6 — automated trailer-cleanup safeguard**.

---

## Phase history

### Phase 0 — Foundation and local runtime
- **PR:** [#14](https://github.com/ishrith-gowda/overage/pull/14) · merged 2026-04-07
- **PRD coverage:** Story 1 (proxy skeleton), Story 7 (quickstart) bootstrap.
- **Outcome:** Repo skeleton, FastAPI scaffolding, local runtime, base CI.
- **Status:** done.

### Phase 1 — OpenAI SDK proxy path, tests, quickstart
- **PR:** [#15](https://github.com/ishrith-gowda/overage/pull/15) · merged 2026-04-07
- **PRD coverage:** Story 1 (route OpenAI calls).
- **Outcome:** `/v1/proxy/openai` end-to-end, OpenAI usage extraction, integration tests, quickstart doc.
- **Status:** done.

### Phase 2 — Anthropic SDK parity, benchmark, latency docs
- **PR:** [#16](https://github.com/ishrith-gowda/overage/pull/16) · merged 2026-04-07
- **PRD coverage:** Story 2 (Anthropic), NFR latency.
- **Outcome:** `/v1/proxy/anthropic`, thinking-tokens extraction, `scripts/benchmark.py` proving p50<5ms / p99<10ms, latency README section.
- **Status:** done.

### Phase 3 — Calls list estimation fields and dashboard highlights
- **PR:** [#17](https://github.com/ishrith-gowda/overage/pull/17) · merged 2026-04-07
- **PRD coverage:** Story 3 (per-call reported vs estimated).
- **Outcome:** `/v1/calls` returns estimation fields, dashboard call-detail view, time-series chart.
- **Status:** done.

> Note: The chat label "phase 3" in spring 2026 sometimes referred to the *post-MVP GitHub-green effort* below; that work is **Phase 7**, not PRD Phase 3. This file is the canonical mapping.

### Phase 4 — Summary group_by, alerts, SDK fixes
- **PR:** [#18](https://github.com/ishrith-gowda/overage/pull/18) · merged 2026-04-07
- **PRD coverage:** Stories 4, 8, 9 (data model), Story 10.
- **Outcome:** `/v1/summary` with `group_by`, `/v1/alerts`, SDK auth headers + endpoint paths corrected.
- **Status:** done.

### Phase 5 — Alert acknowledge, dashboard group chart, CI Docker+Trivy on PRs
- **PR:** [#19](https://github.com/ishrith-gowda/overage/pull/19) · merged 2026-04-07
- **PRD coverage:** Story 9 (alert ack), Story 8 (group chart), NFR/security.
- **Outcome:** `POST /v1/alerts/{id}/ack`, dashboard pivot chart, container scanning in CI.
- **Status:** done.

### Phase 6 — PDF audit report, SDK, dashboard follow-ups
- **PR:** [#20](https://github.com/ishrith-gowda/overage/pull/20) · merged 2026-04-07
- **PRD coverage:** Story 6 (PDF audit report).
- **Outcome:** `/v1/reports/pdf` endpoint, `[reporting]` extras (fpdf2 + matplotlib), SDK helper, dashboard "Download PDF" button, fixture-driven tests.
- **Status:** done.

---

## Phase 7 — Quality Hardening / GitHub Hygiene (active)

Goal: every check on every PR is green, every commit on `main` is clean, branch protection prevents drift, and the agent + dependabot can't sneak in trailers or multi-line bodies.

| ID | Subtask | Status | Anchor |
|----|---------|--------|--------|
| 7.0 | All required CI checks green on `main` (Lint / Type Check / Test / Security Scan / Docker Build / CodeQL / Dependency Review). | done | PR #32, #33 |
| 7.1 | Branch protection: required checks, strict (must be up to date), linear history, no force pushes, conversation resolution. | done | API call (no PR; settings only) |
| 7.2 | Repo merge settings: `squash_merge_commit_title=PR_TITLE`, `squash_merge_commit_message=BLANK`, `delete_branch_on_merge=true`, `allow_merge_commit=false`, `allow_rebase_merge=false`, `allow_auto_merge=false`. | done | API call + PR #33 docs |
| 7.3 | `Commit Lint` workflow + `.gitmessage` + stronger `prepare-commit-msg` hook + `CONTRIBUTING.md` rewrite. | done | PR #33 |
| 7.4 | `dependabot.yml` cleanup (no doubled `(deps)(deps)` titles). | done | PR #44 |
| 7.5 | Rewrite the 23 dirty commits between `bf748dc..pre-rewrite-2026-05-10` to single-line, no body, no trailers. | done | force-push 2026-05-10; safety tag `pre-rewrite-2026-05-10` |
| 7.6 | `make strip-trailers` + `workflow_dispatch` workflow that the maintainer can trigger to scrub `Co-authored-by:` / `Signed-off-by:` from any future drift on `main`. | done | this PR |
| 7.7 | Document the manual squash-merge process (no `--auto`, no UI "Update branch") in `CONTRIBUTING.md`; this is what stops GitHub from auto-injecting `Co-authored-by:` going forward. | done | this PR |
| 7.8 | (optional) GitHub App / fine-grained PAT enabling fully-automated post-merge cleanup without a maintainer step. Tracked but not blocking. | open | — |

When 7.6 + 7.7 land, **Phase 7 is fully done**. 7.8 is a nice-to-have for full automation; the manual `make strip-trailers` covers the same outcome with one command.

---

## Future phases (not started; tracked here so they don't get lost)

- **Phase 8 — Provider expansion:** Gemini adapter (`/v1/proxy/gemini`), provider-aware estimation calibration. Maps to PRD §7 "EXPLICITLY OUT" → Gemini.
- **Phase 9 — Multi-tenant + RBAC:** tenant scoping in data models, per-tenant API key tables, role-based access on dashboard endpoints. Maps to PRD §7 "EXPLICITLY OUT" → Multi-tenant isolation.
- **Phase 10 — Webhook + alerting backend:** HTTPS webhook delivery, retry policy, dead-letter queue, optional email/slack adapters. Maps to PRD §7 → Alerting system, Webhook notifications.
- **Phase 11 — On-prem deployment:** Helm chart, Terraform module, air-gapped image catalog. Maps to PRD §7 → On-prem deployment automation.

Each future phase is a single tracking PR that opens as a draft, links the relevant PRD stories, and only merges when its acceptance criteria are met.

---

## Conventions

- **One phase, one PR** for product-track phases (0–6, 8+). Subtasks of the active hardening phase (Phase 7) may land as separate small PRs.
- The PR title that opens or completes a phase **must** reference the phase (e.g., `feat(phase-8): gemini provider adapter`).
- The agent updates the **Active phase** pointer + the **Status** column in this file as part of the same PR that lands the work.
- The `pre-rewrite-2026-05-10` tag is kept indefinitely as the recovery point for the Phase 7.5 history rewrite. Do not delete without an explicit instruction from the maintainer.

# ROADMAP — Overage master phase ledger

> **Single source of truth for everything Overage is building, has built, and plans to build.**
>
> This document supersedes the phase tables that previously lived in `docs/DEV_INFRASTRUCTURE.md` and the standalone product-only roadmap from May 2026. It consolidates four previously-fragmented numbering schemes — PR-title delivery phases (`phase 0` … `phase 6`), DEV_INFRASTRUCTURE infra phases (`Phase 1` … `Phase 7`), PRD user stories (`Story 1` … `Story 10`), and quality-hardening subtasks (`7.0` … `7.8`) — into one canonical, dependency-aware ledger.
>
> **Authoring rules.** Every phase has a fully expanded section with: goal, status, dates and PR refs, PRD coverage, dependencies, subtasks with acceptance criteria, test plan, definition of done, rollback plan, related files, and risk notes. The agent and the maintainer update **Active phase** at the top, the **Status** field of each phase, and the **Revision history** section the moment a subtask lands on `main`. Adding a phase always means appending a new section at the end of §5; never re-number existing phases (PR titles in git history reference the original numbers and must remain greppable).
>
> **Where this document fits.** [`PRD.md`](../PRD.md) defines product *behaviour* (what the system does for users). [`ARCHITECTURE.md`](../ARCHITECTURE.md) defines *structure* (how components are wired). [`INSTRUCTIONS.md`](../INSTRUCTIONS.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md) define *how we write code and ship*. **This document defines *what we are building, in what order, with what acceptance criteria* —** everything in those other documents flows through here when it becomes scheduled work.

---

## Active phase pointer

| Field | Value |
|-------|-------|
| **Active phase** | **Phase 7 — Quality Hardening / GitHub Hygiene** |
| **Active phase status** | active (started 2026-04-15) |
| **Most recent landed subtask** | 7.5 — rewrite dirty commit history on `main` (force-push 2026-05-10; safety tag `pre-rewrite-2026-05-10`) |
| **Next planned subtask** | 7.6 — automated trailer-cleanup safeguard (this PR) |
| **First non-active phase that is unblocked** | **Phase 8 — Domains & DNS** (no upstream blockers; can start as soon as Phase 7 closes) |
| **Currently blocked phases** | Phase 11 (deploy) blocked on Phase 8/9/10; Phase 14 (multi-tenant) blocked on Phase 13 (provider expansion) only loosely; Phase 16 (on-prem) blocked on Phase 11 |

When a phase completes, the agent updates this table, the **Status** field of the closed phase in §5, and appends a row to §11 (Revision history). Do not silently advance the active pointer in unrelated PRs.

---

## Recent landings (rolling 30-day window)

| Date | Phase / Subtask | PR | Commit | Note |
|------|-----------------|----|--------|------|
| 2026-05-10 | 7.6 / 7.7 | #45 | tip of `docs/cursor-rule-contributing-workflow` | trailer-cleanup tooling, manual-merge doc |
| 2026-05-10 | 7.5 | force-push (no PR) | `pre-rewrite-2026-05-10` → new `main` tip | history rewrite of 23 dirty commits, no force-push allowed since |
| 2026-05-10 | 7.4 | #44 | `c62669d` | dependabot scope dedup |
| 2026-05-10 | 7.3 / 7.0 | #33 | `b335e33` | commit-lint workflow + merge-settings doc |
| 2026-05-10 | 7.0 | #32 | `8a85dfc` | enforce CONTRIBUTING/INSTRUCTIONS workflow in cursor rules |
| 2026-04-07 | Phase 6 | #20 | merged | PDF audit report + SDK + dashboard polish |
| 2026-04-07 | Phase 5 | #19 | merged | alert ack + group chart + CI Trivy |
| 2026-04-07 | Phase 4 | #18 | merged | summary `group_by`, alerts, SDK fixes |
| 2026-04-07 | Phase 3 | #17 | merged | calls list with estimation fields |
| 2026-04-07 | Phase 2 | #16 | merged | Anthropic SDK parity, benchmark, latency docs |
| 2026-04-07 | Phase 1 | #15 | merged | OpenAI SDK proxy path + tests + quickstart |
| 2026-04-07 | Phase 0 | #14 | merged | foundation + local runtime |

A complete merged-PR list is one `gh pr list --state merged --limit 100` away; this table only carries the most recent month plus everything still relevant to active work. Older entries live in §11.

---

## Table of contents

1. [Project north star](#1-project-north-star)
2. [Phase taxonomy and conventions](#2-phase-taxonomy-and-conventions)
3. [PRD story → phase coverage matrix](#3-prd-story--phase-coverage-matrix)
4. [Acceptance-criteria taxonomy and templates](#4-acceptance-criteria-taxonomy-and-templates)
5. [Master phase ledger](#5-master-phase-ledger)
   - [Phase 0 — Foundation and local runtime](#phase-0--foundation-and-local-runtime-done)
   - [Phase 1 — OpenAI SDK proxy path](#phase-1--openai-sdk-proxy-path-done)
   - [Phase 2 — Anthropic parity, benchmark, latency docs](#phase-2--anthropic-parity-benchmark-latency-docs-done)
   - [Phase 3 — Calls list with estimation fields](#phase-3--calls-list-with-estimation-fields-done)
   - [Phase 4 — Summary group_by, alerts, SDK fixes](#phase-4--summary-group_by-alerts-sdk-fixes-done)
   - [Phase 5 — Alert acknowledge, dashboard group chart, CI Docker+Trivy](#phase-5--alert-acknowledge-dashboard-group-chart-ci-dockertrivy-done)
   - [Phase 6 — PDF audit report, SDK, dashboard follow-ups](#phase-6--pdf-audit-report-sdk-dashboard-follow-ups-done)
   - [Phase 7 — Quality Hardening / GitHub Hygiene](#phase-7--quality-hardening--github-hygiene-active)
   - [Phase 8 — Domains & DNS](#phase-8--domains--dns-planned)
   - [Phase 9 — Observability backbone](#phase-9--observability-backbone-planned)
   - [Phase 10 — Production database and migrations](#phase-10--production-database-and-migrations-planned)
   - [Phase 11 — Staging environment and continuous deploy](#phase-11--staging-environment-and-continuous-deploy-planned)
   - [Phase 12 — PALACE training and evaluation pipeline](#phase-12--palace-training-and-evaluation-pipeline-planned)
   - [Phase 13 — Gemini provider adapter](#phase-13--gemini-provider-adapter-planned)
   - [Phase 14 — Multi-tenant isolation and RBAC](#phase-14--multi-tenant-isolation-and-rbac-planned)
   - [Phase 15 — Webhook delivery and alerting backend](#phase-15--webhook-delivery-and-alerting-backend-planned)
   - [Phase 16 — On-prem deployment package](#phase-16--on-prem-deployment-package-planned)
   - [Phase 17 — Billing, Stripe, and metering](#phase-17--billing-stripe-and-metering-planned)
6. [Cross-cutting workstreams](#6-cross-cutting-workstreams)
7. [Rituals and cadence](#7-rituals-and-cadence)
8. [Risk register](#8-risk-register)
9. [Open questions](#9-open-questions)
10. [Glossary](#10-glossary)
11. [Revision history](#11-revision-history)

---

## 1. Project north star

### 1.1 Vision (one paragraph)

Overage is an independent audit layer for hidden LLM reasoning-token billing. It is a FastAPI reverse proxy that sits between an enterprise application and the LLM provider (OpenAI, Anthropic, Google Gemini), forwards requests with under 10ms of added latency, and asynchronously verifies the provider-reported reasoning-token counts using two independent signals: (1) PALACE — a LoRA-fine-tuned Qwen2.5-1.5B model that estimates reasoning tokens from prompt + answer text, and (2) timing analysis — a generation-time-vs-output-token correlation (Pearson ≥ 0.987 per arXiv:2412.15431) that cross-checks reported counts against expected tokens-per-second rates. The dashboard surfaces per-call discrepancies, aggregate honoring rates, and dollar impact. No provider cooperation required.

The full product spec is in [`PRD.md`](../PRD.md). This document never restates product behaviour at the feature level — it links to PRD stories. What this document adds is the **schedule, dependency graph, acceptance criteria, and definition of done** for each delivery slice.

### 1.2 Personas (compressed; full versions in PRD §2)

| ID | Persona | Primary use case | Phases that target this persona |
|----|---------|------------------|---------------------------------|
| **P1** | Alex Chen — Enterprise AI Platform Engineer (Series D fintech) | Routes all LLM traffic through a centralised gateway; needs <10ms overhead, per-model breakdown, and threshold alerting | 1, 2, 3, 4, 5, 9, 13, 15 |
| **P2** | Sarah Rodriguez — FinOps Lead (Fortune 500 insurer) | Audits LLM bills; needs PDF reports, time-series spend, and provider honoring rates for vendor negotiations | 4, 5, 6, 17 |
| **P3** | David Park — VP Engineering / CTO (growth-stage AI company) | Needs verifiable on-prem audit trail, multi-provider coverage, and alignment with AI governance frameworks | 13, 14, 16 |

### 1.3 Strategic guardrails

These constraints apply to **every** phase and override any subtask that would violate them. They are repeated here so a contributor reviewing one phase does not need to read all of `INSTRUCTIONS.md` to understand the non-negotiables.

1. **Latency budget.** The proxy adds **p50 < 5ms, p99 < 10ms** to the critical path. Any phase that touches `proxy/api/routes.py::proxy_request`, `proxy/providers/*`, or middleware **must** include a latency benchmark step in its acceptance criteria.
2. **Privacy.** In cloud mode, raw prompts and responses are **never** persisted. Only metadata: SHA-256 hash, character lengths, token counts, raw provider usage JSON. On-prem mode (Phase 16) is the only path where raw content may live in a customer database, and only when `STORE_RAW_CONTENT=true` is explicitly set.
3. **Stateless proxy.** No phase introduces request-scoped state in process memory that survives the response. Background tasks may read/write the database; they may not write to module-level state.
4. **Type-safety.** mypy strict on `proxy/`. Any phase that adds modules under `proxy/` must pass `mypy proxy/ --strict` before merge.
5. **CI green.** Lint, Type Check, Test, Security Scan, Docker Build, Trivy SARIF upload, CodeQL Analysis, Dependency Review, and Commit Lint must all be green on the PR. `main` is branch-protected with `strict: true` (must be up to date) and `required_linear_history: true`.
6. **Commits.** Single-line, all-lowercase, conventional-commit-prefixed, no body, no trailers, ≤ 72 chars subject. PR titles ≤ 80 chars. The squash merge command is always `gh pr merge <num> --squash --subject "<exact PR title>" --body ""` (see [`CONTRIBUTING.md`](../CONTRIBUTING.md)).
7. **Phase scope discipline.** One phase per PR for product-track phases (0–6, 8+). The hardening track (Phase 7) is the only place where a single phase legitimately ships across multiple small PRs because each subtask is independently revertable.

### 1.4 Out of scope (explicit non-goals)

The following items are frequently misidentified as Overage scope and are not on this roadmap. They live here so future contributors do not waste effort scoping them:

- **Provider-side cryptographic proofs (IMMACULATE-style).** Requires provider cooperation we cannot assume. Overage is unilateral by design.
- **Replacing Stripe / CloudZero / Vantage.** Those are pass-through billing tools; Overage is the verification layer above them. Integrations with them are scoped under Phase 17 and only via export, never replacement.
- **General-purpose LLM gateway features** (prompt caching, fallback routing, model A/B testing). Listed as anti-goals in PRD §7. The proxy stays narrow on its audit job.
- **Frontend marketing site.** A separate repo when the product graduates from technical-pilot stage.
- **Anthropic computer-use / OpenAI assistants API surface.** Story 1/2 cover Chat Completions and Messages only; assistants/threads are out of scope until a customer asks.

### 1.5 Reference glossary (full glossary in §10)

- **PALACE** — Prompt And Language Assessed Computation Estimator. The framework Overage uses to predict reasoning-token counts from a (prompt, answer) pair via a fine-tuned small language model (Qwen2.5-1.5B + LoRA).
- **TPS** — Tokens Per Second. The profiled output generation rate for a specific model, used by the timing estimator.
- **TTFT** — Time To First Token. Used in streaming mode to separate provider queuing from generation time.
- **Honoring rate** — Percentage of calls where the provider-reported reasoning-token count falls inside Overage's PALACE confidence interval `[low, high]`. Reported per provider and overall.
- **Discrepancy %** — `(reported_reasoning_tokens − combined_estimated_tokens) / combined_estimated_tokens × 100`. Positive means the provider reported more than Overage estimated.
- **Signals agree** — `True` when the PALACE estimate and the timing estimate fall within 20% of each other for a given call.

---

## 2. Phase taxonomy and conventions

### 2.1 Status values

Every phase carries one of these status values. The agent must update the field as work progresses:

| Status | Meaning | Allowed transitions |
|--------|---------|---------------------|
| `planned` | Documented but not started; no PR has been opened | → `active`, `cancelled` |
| `active` | Work is in progress; at least one PR is open or under review | → `done`, `blocked`, `cancelled` |
| `blocked` | Cannot progress until a named upstream phase or external dependency lands | → `active`, `cancelled` |
| `done` | All subtasks landed on `main`, definition of done satisfied, retrospective written (if material) | terminal |
| `cancelled` | Decided not to ship; reason recorded in the phase section | terminal |

### 2.2 Phase types

Each phase belongs to exactly one type. Types affect review checklists and which cross-cutting workstream applies (§6).

- **Product** — features that change behaviour observed by an end user (proxy endpoints, dashboard widgets, SDK methods). Phases 0–6, 13, 15, 17.
- **Infra** — platform plumbing that is not visible to the end user but is required for production: domains, observability, database, deploys. Phases 8–11, 16.
- **Quality** — engineering hygiene that improves repeatability/safety without adding features. Phase 7.
- **ML** — model training, evaluation, deployment of PALACE weights. Phase 12.
- **Business** — billing, contracts, packaging. Phase 17 has overlap; pure business work has not yet started its own phase.

### 2.3 Numbering convention

- Phases 0–6 are **historical PR-title slices**. The numbers are baked into git history (`phase 0`, `phase 1`, …) and must never be renumbered. They map 1:1 to PRs #14–#20.
- Phase 7 is the active hardening track. Subtasks are numbered `7.0`, `7.1`, … and may ship as separate PRs.
- Phases 8 onward append in delivery order (not strict numeric order). When two phases are unblocked simultaneously, the agent picks the one with smaller scope first to keep PRs reviewable.
- The PR title of a phase-opening or phase-closing PR includes a `(phase-N)` scope token — for example `feat(phase-8): cloudflare apex on overage.dev` — so a `git log --grep="phase-N"` produces the full phase history.

### 2.4 Dependency graph

Dependencies are recorded explicitly per phase. The high-level shape is:

```
Phase 0 ── Phase 1 ─┬─ Phase 2 ─┬─ Phase 3 ─ Phase 4 ─ Phase 5 ─ Phase 6 ─ Phase 7
                    │           │
                    └─ Phase 13 ┘
                    
Phase 7 ─┬─ Phase 8 ─┬─ Phase 11 ─ Phase 16
         │           │
         ├─ Phase 9 ─┤
         │           │
         └─ Phase 10 ┘

Phase 12 (PALACE training) is independent of the proxy track; it can run in parallel with anything once Phase 7 is closed because it only writes to `model/`.

Phase 14 (multi-tenant) depends on Phase 10 (production DB) for row-level isolation primitives.

Phase 15 (webhooks) depends on Phase 9 (observability) for retry telemetry and Phase 11 (staging) for end-to-end testing.

Phase 17 (billing) depends on Phase 14 for tenant scoping and Phase 11 for production deploy.
```

The dependency edges are repeated in each phase's **Dependencies** subsection so a reviewer only needs to read the phase they care about.

### 2.5 Branch and PR conventions

Per [`CONTRIBUTING.md`](../CONTRIBUTING.md), enforced by `Commit Lint` workflow:

| Token | Format | Example |
|-------|--------|---------|
| Branch name | `<type>/<phase-or-scope>-<short-slug>` | `feat/phase-8-cloudflare-apex` |
| PR title | `<type>(phase-N\|scope): <lowercase imperative subject>` | `feat(phase-8): activate cloudflare apex on overage.dev` |
| Commit subject | same as PR title (squash merge uses PR title verbatim) | — |
| Squash command | `gh pr merge <num> --squash --subject "<exact PR title>" --body ""` | — |

Trailers (`Signed-off-by:`, `Co-authored-by:`, `Made-with:`, `Generated-by:`, `Reported-by:`, `Reviewed-by:`, `Tested-by:`) are forbidden on every commit and every PR title. The `prepare-commit-msg` hook in `.githooks/` strips them locally; the `Commit Lint` workflow blocks PRs with bad titles.

---

## 3. PRD story → phase coverage matrix

This matrix is the bidirectional cross-reference between PRD §3 user stories and the phases that deliver them. When a story is partially covered, the matrix shows which phase covers which acceptance criterion.

| Story | Title | Persona | Priority | Sprint | Phase(s) that deliver it | Coverage notes |
|-------|-------|---------|----------|--------|--------------------------|----------------|
| **1** | Route OpenAI API calls through proxy | P1 | P0 | MVP | **Phase 1** (full) | All AC met by PR #15. Streaming SSE supported via `proxy/api/routes.py::proxy_request`. |
| **2** | Route Anthropic API calls through proxy | P1 | P0 | MVP | **Phase 2** (full) | All AC met by PR #16. Thinking-token extraction implemented in `proxy/providers/anthropic.py`. |
| **3** | View reported vs estimated reasoning tokens per call | P2 | P0 | MVP | **Phase 3** (full) | `GET /v1/calls` returns `reported_reasoning_tokens`, `estimated_reasoning_tokens`, `discrepancy_pct`, `timing_r_squared`, `signals_agree`. |
| **4** | View cumulative discrepancy in dollars over time | P2 | P0 | MVP | **Phase 4** (full) | `GET /v1/summary` and `GET /v1/summary/timeseries`. Per-token pricing in `proxy/constants.py`. |
| **5** | View timing consistency scores | P1 | P1 | MVP | **Phase 3** (data) + **Phase 5** (dashboard column) | `EstimationResult.timing_r_squared` populated; dashboard call table shows it. |
| **6** | Generate PDF audit report | P2 | P2 | post-MVP | **Phase 6** (full) | `GET /v1/report?start_date=&end_date=`, fpdf2 + matplotlib in `[reporting]` extra. |
| **7** | Add API key and start routing in <5min | new user | P0 | MVP | **Phase 0** (skeleton) + **Phase 1** (quickstart) + **Phase 17** (billing-free tier) | Quickstart in `README.md`. AC checked in [`PRD.md`](../PRD.md) — all marked `[x]`. |
| **8** | Per-model, per-endpoint discrepancy breakdown | P3 | P1 | MVP | **Phase 4** (`group_by`) + **Phase 5** (dashboard chart) | `group_by={provider, model, provider_model}` on `/v1/summary`. |
| **9** | Set alerting threshold for discrepancy | P1 | P2 | post-MVP | **Phase 4** (data model) + **Phase 5** (ack) + **Phase 15** (webhooks) | Alert rows + ack endpoint shipped; webhook delivery deferred to Phase 15. |
| **10** | View provider honoring rate | P2 | P1 | MVP | **Phase 4** (computation) + **Phase 5** (dashboard prominence) | `honoring_rate_pct` in summary; dashboard widget. |

PRD §7 "EXPLICITLY OUT" mapping:

| PRD §7 entry | Re-scoped to phase | Rationale |
|--------------|--------------------|-----------|
| Gemini provider adapter | **Phase 13** | Promoted from "out" to scheduled because growth-stage customers ask for it. |
| PDF report generation | **Phase 6** (already done) | Promoted to MVP scope during the April sprint. |
| Alerting system | **Phase 15** (webhooks) | Data model in Phase 4, ack in Phase 5, delivery layer in Phase 15. |
| On-prem deployment automation | **Phase 16** | Triggered when first enterprise pilot signs an LOI. |
| User management UI | not yet scheduled | API + CLI is sufficient until self-serve onboarding becomes a priority. |
| Webhook notifications | **Phase 15** | Same phase as alerting; both share the delivery substrate. |
| Multi-tenant isolation | **Phase 14** | Single-tenant remains acceptable through Phase 13. Becomes blocking once a second pilot user is signed. |
| Model A/B testing | not yet scheduled | Requires v0.2 and v0.3 PALACE weights from Phase 12 first. |
| Caching layer | not yet scheduled | Premature; revisit when a benchmark proves p99 latency budget is at risk. |
| Email verification | not yet scheduled | Pilot users are hand-onboarded; not needed until self-serve. |
| Per-endpoint rate limiting | not yet scheduled | Global per-key limit is sufficient until a customer reports a need. |

When a phase ships a story partially, the coverage notes in this matrix and the phase's own §5 entry are updated in the same PR.

---

## 4. Acceptance-criteria taxonomy and templates

Every phase's **Subtasks → Acceptance criteria** section uses the same structure so reviewers can mechanically verify completion. This section defines what each row means.

### 4.1 Acceptance-criterion shape

Each AC is one row of the form:

```
- [ ] <verb-leading description> — <verifiable signal> (<file or command that proves it>)
```

Examples:

```
- [ ] Returns 401 for unknown API key — `curl -i $BASE/v1/calls` with bad header → HTTP 401 (proxy/tests/test_api.py::test_list_calls_invalid_key)
- [ ] mypy strict passes on new module — `make typecheck` exit 0 (CI Type Check job)
- [ ] PR title <= 80 chars — Commit Lint workflow green
```

The verifiable signal must be **machine-checkable** wherever possible (a CI job, a curl command, a pytest test name) so that a reviewer can confirm the box without judgment.

### 4.2 Test-plan template

Every product, ML, or infra phase that touches code includes a test plan with these layers (skip layers that do not apply, never collapse them):

| Layer | What it covers | Tooling | Where it lives |
|-------|----------------|---------|----------------|
| **Unit** | Individual functions/classes in isolation; no DB, no network | pytest + AsyncMock | `proxy/tests/test_<module>.py` |
| **Integration** | Components working together; in-memory DB, mocked providers | pytest + httpx mock | `proxy/tests/test_<flow>.py` |
| **End-to-end** | Full request → DB → estimation → response | pytest with real SQLite | `proxy/tests/test_proxy_route.py` |
| **Latency** | Adds-no-overhead claim verified | `scripts/benchmark.py` | manual; recorded in PR description |
| **Manual smoke** | Things that automation cannot easily express (UX, dashboard rendering) | Streamlit + curl | recorded in PR description as a checklist |

Phases that do not produce code (pure documentation, branch-protection settings) skip the test layers and substitute a verification table with the API call that proves the change took effect.

### 4.3 Definition-of-done template

Every phase has a **Definition of done** subsection that is a checklist. Defaults that apply to every product/ML/infra phase:

- All subtasks have status `done`.
- All acceptance criteria checkboxes are checked.
- CI is green on the merge commit for every PR that contributed.
- The PR title(s) and commit subject(s) on `main` are single-line, lowercase, conventional, no trailers.
- Any new module under `proxy/` has tests covering at least the happy path and one error path.
- Any new public API surface (HTTP endpoint, SDK method) is documented in [`PRD.md`](../PRD.md) §5 (API contract) or [`README.md`](../README.md) (usage).
- The phase's section in this document has been updated with the actual landed PR numbers and dates.
- The Active phase pointer at the top of this document is advanced if appropriate.

Phases declare additional DoD items inline.

### 4.4 Rollback-plan template

Every phase declares the rollback path. Default options, in increasing order of cost:

1. **Feature flag flip** — preferred. Each new behaviour is gated on an env var or config key (`ESTIMATION_ENABLED`, etc.); flipping the flag returns to prior behaviour without redeploy.
2. **Revert PR** — `gh pr revert <num>` opened immediately on `main`; merged with the same squash conventions. Acceptable when the phase introduces no migration.
3. **Forward-fix PR** — when the bug is small and a revert would lose other useful work; only acceptable if the forward fix can ship within the same day.
4. **Migration rollback** — `alembic downgrade -1` plus a revert PR. Required when the phase added a column or table.

Each phase's rollback subsection picks one of these and documents what to do exactly.

---

## 5. Master phase ledger

This is the long section. Each phase has the same shape; copy it as a template when adding a new phase.

### Phase 0 — Foundation and local runtime (DONE)

**Goal.** Stand up the FastAPI repository skeleton, local-development workflow, and CI baseline so subsequent phases can ship features without re-litigating tooling.

**Type.** Product (foundational).

**Status.** `done` (closed 2026-04-07).

**PR refs.** [#14](https://github.com/ishrith-gowda/overage/pull/14) (merged 2026-04-07).

**PRD coverage.** Story 7 (skeleton — quickstart authentication endpoints exist; full <5min onboarding closed by Phase 1).

**Dependencies.** None.

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 0.1 | Bootstrap `pyproject.toml` with FastAPI + uvicorn + SQLAlchemy 2.0 async + httpx + structlog + Pydantic v2 | `pip install -e .` succeeds on Python 3.12 | done |
| 0.2 | Add `proxy/main.py` FastAPI app factory and `proxy/config.py` pydantic-settings | `uvicorn proxy.main:app` starts and `GET /health` returns 200 | done |
| 0.3 | Wire structlog with request-ID middleware in `proxy/middleware/request_id.py` | Each request log line includes `request_id` UUID4 | done |
| 0.4 | Define ORM models in `proxy/storage/models.py` matching PRD §4 | `from proxy.storage.models import User, APIKey, APICallLog, EstimationResult, DiscrepancyAlert` succeeds | done |
| 0.5 | Set up Alembic in `proxy/storage/migrations/` | `alembic upgrade head` builds the schema on a fresh SQLite | done |
| 0.6 | Auth endpoints `POST /v1/auth/register` and `POST /v1/auth/apikey` | Curl roundtrip returns a `ovg_live_…` key once and 401 thereafter for unknown keys | done |
| 0.7 | Custom exception hierarchy in `proxy/exceptions.py` | `OverageError` with subclasses; global FastAPI exception handler maps to `ErrorResponse` | done |
| 0.8 | First CI workflow `ci.yml` with lint + type-check + test jobs | Green on PR #14 | done |
| 0.9 | Makefile with `install-dev`, `lint`, `typecheck`, `test`, `run`, `migrate`, `check` | `make check` runs end-to-end locally | done |
| 0.10 | `README.md` quickstart that boots the proxy in <5 minutes | Timed by the maintainer; recorded in PR description | done |

**Test plan.**

- Unit: `proxy/tests/test_api.py::test_health_returns_healthy_when_db_reachable` and the auth happy/sad paths.
- Integration: implicit — `pytest proxy/tests/` boots the FastAPI test client and exercises the full router.
- Latency: not applicable yet (no provider call path).
- Manual smoke: `curl localhost:8000/health` after `make run`.

**Definition of done.**

- [x] All subtasks done.
- [x] PR #14 merged with green CI.
- [x] `make check` passes from a fresh clone.
- [x] Quickstart in `README.md` reproducible.
- [x] Section updated with PR ref and date.

**Rollback plan.** Not applicable. This phase is the floor; rollback would mean abandoning the project. If a foundational choice (e.g. SQLAlchemy 2.0 vs Tortoise) needs to change, it ships as a separate refactor PR with its own phase rather than reverting Phase 0.

**Related files.** `pyproject.toml`, `proxy/main.py`, `proxy/config.py`, `proxy/exceptions.py`, `proxy/storage/`, `proxy/middleware/request_id.py`, `proxy/api/auth.py`, `Makefile`, `.github/workflows/ci.yml`, `README.md`, `INSTRUCTIONS.md`.

**Risks (closed).**

- Pydantic v1 → v2 migration churn — mitigated by pinning v2 from the start.
- SQLAlchemy 1.4 vs 2.0 async patterns — mitigated by adopting 2.0 from the start.
- exFAT/USB volume venv breakage — mitigated by `--copies` venv flag and `make venv-fresh` (documented in `CONTRIBUTING.md`).

---

### Phase 1 — OpenAI SDK proxy path (DONE)

**Goal.** Route OpenAI Chat Completions calls (including o-series reasoning models) through the proxy so the client only changes the `base_url` of the OpenAI SDK. Forward request and response unmodified, record timing, extract reasoning-token usage, and return the unmodified response with `X-Overage-Request-Id` and `X-Overage-Latency-Added-Ms` headers.

**Type.** Product.

**Status.** `done` (closed 2026-04-07).

**PR refs.** [#15](https://github.com/ishrith-gowda/overage/pull/15) (merged 2026-04-07).

**PRD coverage.** Story 1 (full).

**Dependencies.** Phase 0.

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 1.1 | Implement `proxy/providers/base.py::BaseProvider` ABC with `forward_request`, `forward_streaming_request`, `extract_usage`, `get_model_from_response` | Subclassing the ABC and forgetting `forward_request` raises at import time | done |
| 1.2 | Implement `proxy/providers/openai.py::OpenAIProvider` | Forwards to `https://api.openai.com/v1/chat/completions` with `Authorization: Bearer <key>` | done |
| 1.3 | Implement `proxy/providers/registry.py::provider_registry` with `get(name) -> BaseProvider` | `provider_registry.get("openai")` returns `OpenAIProvider`; `get("nope")` raises `ValidationError` | done |
| 1.4 | Wire `POST /v1/proxy/{provider_name}` and `/v1/proxy/{provider_name}/chat/completions` in `proxy/api/routes.py::proxy_request` | `curl -X POST $BASE/v1/proxy/openai/chat/completions ...` returns the OpenAI response unmodified | done |
| 1.5 | Extract reasoning tokens from `response.usage.completion_tokens_details.reasoning_tokens` | Missing field defaults to 0; valid response yields the integer | done |
| 1.6 | Streaming SSE support via `forward_streaming_request` and `StreamingResponse` | `curl -N --no-buffer ...` shows event chunks; TTFT recorded | done |
| 1.7 | `X-Overage-Request-Id` and `X-Overage-Latency-Added-Ms` response headers populated | Round-trip script asserts headers exist | done |
| 1.8 | Background task `_record_and_estimate` writes `APICallLog` row | After a call, `GET /v1/calls` lists it | done |
| 1.9 | `scripts/benchmark.py` measures local roundtrip latency to `/health` | `make benchmark` prints p50/p99; goal: p50<5ms, p99<10ms on dev hardware | done |
| 1.10 | Quickstart in `README.md` shows OpenAI Python SDK with `base_url` redirect | Timed reproduction by maintainer | done |
| 1.11 | Unit tests `proxy/tests/test_openai_provider.py` | All cases covered: success, missing usage, missing reasoning_tokens, timeout, HTTP error | done |
| 1.12 | Integration test `proxy/tests/test_proxy_route.py::test_proxy_openai_*` | Mocked httpx returns canned response; full flow asserts correct headers and body | done |

**Test plan.**

- Unit: `proxy/tests/test_openai_provider.py` (12 cases).
- Integration: `proxy/tests/test_proxy_route.py` (full request → DB row → response).
- Latency: `scripts/benchmark.py --iterations 200` shows `p50<5ms p99<10ms` against `/health`. Provider RTT is dominated by the upstream provider.
- Manual smoke: `curl http://localhost:8000/v1/proxy/openai/chat/completions -H "X-API-Key: ..." -H "Authorization: Bearer $OPENAI_API_KEY" -d '{"model":"o3", ...}'` returns OpenAI's response with Overage headers prepended.

**Definition of done.**

- [x] All subtasks done.
- [x] PR #15 merged with green CI.
- [x] OpenAI Python SDK quickstart works end-to-end.
- [x] Latency benchmark recorded in PR description.

**Rollback plan.** Feature flag (`ESTIMATION_ENABLED=false`) disables the background estimation; the proxy still forwards. If the proxy itself is broken, revert PR #15. No migration ran in this phase.

**Related files.** `proxy/providers/base.py`, `proxy/providers/openai.py`, `proxy/api/routes.py`, `proxy/middleware/request_id.py`, `scripts/benchmark.py`, `proxy/tests/test_openai_provider.py`, `proxy/tests/test_proxy_route.py`, `README.md`.

**Risks (closed).**

- httpx streaming deadlock under specific provider chunking — mitigated by `forward_streaming_request` returning the byte chunks list rather than a live async iterator. Re-evaluate if memory pressure becomes an issue.
- OpenAI changing the reasoning-token field path — mitigated by `extract_usage` defaulting to 0 on missing fields and logging a warning, so the proxy never 500s on schema drift.

---

### Phase 2 — Anthropic parity, benchmark, latency docs (DONE)

**Goal.** Add Anthropic Messages-API parity to the proxy (extended thinking + thinking-token extraction), a wire-RTT benchmark, and a README latency section that explains the budget and how to measure it.

**Type.** Product.

**Status.** `done` (closed 2026-04-07).

**PR refs.** [#16](https://github.com/ishrith-gowda/overage/pull/16) (merged 2026-04-07).

**PRD coverage.** Story 2 (full); NFR latency budget documented.

**Dependencies.** Phase 1 (provider registry + proxy router).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 2.1 | Implement `proxy/providers/anthropic.py::AnthropicProvider` | Forwards to `https://api.anthropic.com/v1/messages` with `x-api-key` and `anthropic-version` headers | done |
| 2.2 | Wire OpenAI-style and Anthropic-style aliases on `/v1/proxy/{provider}/v1/messages` | Anthropic SDK with `base_url=http://localhost:8000/v1/proxy/anthropic` works without code changes | done |
| 2.3 | Extract thinking tokens from `response.usage.thinking_tokens` (when extended thinking enabled) | Missing field → 0; present field → integer | done |
| 2.4 | Profile TPS rates for Anthropic models in `proxy/constants.py` (claude-sonnet-4 and claude-3.5-sonnet at thinking on) | TPS table in `proxy/estimation/timing.py` covers all proxied models | done |
| 2.5 | Add `make benchmark` target wrapping `scripts/benchmark.py --iterations 200` | `make benchmark` prints summary stats | done |
| 2.6 | Document latency budget in `README.md` (link to `scripts/benchmark.py`) | README has "Latency benchmark (wire RTT)" section | done |
| 2.7 | Anthropic SDK quickstart in `README.md` | Curl + Python SDK examples both work | done |
| 2.8 | Unit + integration tests for Anthropic provider | `proxy/tests/test_*` includes Anthropic cases | done |

**Test plan.**

- Unit: extract_usage variants for thinking on/off, missing field, present field.
- Integration: `test_proxy_route.py::test_proxy_anthropic_*` with mocked httpx.
- Latency: `scripts/benchmark.py` re-run after Anthropic adapter added; same budget upheld.
- Manual smoke: `curl http://localhost:8000/v1/proxy/anthropic/v1/messages ...` returns Anthropic's response.

**Definition of done.**

- [x] All subtasks done.
- [x] PR #16 merged with green CI.
- [x] Anthropic SDK quickstart reproduces.
- [x] Benchmark p50<5ms / p99<10ms confirmed.

**Rollback plan.** Same as Phase 1 — flag-flip + revert PR. No migration.

**Related files.** `proxy/providers/anthropic.py`, `proxy/providers/registry.py`, `proxy/estimation/timing.py`, `proxy/constants.py`, `scripts/benchmark.py`, `Makefile` (benchmark target), `README.md`.

**Risks (closed).**

- Anthropic version-header mismatch (`anthropic-version: 2023-06-01` vs newer) — mitigated by forwarding whatever the client sent rather than rewriting it. Adapter is a pass-through.
- Streaming for thinking traces (longer-running than Chat Completions) — verified end-to-end in tests; budget upheld.

---

### Phase 3 — Calls list with estimation fields (DONE)

**Goal.** Surface per-call discrepancy data through `GET /v1/calls`. Each row now carries estimation fields when the background pipeline has run (and `null` placeholders when it has not), so the dashboard can render side-by-side reported-vs-estimated columns.

**Type.** Product.

**Status.** `done` (closed 2026-04-07).

**PR refs.** [#17](https://github.com/ishrith-gowda/overage/pull/17) (merged 2026-04-07).

**PRD coverage.** Story 3 (full); Story 5 (data layer — dashboard column added in Phase 5).

**Dependencies.** Phases 1 and 2 (provider proxying so there is data to list).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 3.1 | Add `EstimationResult` ORM model populated by background task | After a call, `EstimationResult` row exists with PALACE + timing fields | done |
| 3.2 | Wire `proxy/estimation/palace.py::PALACEEstimator.predict` (with optional `[ml]` extra) | When `[ml]` installed, returns mean + confidence interval; when not installed, returns deterministic placeholder so tests pass | done |
| 3.3 | Wire `proxy/estimation/timing.py::TimingEstimator.estimate` | Returns `(estimated_tokens, tps_used, r_squared)` from latency_ms × profiled TPS | done |
| 3.4 | Wire `proxy/estimation/aggregator.py::DiscrepancyAggregator.aggregate_single_call` | Combines PALACE + timing into one `combined_estimated_tokens` and a `discrepancy_pct` | done |
| 3.5 | Update `GET /v1/calls` response to include `estimated_reasoning_tokens`, `discrepancy_pct`, `timing_r_squared`, `timing_estimated_tokens`, `signals_agree`, `dollar_impact` | Each row carries those keys (or `null` if estimation has not run) | done |
| 3.6 | Update `GET /v1/calls/{id}` to return `estimation` object with full PALACE + timing detail | Response shape matches PRD §5 example | done |
| 3.7 | Dashboard call-detail page renders the estimation block | Manual screenshot in PR description | done |
| 3.8 | Unit + integration tests for aggregator and updated routes | `proxy/tests/test_aggregator.py`, `test_api.py::test_list_calls_includes_estimation_fields` | done |

**Test plan.**

- Unit: `test_aggregator.py` (signal combination, signal-agreement boundary at 20%), `test_timing.py` (TPS lookup, R² calc).
- Integration: `test_api.py::test_list_calls_includes_estimation_fields` after a call has been recorded.
- Manual smoke: dashboard call-detail view shows reported, palace estimate, timing estimate, combined, discrepancy.

**Definition of done.**

- [x] All subtasks done.
- [x] PR #17 merged with green CI.
- [x] Dashboard renders estimation columns.

**Rollback plan.** `ESTIMATION_ENABLED=false` flips off the background task; the calls list will return `null` estimation fields without breaking any consumer (clients are expected to handle `null` per PRD §5). Revert PR for code-level rollback. No migration in this phase.

**Related files.** `proxy/estimation/palace.py`, `proxy/estimation/timing.py`, `proxy/estimation/aggregator.py`, `proxy/api/routes.py`, `proxy/storage/models.py`, `dashboard/app.py`, `proxy/tests/test_aggregator.py`, `proxy/tests/test_timing.py`.

**Risks (closed).**

- PALACE inference hot-loop blocking the event loop — mitigated by lazy import of torch/transformers/peft in `proxy/estimation/palace.py` and running inference in a thread pool when `[ml]` is installed.
- Timing R² noisy on short responses — mitigated by computing R² over a sliding profiling window in `TimingEstimator.profile_update` rather than per-call.

---

### Phase 4 — Summary group_by, alerts, SDK fixes (DONE)

**Goal.** Aggregate the per-call data into provider/model breakdowns and dollar impact for FinOps personas, persist a `DiscrepancyAlert` data model so subsequent phases can build alerting on top, and fix the SDK auth headers + endpoint paths discovered during integration testing.

**Type.** Product.

**Status.** `done` (closed 2026-04-07).

**PR refs.** [#18](https://github.com/ishrith-gowda/overage/pull/18) (merged 2026-04-07).

**PRD coverage.** Story 4 (full); Story 8 (full); Story 9 (data model only — ack endpoint shipped in Phase 5, webhook delivery in Phase 15); Story 10 (full).

**Dependencies.** Phase 3 (per-call estimation).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 4.1 | Add `GET /v1/summary` returning `SummaryStats` (total_calls, total_reported, total_estimated, aggregate_discrepancy_pct, total_dollar_impact, avg_discrepancy_pct, honoring_rate_pct) | `_fetch_summary_stats` query in `proxy/api/routes.py` returns all fields | done |
| 4.2 | Add `group_by ∈ {provider, model, provider_model}` query parameter | Response shape becomes `{overall, groups: [SummaryGroupRow]}` when set | done |
| 4.3 | Add `GET /v1/summary/timeseries` returning `[{date, call_count, reported, estimated, discrepancy_pct, dollar_impact}]` | Daily aggregation by `date(timestamp)` over selected range | done |
| 4.4 | Compute `honoring_rate_pct` as % of calls where `reported ∈ [palace_low, palace_high]` | Verified against synthetic data via `scripts/demo_data.py` | done |
| 4.5 | Persist `DiscrepancyAlert` rows when sliding-window discrepancy exceeds threshold | After 50 calls with > 15% drift, `alert_status='active'` row exists | done |
| 4.6 | `GET /v1/alerts?status={active,acknowledged,resolved,all}` lists rows | Default `status=active`; filter works | done |
| 4.7 | Per-token pricing table in `proxy/constants.py` | Matches PRD Appendix A | done |
| 4.8 | SDK fix: `default_headers={"X-API-Key": OVERAGE_KEY}` for OpenAI + Anthropic clients | `sdk/overage/client.py` documented; integration test uses both SDKs | done |
| 4.9 | Tests for summary, group_by, alerts | `test_api.py::test_summary_*` + `test_aggregator.py::test_record_discrepancy_*` | done |

**Test plan.**

- Unit: `test_aggregator.py` for sliding-window math; `test_api.py` for `group_by` enumeration validation.
- Integration: full flow that creates 50 calls with synthetic discrepancies and verifies alert row appears.
- Manual smoke: dashboard renders the summary and group breakdown.

**Definition of done.**

- [x] All subtasks done.
- [x] PR #18 merged with green CI.
- [x] Demo data confirms honoring rate calculation matches expected %.

**Rollback plan.** No migration; revert PR. If only the alert subsystem needs disabling, set `DISCREPANCY_ALERT_THRESHOLD=999.0` so no row ever persists; the rest of the summary keeps working.

**Related files.** `proxy/api/routes.py` (summary, timeseries, alerts), `proxy/estimation/aggregator.py` (sliding window), `proxy/storage/models.py` (`DiscrepancyAlert`, `SummaryStats`, `SummaryGroupRow`), `proxy/constants.py` (pricing), `sdk/overage/client.py`.

**Risks (closed).**

- N+1 query risk in calls listing — mitigated by `selectinload(APICallLog.estimation)` in the `list_calls` route.
- SQLite vs Postgres date arithmetic differences — mitigated by `func.date(...)` which works on both.

---

### Phase 5 — Alert acknowledge, dashboard group chart, CI Docker+Trivy (DONE)

**Goal.** Close the alerting feedback loop with a `POST /v1/alerts/{id}/acknowledge` endpoint, render the per-provider/model breakdown as a chart on the dashboard, and start running container-vulnerability scans (Trivy) on every PR via the CI pipeline.

**Type.** Product (alert ack + dashboard) + Quality (CI Trivy).

**Status.** `done` (closed 2026-04-07).

**PR refs.** [#19](https://github.com/ishrith-gowda/overage/pull/19) (merged 2026-04-07).

**PRD coverage.** Story 9 (ack); Story 8 (dashboard chart).

**Dependencies.** Phase 4 (alert data model).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 5.1 | `POST /v1/alerts/{alert_id}/acknowledge` flips `alert_status` to `acknowledged` and stamps `acknowledged_at` | Idempotent: second call is a no-op; returns 404 for unknown id | done |
| 5.2 | Dashboard alert banner appears when active alerts exist | Manual screenshot confirms; vanishes when all are acknowledged | done |
| 5.3 | Dashboard group chart on summary page (Plotly bar chart per provider+model) | Renders for synthetic and real data | done |
| 5.4 | Container-vulnerability scanning via Trivy on every PR build | Trivy SARIF uploaded to GitHub Security tab | done |
| 5.5 | Integration test for ack endpoint and dashboard endpoint coverage | `test_api.py::test_acknowledge_alert_*` | done |

**Test plan.**

- Unit: ack idempotency.
- Integration: ack a non-existent id → 404; ack an existing id twice → first sets status, second is no-op.
- Manual smoke: dashboard banner appears/disappears.

**Definition of done.**

- [x] All subtasks done.
- [x] PR #19 merged with green CI.
- [x] Trivy SARIF visible on the GitHub Security tab.

**Rollback plan.** Trivy is non-blocking initially (`if: success()` upload); acking can be disabled by removing the route. No migration.

**Related files.** `proxy/api/routes.py::acknowledge_alert`, `dashboard/app.py` (banner, chart), `.github/workflows/ci.yml` (Trivy step), `proxy/tests/test_api.py`.

**Risks (closed).**

- Trivy upload could spam Security tab for known-low-impact deps — mitigated by `severity: CRITICAL,HIGH` filter so noise is gated.

---

### Phase 6 — PDF audit report, SDK, dashboard follow-ups (DONE)

**Goal.** Generate a downloadable PDF audit report for any date range so FinOps users have a vendor-shareable artefact, package the optional `[reporting]` extra (fpdf2 + matplotlib) so the proxy image stays slim by default, and round out SDK + dashboard polish that fell out of pilot dogfooding.

**Type.** Product.

**Status.** `done` (closed 2026-04-07).

**PR refs.** [#20](https://github.com/ishrith-gowda/overage/pull/20) (merged 2026-04-07).

**PRD coverage.** Story 6 (full).

**Dependencies.** Phase 4 (summary data feeds the PDF) and Phase 5 (alert ack — referenced in the report's "open issues" section).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 6.1 | `GET /v1/report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` returns `application/pdf` with `Content-Disposition: attachment` | Curl writes a parseable PDF to disk | done |
| 6.2 | Bundle loader `proxy/reporting/data.py::load_audit_report_bundle` aggregates the data needed | Pure-Python; tested with synthetic input | done |
| 6.3 | PDF renderer `proxy/reporting/pdf_audit.py::render_audit_pdf` produces a branded PDF with executive summary, methodology, per-provider table, top-20-discrepancy calls, time-series chart, methodology notes, and disclaimer | Sample PDF in `scripts/generate_report.py` | done |
| 6.4 | `[reporting]` optional dependency group: fpdf2 + matplotlib | `pip install ".[reporting]"` adds them; default install does not | done |
| 6.5 | SDK helper `sdk/overage/client.py::download_report(start_date, end_date, path)` | Writes the response to `path` | done |
| 6.6 | Dashboard "Download PDF" button | Triggers `GET /v1/report` for the current filter range | done |
| 6.7 | Tests `proxy/tests/test_reporting.py` (data + PDF generation, fixture-based) | Snapshot test of bundle dict + non-empty PDF byte stream | done |
| 6.8 | Date-range validation: `end_date >= start_date`, range ≤ 366 days | 422 returned otherwise | done |

**Test plan.**

- Unit: `test_reporting.py::test_load_audit_report_bundle_matches_fixture`, `test_render_audit_pdf_returns_non_empty_bytes`.
- Integration: `test_api.py::test_get_report_returns_pdf_for_valid_range`.
- Latency: not strictly enforced — PDF generation is on-demand and < 30s for 10k calls per PRD AC.
- Manual smoke: dashboard download button → PDF opens in default viewer.

**Definition of done.**

- [x] All subtasks done.
- [x] PR #20 merged with green CI.
- [x] Report renders for synthetic and real data.

**Rollback plan.** Remove the `report` route registration in `proxy/api/routes.py` (single import). The `[reporting]` extra is optional; uninstalling it disables the endpoint via lazy import that raises a clear `ModuleNotFoundError`.

**Related files.** `proxy/reporting/`, `proxy/api/routes.py::get_audit_report`, `sdk/overage/client.py`, `dashboard/app.py`, `scripts/generate_report.py`, `proxy/tests/test_reporting.py`, `pyproject.toml` (`[reporting]` extra).

**Risks (closed).**

- fpdf2 cell signature differences between versions — mitigated by `[[tool.mypy.overrides]] module = "proxy.reporting.pdf_audit" disable_error_code = ["arg-type", "import-untyped", "unused-ignore"]` so mypy stays strict on the rest of the module.
- matplotlib import cost (~600ms) added to lazy-import path in `pdf_audit.py` so the proxy startup is unaffected.

---

### Phase 7 — Quality Hardening / GitHub Hygiene (active)

**Goal.** Make the GitHub side of the project bulletproof: every check on every PR is green, every commit on `main` is single-line and machine-greppable, branch protection prevents drift, dependabot stays clean, and the agent + maintainer cannot accidentally inject trailers or multi-line bodies. This phase is the only one that legitimately ships across many small PRs because each subtask is independently revertable.

**Type.** Quality.

**Status.** `active` (started 2026-04-15; expected to close when subtasks 7.6 + 7.7 land in this PR; subtask 7.8 is optional and tracked separately).

**PR refs (rolling).** #32, #33, #44 (already merged); current PR contains 7.6 + 7.7.

**PRD coverage.** None directly — this phase is engineering hygiene that supports every other phase.

**Dependencies.** Phase 6 (because the hardening rewrite needs to land on a stable feature surface so the rewrite does not lose work).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion | Status |
|----|---------|----------------------|--------|
| 7.0 | All required CI checks green on `main` (Lint, Type Check, Test, Security Scan, Docker Build, CodeQL Analysis, Dependency Review, Commit Lint) | `gh pr checks <num>` all pass on the most recent merge | done |
| 7.1 | Branch protection on `main`: `required_status_checks.strict=true`, `required_linear_history=true`, `allow_force_pushes=false` (except short-lived 7.5 window), `required_conversation_resolution=true`, `enforce_admins=true` | `gh api repos/:owner/:repo/branches/main/protection` matches | done |
| 7.2 | Repo merge settings: `squash_merge_commit_title=PR_TITLE`, `squash_merge_commit_message=BLANK`, `delete_branch_on_merge=true`, `allow_merge_commit=false`, `allow_rebase_merge=false`, `allow_auto_merge=false` | `gh api repos/:owner/:repo` shows these values | done |
| 7.3 | `Commit Lint` workflow + `.gitmessage` template + stronger `prepare-commit-msg` hook + rewritten `CONTRIBUTING.md` | PR title format check passes/fails on every PR; trailers stripped locally | done |
| 7.4 | `dependabot.yml` cleanup so titles are `chore(deps): ...` not `chore(deps)(deps): ...` | Last 5 dependabot PRs have single-scope titles | done |
| 7.5 | Rewrite the 23 dirty commits between `bf748dc..pre-rewrite-2026-05-10` to single-line subjects, no body, no trailers | `git log main --since=2026-05-09 --pretty='%H %s%n%b'` shows only single-line subjects with no `Co-authored-by`/`Signed-off-by` | done |
| 7.6 | `make strip-trailers` + `workflow_dispatch` workflow (`.github/workflows/strip-trailers.yml`) lets the maintainer scrub future drift on `main` with one command | `make strip-trailers SINCE=<sha> REF=main` works dry-run; `gh workflow run strip-trailers.yml -f confirm=YES` re-runs the rewrite if needed | done (this PR) |
| 7.7 | Document the manual squash-merge process (no `--auto`, no UI "Update branch") in `CONTRIBUTING.md` | "PR Process" §7 explicitly forbids `--auto` and UI clicks; provides the exact `gh pr merge --subject "..." --body ""` form | done (this PR) |
| 7.8 | (Optional) Fine-grained PAT or GitHub App that lets a workflow auto-scrub trailers without the maintainer step | A PAT with `contents:write` + `administration:write` is in repo secrets; the strip-trailers workflow runs without `confirm=YES` gating | open |

**Test plan.**

- Verification: every subtask has a "how to prove it" command in the AC column. The `Commit Lint` workflow is itself the regression test for 7.3 going forward.
- No code tests — this phase is process work.
- Manual: maintainer reviews `gh pr list --state merged --limit 10` after the rewrite and confirms every subject is single-line.

**Definition of done.**

- [x] Subtasks 7.0–7.7 all `done` (7.5 already landed on `main`; 7.6 + 7.7 land in this PR).
- [x] Active phase pointer at the top of this document is updated to point to Phase 8 once 7.6 + 7.7 merge.
- [ ] Subtask 7.8 is explicitly tracked but not blocking. It moves to `done` when the PAT path is implemented; otherwise it stays `open` indefinitely without holding the phase open.
- [ ] Retrospective written into §11 (Revision history) when the phase closes.

**Rollback plan.**

- 7.0–7.4: revert PR.
- 7.5 (history rewrite): the safety tag `pre-rewrite-2026-05-10` (kept indefinitely) is the recovery point. To roll back: relax `allow_force_pushes` on `main`, `git push --force-with-lease origin pre-rewrite-2026-05-10:main`, restore protection. Do not delete the tag without explicit maintainer instruction.
- 7.6: drop `make strip-trailers` and the workflow. The hook + Commit Lint workflow remain as the daily safety net.

**Related files.** `.github/workflows/ci.yml`, `.github/workflows/security.yml`, `.github/workflows/commit-lint.yml`, `.github/workflows/strip-trailers.yml`, `.github/dependabot.yml`, `.githooks/prepare-commit-msg`, `.gitmessage`, `Makefile` (`strip-trailers` target), `scripts/strip_trailers.sh`, `CONTRIBUTING.md`, `INSTRUCTIONS.md`, this document.

**Risks (open).**

- **GitHub auto-injects trailers via UI** — open if a maintainer ever clicks "Enable auto-merge" or "Update branch". Mitigation is documented in `CONTRIBUTING.md`; recovery is `make strip-trailers`.
- **Force-push race** — small; `--force-with-lease` rejects if remote moved during the window. Documented in 7.5 procedure.
- **Subtask 7.8 deferred** — maintainer accepts that automatic post-merge cleanup remains a one-command manual step until the PAT lands.

---

### Phase 8 — Domains & DNS (planned)

**Goal.** Pick one canonical apex domain for Overage, delegate it to Cloudflare, set up the minimum DNS records (apex placeholder + reserved `api.` and `app.` subdomains), and wire `CORS_ORIGINS` so the dashboard can call the API once the proxy is deployed in Phase 11.

**Type.** Infra.

**Status.** `planned`.

**PR refs.** TBD (target: a single PR `feat(phase-8): cloudflare apex on overage.dev`).

**PRD coverage.** None directly; underpins Story 7 (5-minute onboarding for cloud users) once the cloud URL exists.

**Dependencies.** Phase 7 (so all subsequent infra PRs flow through clean CI). No code dependencies.

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 8.1 | Pick canonical apex domain. Default plan: `overage.dev`. Document the choice and the redirect plan for the other two owned domains (`overage.me` → 301 to apex; `overage.tech` → reserved for staging) | Choice recorded in this section + in `docs/DEV_INFRASTRUCTURE.md` account inventory |
| 8.2 | Add the apex to Cloudflare and delegate nameservers from name.com to Cloudflare | `dig NS overage.dev` returns Cloudflare nameservers; Cloudflare dashboard shows status `Active` |
| 8.3 | DNS minimum records: apex `A`/`CNAME` (placeholder until Phase 11), `CNAME api.overage.dev → <provider TBD>` reservation, `CNAME app.overage.dev → <provider TBD>` reservation | `dig` returns expected answers |
| 8.4 | TLS: enable Cloudflare Universal SSL with mode `Full (strict)` once Phase 11 deploys an origin with a valid cert; until then `Flexible` is documented as the chosen interim | Cloudflare dashboard shows the chosen mode; documented in this section |
| 8.5 | Update `CORS_ORIGINS` in Doppler `dev` to include `https://app.overage.dev` and `https://overage.dev` | `make secrets-verify` (or equivalent) confirms env var present |
| 8.6 | Update `docs/DEV_INFRASTRUCTURE.md` Phase 3 status to `done` and link here | Doc diff in PR |

**Test plan.**

- Verification only (no code change).
- Manual: `curl -I https://overage.dev` returns a Cloudflare-fronted response. `dig NS overage.dev` shows two Cloudflare NS records.

**Definition of done.**

- All subtasks `done`.
- DNS resolves from at least three external resolvers (Google 8.8.8.8, Cloudflare 1.1.1.1, Quad9 9.9.9.9) with consistent answers.
- `CORS_ORIGINS` value committed (env name only) to `.env.example`.
- This section status set to `done` and PR ref added.

**Rollback plan.** DNS-only changes are reversible by re-pointing nameservers back to the registrar default. TLS choice can be relaxed back to `Flexible` if Phase 11 origin certificate is delayed. Document the rollback procedure in the PR description.

**Related files.** `docs/DEV_INFRASTRUCTURE.md` (account inventory section), `.env.example` (`CORS_ORIGINS`), `proxy/config.py` (existing setting), this document.

**Risks.**

- Wrong domain chosen and abandoned later — mitigated by documenting the choice and the redirect plan; the other two domains stay registered but unused.
- Nameserver delegation propagation delay — mitigated by performing the change during low-traffic windows and validating across resolvers before declaring `done`.

**Open questions.**

- [ ] Which provider hostname will `api.overage.dev` `CNAME` to? Resolved in Phase 11.

---

### Phase 9 — Observability backbone (planned)

**Goal.** Wire structured-log shipping, error tracking, and product-analytics for the proxy so post-MVP debugging and customer-pilot analysis do not require log-into-the-server work. Keep cost ≈ $0 by leaning on Sentry (Education Team), Datadog (Student Pro), and PostHog (free tier).

**Type.** Infra.

**Status.** `planned`.

**PR refs.** TBD (target: `feat(phase-9): wire sentry+posthog and structlog shipping`).

**PRD coverage.** Underpins NFR §6 (Availability — "Database outage should not block proxying"; we need to detect that). No new product behaviour.

**Dependencies.** Phase 8 (so `*.overage.dev` exists for CORS / cookie work). Loosely depends on Phase 7 closure.

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 9.1 | Sentry FastAPI integration in `proxy/main.py` with `traces_sample_rate=0.1`, `profiles_sample_rate=0.1`, `environment=settings.environment` | Test by raising a controlled exception; event appears in Sentry dashboard |
| 9.2 | Sentry context tagging: `provider`, `model`, `user_id`, `request_id` set on every captured exception via the existing structlog binding | Sentry event detail shows tags |
| 9.3 | structlog → JSON output → stdout pipeline + (env-gated) ship-to-Datadog Log Management | Local dev: pretty console output; production: JSON to stdout; Datadog ingestion lag < 30s |
| 9.4 | PostHog client wired in dashboard for product analytics (opt-out via `POSTHOG_OPT_OUT=true`) | Dashboard page-view event reaches PostHog within 30s |
| 9.5 | Health-check enhancements: `GET /health` reports `database`, `palace_model`, `provider_reachability` per PRD §5 | All four sub-checks visible in JSON |
| 9.6 | Custom Datadog metrics: `overage.proxy.latency_added_ms`, `overage.proxy.requests_per_minute`, `overage.estimation.discrepancy_pct`, `overage.provider.error_rate` | Metrics visible in Datadog dashboard |
| 9.7 | Sentry rate limiter: only one event per (error_code, model) per minute to prevent flood | Synthetic test of 100 identical errors yields ≤ 60 Sentry events |
| 9.8 | Document rotation policy: how to disable Sentry/PostHog without losing local stdout logs | Section in `docs/DEV_INFRASTRUCTURE.md` |

**Test plan.**

- Unit: `test_main.py::test_sentry_integration_loaded_when_dsn_set` (no network).
- Integration: optional `pytest -m manual` test that hits a real Sentry dev DSN if `SENTRY_DSN` is set in the env.
- Manual smoke: trigger a 502 on the proxy, confirm Sentry receives it within 30s.

**Definition of done.**

- All subtasks `done`.
- Sentry, PostHog, Datadog have at least one received event in the last 24 hours.
- `make check` still green (no new lint errors from sentry-sdk/posthog/datadog imports).
- This section status set to `done`.

**Rollback plan.** All three integrations are config-gated by env var (`SENTRY_DSN`, `DATADOG_API_KEY`, `POSTHOG_API_KEY`). Unsetting any env var disables that integration without code change.

**Related files.** `proxy/main.py` (Sentry init), `proxy/config.py` (settings), `proxy/middleware/request_id.py` (context binding), `dashboard/app.py` (PostHog), `proxy/api/routes.py::get_health` (extended checks), `docs/DEV_INFRASTRUCTURE.md`.

**Risks.**

- Sentry quota exhaustion — mitigated by 9.7 rate limiter and `traces_sample_rate=0.1`.
- Datadog cost overrun if Pro Student plan is downgraded — mitigated by env-gated shipping; can disable shipping while keeping stdout logs.
- PII leaks via structlog context — mitigated by never binding raw prompt/answer; only hashes + lengths flow through context.

---

### Phase 10 — Production database and migrations (planned)

**Goal.** Move from SQLite-dev to managed PostgreSQL for staging and production, enforce that every model change ships as an Alembic migration, and add Postgres-specific table partitioning for `api_call_logs` (timestamp partition by month) so the table scales past a million rows without query-plan regression.

**Type.** Infra.

**Status.** `planned`.

**PR refs.** TBD (likely 2 PRs: `feat(phase-10): supabase postgres for dev/staging` and `feat(phase-10): partition api_call_logs by month`).

**PRD coverage.** Underpins NFR §6 (Scalability — "PostgreSQL handles 10K+ concurrent connections with pooling").

**Dependencies.** Phase 7 (clean CI). Loosely Phase 9 (observability — needed for Postgres slow-query monitoring).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 10.1 | Provision a Supabase Postgres project for `overage-dev` | Connection string in Doppler `dev` config (only) |
| 10.2 | Add `asyncpg` to default dependencies (already in `pyproject.toml`) and verify `DATABASE_URL=postgresql+asyncpg://...` works | `make migrate` runs against Postgres without error |
| 10.3 | Generate the initial Alembic migration set from current ORM models | `alembic upgrade head` on a fresh Postgres DB produces the same schema as SQLite |
| 10.4 | Postgres-specific column type adjustments: `JSONB` for `raw_usage_json`, indexed properly | `alembic check` passes; `EXPLAIN ANALYZE SELECT ... raw_usage_json @> '{"reasoning_tokens": 0}'::jsonb` uses GIN index |
| 10.5 | Partition `api_call_logs` by `RANGE (timestamp)` with monthly child tables, including a default partition | `EXPLAIN` on a date-bounded query touches only the relevant partitions |
| 10.6 | Connection pooling via PgBouncer (Supabase provides this) configured in `proxy/storage/database.py` (statement-mode pooling for asyncpg) | Pool stats visible in Datadog |
| 10.7 | Backup policy: Supabase auto-backup daily; document RPO/RTO | Documented in `docs/DEPLOYMENT.md` |
| 10.8 | CI matrix: tests run against both SQLite and Postgres | `.github/workflows/ci.yml` adds `services: postgres` |
| 10.9 | `make docker-up` includes a Postgres container so local dev does not need Supabase login | `docker compose up -d` starts proxy + dashboard + postgres |

**Test plan.**

- Unit: run existing test suite against Postgres (parametrised via `DATABASE_URL`).
- Integration: full `make test` against `services.postgres` in CI.
- Performance: `EXPLAIN ANALYZE` snapshots committed to `docs/DB_PLANS.md` for the most common queries (`list_calls`, `get_summary`, `get_timeseries`).
- Manual smoke: `make demo` against Postgres works.

**Definition of done.**

- All subtasks `done`.
- CI matrix is green on both SQLite and Postgres.
- Monthly partitions auto-created via a `pg_cron` job (or a maintenance worker) and documented.
- `docs/DEPLOYMENT.md` includes the Postgres section with backup/restore procedure.

**Rollback plan.** `DATABASE_URL` env var picks the backend at runtime. If Postgres causes regressions, point `DATABASE_URL` back at the SQLite dev DB. Drop the partitioned table by `alembic downgrade -1`. Production cutover is rehearsed on staging first (Phase 11).

**Related files.** `pyproject.toml`, `proxy/storage/database.py`, `proxy/storage/migrations/`, `proxy/config.py`, `Makefile` (`docker-up`), `docker-compose.yml`, `.github/workflows/ci.yml`.

**Risks.**

- Supabase region cold start — choose a region close to the deploy target (Phase 11).
- asyncpg+SQLAlchemy edge cases (composite primary keys, savepoints) — covered by full test suite running against Postgres.
- Partition maintenance forgotten and writes hitting the default partition — mitigated by monitoring the row-count of the default partition and alerting on unexpected growth.

---

### Phase 11 — Staging environment and continuous deploy (planned)

**Goal.** Run a staging deployment of the proxy that mirrors production topology (Cloudflare → DigitalOcean → Supabase), wire CD via GitHub Actions on `main` merge, and prove the production runbook with a controlled "promote staging → production" exercise.

**Type.** Infra.

**Status.** `planned`.

**PR refs.** TBD (1 PR for staging, 1 PR for production promotion runbook).

**PRD coverage.** Cloud-mode of Story 7 (the cloud URL becomes real).

**Dependencies.** Phase 8 (DNS), Phase 9 (observability), Phase 10 (Postgres).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 11.1 | Pick deploy target. Default plan: DigitalOcean App Platform (Docker) for staging; same for production | Decision recorded |
| 11.2 | Create staging app + production app in DigitalOcean | `doctl apps list` shows both |
| 11.3 | `.github/workflows/cd-api.yml` deploys to staging on `main` push, with manual gate to production | Push to `main` triggers staging; promote-to-prod is `workflow_dispatch` only |
| 11.4 | Cloudflare CNAME `api.overage.dev` → `<staging-app>.ondigitalocean.app`; flip to production app on promotion | DNS verified |
| 11.5 | TLS cert via Cloudflare (origin cert pinned on the App Platform side) | `curl https://api.overage.dev/health` returns 200 with valid cert |
| 11.6 | Smoke test in CD: after deploy, run `curl /health` and assert `{"status":"healthy"}` | Workflow fails the promote step on regression |
| 11.7 | Rollback step: `doctl apps update <app> --spec <previous-spec>` documented + tested | Rollback to the previous deployment succeeds within 5 minutes |
| 11.8 | Production-only env vars documented in `docs/DEPLOYMENT.md` (no secrets, just names) | Diff in PR |
| 11.9 | Sentry environment tagging: `staging` and `production` distinguished | Sentry event filters work per environment |
| 11.10 | Cost cap: alert on DigitalOcean spend > $50/mo combined | Alert configured |

**Test plan.**

- Verification: post-deploy smoke (curl-based) is the integration test.
- Performance: `scripts/benchmark.py` against `https://api.overage.dev/health` in staging confirms p50<5ms internally; cross-AZ latency may exceed 10ms — that is provider-side.
- Manual smoke: `curl https://api.overage.dev/v1/auth/register` end-to-end works.

**Definition of done.**

- All subtasks `done`.
- A change-control runbook is documented in `docs/DEPLOYMENT.md` with: commit → CI green → staging deploy → smoke → manual promote → production smoke → rollback path.
- At least one staged-then-promoted change has been performed.

**Rollback plan.** `doctl apps update <app> --spec <previous-spec>` rolls forward to the prior image; documented in 11.7. DNS rollback (re-point CNAME away from production app) is the nuclear option.

**Related files.** `.github/workflows/cd-api.yml`, `Dockerfile`, `proxy/config.py`, `docs/DEPLOYMENT.md`, `docs/DEV_INFRASTRUCTURE.md`.

**Risks.**

- App Platform rebuilds on every deploy and exceeds free-tier minutes — mitigated by Docker layer caching (already configured for CI; reuse for CD).
- Secret leakage via `doctl` config — mitigated by GitHub Actions secrets used in CD; no secrets on local laptop.
- Schema drift between staging and production — mitigated by running `alembic upgrade head` as part of the deploy step.

---

### Phase 12 — PALACE training and evaluation pipeline (planned)

**Goal.** Stand up the offline ML pipeline that trains and evaluates new PALACE LoRA weights, version weights with `palace_model_version`, and ship a reproducible "v0.2 → v0.3" upgrade path so the production proxy can roll new weights without code change.

**Type.** ML.

**Status.** `planned`.

**PR refs.** TBD (likely 3 PRs: training scaffold, evaluation harness, production-deploy of v0.2).

**PRD coverage.** Underpins Stories 3, 4, 8, 10 (better PALACE accuracy → more useful discrepancy data).

**Dependencies.** Phase 7 (clean CI). No code dependency on Phases 8–11; can run in parallel.

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 12.1 | Reproducible data-prep script under `model/data_prep.py` that builds the (prompt, answer, reasoning_tokens) training set | `python -m model.data_prep --output data/palace_v0_2.jsonl` produces a deterministic file |
| 12.2 | LoRA training script under `model/train.py` (Qwen2.5-1.5B base + LoRA adapters via PEFT) | `python -m model.train --config model/configs/v0_2.yaml --epochs 3` produces a checkpoint directory |
| 12.3 | Evaluation harness `model/evaluate.py` reporting Pass@1 at error thresholds {10%, 20%, 33%, 50%} on a held-out test set | `python -m model.evaluate --model models/palace-v0.2 --testset data/palace_test_v1.jsonl` writes `eval/v0_2.json` |
| 12.4 | Domain-stratified eval: Pass@1 per `domain_classification` (math_reasoning, code_generation, logical_reasoning, creative_writing, general_qa) | Results per domain in `eval/v0_2.json` |
| 12.5 | `.github/workflows/model-eval.yml` runs the eval harness on a CPU runner against a fixture test set when ML training PRs touch `model/` | Workflow uploads `eval/*.json` as artefact |
| 12.6 | Upload v0.2 weights to a model store (Hugging Face private repo or S3-compatible) | `hf download` or `aws s3 cp` retrieves the weights |
| 12.7 | Production cutover: bump `PALACE_MODEL_VERSION=v0.2` and `PALACE_MODEL_PATH` in Doppler; restart proxy | Health check shows `palace_model: loaded` with new version; Sentry shows zero exceptions for first 1000 estimations |
| 12.8 | A/B test capability (post-cutover): load v0.1 and v0.2 simultaneously and route N% to v0.2 (configurable via `PALACE_AB_PCT_V_NEW`) | Both versions appear in `EstimationResult.palace_model_version`; comparison query returns per-version metrics |

**Test plan.**

- Unit: `test_palace.py::test_predict_returns_estimate_with_confidence_interval` (no network, no GPU; uses mocked transformer).
- Integration: model-eval workflow runs the small fixture eval on every PR touching `model/`.
- Performance: eval harness reports inference latency p50/p99 per call.
- Manual smoke: production health check shows the new version after cutover.

**Definition of done.**

- All subtasks `done`.
- Eval shows v0.2 ≥ v0.1 on at least 4 of 5 domains.
- Rollback to v0.1 takes one Doppler env-var flip and a proxy restart (≤ 5 minutes).
- Documentation in `docs/ESTIMATION.md` updated with the v0.2 numbers.

**Rollback plan.** Set `PALACE_MODEL_VERSION` and `PALACE_MODEL_PATH` back to v0.1 values; restart proxy. Historical `EstimationResult.palace_model_version` is preserved for audit, so rollback does not lose the v0.2 estimations that did happen.

**Related files.** `model/data_prep.py`, `model/train.py`, `model/evaluate.py`, `model/configs/`, `proxy/estimation/palace.py`, `proxy/config.py` (`PALACE_MODEL_VERSION`, `PALACE_MODEL_PATH`), `.github/workflows/model-eval.yml`, `docs/ESTIMATION.md`.

**Risks.**

- Training cost on Colab/Chameleon — mitigated by pinning to the smallest base model (Qwen2.5-1.5B) and 3-epoch fine-tune; full training run < $5 on Colab Pro.
- Reproducibility drift between training environments — mitigated by `requirements-train.txt` with pinned versions and `model/configs/v0_2.yaml` checksum-checked in CI.
- v0.2 worse than v0.1 on a key domain — eval harness is the gate; do not promote.
- Confidence-interval calibration drift — mitigated by adding a calibration step (`model/calibrate.py`) that fits CI bounds against held-out data.

---

### Phase 13 — Gemini provider adapter (planned)

**Goal.** Add Google Gemini support so users with `gemini-2.0-flash-thinking` traffic can audit it through the same proxy and dashboard.

**Type.** Product.

**Status.** `planned`.

**PR refs.** TBD (`feat(phase-13): gemini provider adapter`).

**PRD coverage.** Promotes the "EXPLICITLY OUT" item to scheduled. Stories 1/2/3/4/5/8/10 extend automatically once the adapter exists.

**Dependencies.** Phase 7 (clean CI). No other code dependency. Loosely depends on Phase 12 (PALACE may need Gemini-domain calibration once Gemini traffic exists).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 13.1 | Implement `proxy/providers/gemini.py::GeminiProvider` | Forwards to `https://generativelanguage.googleapis.com/v1beta/models/...` |
| 13.2 | Extract `thoughts_token_count` from `response.usage_metadata.thoughts_token_count` per Google docs | Missing field → 0 |
| 13.3 | Add Gemini TPS rates to `proxy/constants.py` and `proxy/estimation/timing.py` | Documented; verified by `scripts/profile_tps.py` once an API key is available |
| 13.4 | Register adapter in `proxy/providers/registry.py` | `provider_registry.get("gemini")` returns the instance |
| 13.5 | Wire alias paths `/v1/proxy/gemini/v1beta/models/{model}:generateContent` matching the Gemini SDK shape | SDK roundtrip works |
| 13.6 | Streaming SSE support if Gemini exposes it for thinking models | Streaming roundtrip works |
| 13.7 | Tests `proxy/tests/test_gemini_provider.py` and integration in `test_proxy_route.py` | Coverage parity with OpenAI/Anthropic |
| 13.8 | README + docs/API.md updated with Gemini examples | Docs diff |
| 13.9 | `.env.example` includes `GEMINI_API_KEY` | File diff |

**Test plan.**

- Unit: extract_usage variants for Gemini; missing field; thinking off vs on.
- Integration: full proxy roundtrip with mocked httpx.
- Manual smoke: real Gemini API key roundtrip from local dev.

**Definition of done.**

- All subtasks `done`.
- Coverage parity with OpenAI/Anthropic adapters.
- Gemini quickstart in README.

**Rollback plan.** Remove the registry entry and the alias routes; revert PR. No migration.

**Related files.** `proxy/providers/gemini.py`, `proxy/providers/registry.py`, `proxy/api/routes.py` (alias path), `proxy/constants.py`, `proxy/estimation/timing.py`, `proxy/tests/test_gemini_provider.py`, `README.md`, `docs/API.md`, `.env.example`.

**Risks.**

- Gemini schema drift on `thoughts_token_count` (still beta) — mitigated by defaulting to 0 and logging a warning on missing fields.
- Different API path shapes vs OpenAI/Anthropic (model name in URL, not body) — mitigated by keeping the alias path `…/v1beta/models/{model}:generateContent`.

---

### Phase 14 — Multi-tenant isolation and RBAC (planned)

**Goal.** Make Overage safe to run for more than one customer at a time. Today every request is scoped by `user_id`; that is sufficient for solo-pilot usage but not for SaaS. This phase adds tenant scoping (a tenant owns N users), row-level security at the Postgres level, and role-based access control on dashboard endpoints (admin vs viewer vs auditor).

**Type.** Product (data model + API) + Infra (Postgres RLS).

**Status.** `planned`.

**PR refs.** TBD.

**PRD coverage.** Promotes the "EXPLICITLY OUT" item to scheduled when the second pilot is signed.

**Dependencies.** Phase 10 (production Postgres for RLS) and Phase 13 (loosely; want all providers shipped first so we are not migrating tenant scoping mid-feature).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 14.1 | Add `Tenant` ORM model and `tenant_id` FK to `User`, `APIKey`, `APICallLog`, `EstimationResult`, `DiscrepancyAlert` | Migration created and applied |
| 14.2 | Backfill existing data into a single "default" tenant | Migration data step preserves all existing rows |
| 14.3 | Row-level security policies in Postgres: every table has `USING (tenant_id = current_setting('overage.current_tenant')::int)` | `psql` test as a non-admin role only sees the current tenant's rows |
| 14.4 | Auth middleware sets `current_setting('overage.current_tenant', '<tenant_id>', false)` per request | Verified by integration test |
| 14.5 | Roles: `admin` (manage users + keys), `viewer` (read calls + summary), `auditor` (read calls + summary + reports). Stored on `User.role` | API endpoints enforce role |
| 14.6 | Tenant-scoped API key rotation: key revocation cascades within the tenant | Test |
| 14.7 | Dashboard tenant switcher (when a user belongs to multiple tenants) | UX manually verified |
| 14.8 | Tenant-aware audit log (who did what, when) | New `audit_log` table |

**Test plan.**

- Unit: role enforcement on each endpoint.
- Integration: cross-tenant access attempts return 404 (not 403, to avoid information leakage).
- Performance: confirm RLS does not regress query latency by more than 10% (EXPLAIN snapshots in `docs/DB_PLANS.md`).
- Manual: dashboard tenant switcher works.

**Definition of done.**

- All subtasks `done`.
- Two-tenant integration test passes.
- RLS policies are documented in `docs/SECURITY.md` (new file).

**Rollback plan.** Deferred-default migration: if RLS causes performance regression, the policies can be dropped without dropping the `tenant_id` column. Code path falls back to the existing `WHERE user_id = ...` filter. Worst case: `alembic downgrade -1` reverts the tenancy migration.

**Related files.** `proxy/storage/models.py`, `proxy/storage/migrations/`, `proxy/api/auth.py`, `proxy/api/routes.py` (role enforcement), `dashboard/app.py` (tenant switcher), `docs/SECURITY.md`.

**Risks.**

- Migration on production data — rehearsed on staging first; backup taken before applying.
- RLS performance — measured before merge.
- Breaking existing customer integrations during the cutover — single-tenant default backfill avoids any client-visible change.

---

### Phase 15 — Webhook delivery and alerting backend (planned)

**Goal.** Deliver `DiscrepancyAlert` notifications to user-configured webhooks (HTTPS POST with HMAC-signed body), with retry policy, dead-letter queue, and an optional Slack adapter as the first concrete recipient. Closes Story 9 fully.

**Type.** Product.

**Status.** `planned`.

**PR refs.** TBD.

**PRD coverage.** Story 9 (full closure).

**Dependencies.** Phase 9 (observability for retry telemetry), Phase 11 (staging for end-to-end webhook delivery testing). Optionally Phase 14 (tenant-scoped webhook configs).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 15.1 | `WebhookEndpoint` ORM model: `url`, `secret`, `events`, `is_active`, `tenant_id` (or `user_id` if Phase 14 not yet shipped) | Migration |
| 15.2 | `POST /v1/webhooks` to register; `GET /v1/webhooks` to list; `DELETE /v1/webhooks/{id}` to deactivate | Tested |
| 15.3 | Delivery worker that POSTs alert payload with `X-Overage-Signature: sha256=<hmac>` header | Recipient can verify HMAC with shared secret |
| 15.4 | Retry policy: exponential backoff at 1m / 5m / 30m / 2h; dead-letter after 4 failures | Verified by integration test with a flaky recipient |
| 15.5 | Dead-letter queue: failed deliveries listed via `GET /v1/webhooks/dead-letter`; manual re-drive endpoint | Tested |
| 15.6 | Slack adapter: `slack://<channel>` URL scheme rendered as a Slack-blocks payload | Manual verification with a real Slack workspace |
| 15.7 | Email adapter (Postmark or AWS SES via Marketplace): `mailto:` recipient registered as a webhook | Manual verification |
| 15.8 | Datadog metric `overage.webhook.delivery_latency_ms` and counter `overage.webhook.delivery_failures` | Visible in Datadog |
| 15.9 | Documentation in `docs/WEBHOOKS.md` (new file) with HMAC example in Python and Node | File diff |

**Test plan.**

- Unit: HMAC computation, retry-schedule math.
- Integration: webhook hits an in-process httpx mock that fails twice then succeeds; delivery succeeds on third attempt.
- Performance: delivery latency p99 < 5 seconds for healthy recipients.
- Manual: real Slack delivery.

**Definition of done.**

- All subtasks `done`.
- Documentation includes HMAC verification examples.
- At least one alert delivered end-to-end in staging.

**Rollback plan.** Disable delivery worker via `WEBHOOK_DELIVERY_ENABLED=false`. Existing rows persist; no data loss. Rollback PR removes routes.

**Related files.** `proxy/storage/models.py`, `proxy/api/routes.py` (`/v1/webhooks`), `proxy/webhooks/` (new package: `delivery.py`, `adapters/slack.py`, `adapters/email.py`), `docs/WEBHOOKS.md`.

**Risks.**

- Webhook recipient is slow → worker queue backs up — mitigated by per-endpoint concurrency limit and explicit timeout (5s connect + 10s read).
- HMAC secret leak — mitigated by shipping a per-endpoint secret (rotatable) and never logging the raw secret.
- Slack rate limits — mitigated by per-channel rate limit and graceful 429 backoff.

---

### Phase 16 — On-prem deployment package (planned)

**Goal.** Ship Overage as a deployable bundle that runs entirely inside a customer's VPC: Docker images, docker-compose, Kubernetes Helm chart, Terraform module for Postgres, and an air-gapped install path. No telemetry leaves the customer boundary.

**Type.** Infra + Product.

**Status.** `planned`.

**PR refs.** TBD.

**PRD coverage.** Promotes the "EXPLICITLY OUT" item once the first enterprise pilot signs an LOI.

**Dependencies.** Phase 11 (production deploy primitives), Phase 14 (tenant isolation), Phase 15 (webhook delivery — for in-VPC alerting).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 16.1 | Tagged Docker images on a public registry (ghcr.io) with reproducible tags `overage/proxy:v0.2.0`, `overage/dashboard:v0.2.0` | `docker pull` works; SBOM attached |
| 16.2 | docker-compose template `deploy/docker-compose.onprem.yml` for proxy + dashboard + postgres + GPU container for PALACE | `docker compose up` brings the stack up offline |
| 16.3 | Kubernetes Helm chart `deploy/helm/overage/` with values for image tag, secrets, ingress, GPU node selector | `helm install --dry-run` produces valid manifests |
| 16.4 | Terraform module `deploy/terraform/modules/overage-pg/` for Postgres provisioning (RDS or equivalent) | `terraform plan` succeeds |
| 16.5 | Air-gapped install bundle: `scripts/build_offline_bundle.sh` packages images + Helm chart + checksums into a tarball | Tarball verified on a fresh node without internet |
| 16.6 | Configuration flag `STORE_RAW_CONTENT=true` enables raw prompt/answer storage (off by default) | Documented; tested |
| 16.7 | Telemetry kill-switch: `OVERAGE_TELEMETRY_DISABLED=true` disables Sentry, Datadog, PostHog | Verified by absence of network egress |
| 16.8 | Customer-facing runbook `docs/ONPREM_DEPLOYMENT.md` (new file) | File diff |
| 16.9 | License/SLA template (legal — not in this repo) referenced from runbook | Link |

**Test plan.**

- Manual: end-to-end install on a Kubernetes cluster (kind or k3d) with no internet access.
- Integration: smoke tests the customer would run (`curl /health`, register user, send proxied request).
- Compliance: SBOM and provenance attestations attached to each image.

**Definition of done.**

- All subtasks `done`.
- A "fresh install" exercise has been performed and timed (< 30 minutes).
- Runbook is verified by a non-author.

**Rollback plan.** On-prem is customer-managed; rollback means publishing a previous image tag. Helm rollback `helm rollback overage <revision>` is the standard procedure.

**Related files.** `Dockerfile` (multi-stage already in place), `deploy/` (new directory: `docker-compose.onprem.yml`, `helm/`, `terraform/`), `scripts/build_offline_bundle.sh`, `docs/ONPREM_DEPLOYMENT.md`.

**Risks.**

- GPU availability in customer VPCs — mitigated by CPU-only PALACE inference fallback (slower but functional).
- Air-gapped install complexity — mitigated by pre-built tarball with checksums; SBOM signed.
- License terms not yet drafted — out of repo scope; tracked in business backlog.

---

### Phase 17 — Billing, Stripe, and metering (planned)

**Goal.** Stand up usage-based billing per the PRD §9 pricing model: free tier ≤ 1,000 audited calls/month, growth tier billed as % of monitored LLM spend, enterprise tier custom. Wire Stripe (or Stripe-compatible) for payment, persist a per-tenant meter, and surface the bill in the dashboard.

**Type.** Business + Product.

**Status.** `planned`.

**PR refs.** TBD.

**PRD coverage.** PRD §9 (full closure when this phase ships).

**Dependencies.** Phase 14 (tenant isolation — bills are per tenant), Phase 11 (production deploy).

**Subtasks and acceptance criteria.**

| ID | Subtask | Acceptance criterion |
|----|---------|----------------------|
| 17.1 | Stripe account provisioned (or via Vercel Marketplace if supported); products + price tiers defined | Stripe dashboard shows three products: free, growth, enterprise |
| 17.2 | `Tenant.subscription_id` and `Tenant.subscription_status` fields | Migration |
| 17.3 | Meter: per-tenant counter of audited calls per month | Visible in dashboard |
| 17.4 | Free-tier enforcement: 1,001st call in the month is allowed but logged as "over-quota" with a soft banner | Tested |
| 17.5 | Growth-tier metering: % of monitored LLM spend reported to Stripe via Usage Records API | Stripe invoice reflects monitored spend × percentage |
| 17.6 | Webhook handler `POST /v1/billing/stripe-webhook` validates signature and processes events (subscription.updated, invoice.paid, etc.) | Tested with Stripe CLI replay |
| 17.7 | Dashboard billing page: current period usage, bill estimate, plan upgrade CTA | Manual verification |
| 17.8 | Compliance: PCI scope reduced by never handling card data (Stripe-hosted checkout only) | Documented in `docs/SECURITY.md` |

**Test plan.**

- Unit: webhook signature validation, meter math.
- Integration: Stripe CLI replay of a `subscription.updated` event flips the tenant tier.
- Manual: end-to-end Stripe Checkout in test mode.

**Definition of done.**

- All subtasks `done`.
- Test-mode end-to-end works.
- Production cutover documented (separate from this phase's DoD; cutover happens once a paying customer is ready).

**Rollback plan.** `BILLING_ENABLED=false` disables enforcement; tenants stay on the free tier indefinitely. Stripe can be disconnected without code change. Rollback PR removes routes.

**Related files.** `proxy/storage/models.py` (Tenant fields), `proxy/api/billing.py` (new), `dashboard/pages/billing.py` (new), `docs/SECURITY.md`.

**Risks.**

- Pricing model rejected by early customers — mitigated by pilot conversations before this phase opens; the % model is well-understood from CloudZero/Vantage.
- Stripe webhook reliability — mitigated by idempotency keys and a dead-letter queue.
- VAT / tax compliance — out of repo scope; handled by Stripe Tax.

---

## 6. Cross-cutting workstreams

These workstreams are not phases — they apply across every phase as recurring obligations. Each workstream defines a checklist that the agent and reviewer should re-verify per PR.

### 6.1 Documentation hygiene

Every PR that changes behaviour or interface MUST update at least one of these files:

| Trigger | Required doc update |
|---------|---------------------|
| New HTTP endpoint | `PRD.md` §5 (API contract), `README.md` examples (if user-facing), `docs/API.md` |
| New ORM model or column | `PRD.md` §4 (data models), `ARCHITECTURE.md` ER diagram, Alembic migration |
| New environment variable | `INSTRUCTIONS.md` §14, `.env.example`, `docs/DEV_INFRASTRUCTURE.md` if it goes in Doppler |
| New phase opened or closed | This document (`docs/ROADMAP.md`) — Active phase pointer + the phase's section |
| Provider added | `proxy/providers/` files, `proxy/constants.py` (TPS rates), `README.md` quickstart, `docs/API.md` |
| Coding-pattern change | `INSTRUCTIONS.md` (the relevant section) |
| Workflow / merge process change | `CONTRIBUTING.md` and `INSTRUCTIONS.md` §9 |

The `Commit Lint` workflow does not enforce documentation — the reviewer does. The PR template asks "what docs were updated"; a missing answer blocks merge.

### 6.2 Security and vulnerability management

Every phase that changes dependencies, runtime, or surface area must pass:

- **Bandit** clean on `proxy/` (`bandit -r proxy/ -ll -ii --exclude proxy/tests` exit 0).
- **CodeQL** Analysis green (Python query suite).
- **Trivy** image scan green at `CRITICAL,HIGH` for the proxy image.
- **Dependency Review** action on every PR; advisories triaged within 7 days.
- **Safety** advisory check (advisory-only — does not block, but is reviewed weekly).
- **detect-secrets** baseline maintained; new secrets require explicit baseline update + rationale in PR.

Secret-rotation policy: any secret that ever appears in chat, screenshots, logs, or non-secret-store files is rotated immediately at the provider. Doppler is the source of truth; 1Password holds the human-readable backup ("Overage — Doppler dev snapshot").

### 6.3 Testing pyramid and coverage budget

The current floor (`pyproject.toml` and `Makefile`) is **55% line coverage on `proxy/`** with `--branch=true`. Floors per directory:

| Directory | Target coverage |
|-----------|-----------------|
| `proxy/api/` | ≥ 70% |
| `proxy/providers/` | ≥ 80% |
| `proxy/estimation/` | ≥ 70% (excludes optional `[ml]` import paths) |
| `proxy/storage/` | ≥ 50% (ORM definitions exercised via integration) |
| `proxy/reporting/` | ≥ 60% (PDF rendering covered by snapshot tests) |
| `dashboard/` | not in coverage scope (Streamlit) |
| `sdk/` | not in coverage scope (separate package) |

Test types per phase:

- **Unit** for every public function in a new module.
- **Integration** for every new HTTP endpoint and every cross-module flow.
- **End-to-end** for changes that touch the proxy hot path.
- **Performance** (`scripts/benchmark.py`) for any change to the proxy hot path.

When the floor cannot be met (legitimately — e.g., a phase that adds an interface but no implementation), the phase section explains the carve-out and includes a follow-up PR id that closes the gap.

### 6.4 Performance budgets

| Surface | Budget | How measured |
|---------|--------|--------------|
| Proxy critical path | p50 < 5ms, p99 < 10ms added latency | `scripts/benchmark.py --iterations 200` |
| Background estimation | < 5 seconds wall clock per call | structlog `palace_estimation_complete` event timing |
| `GET /v1/calls` | < 250ms p99 for 50-row response | Datadog APM (post-Phase 9) |
| `GET /v1/summary` | < 500ms p99 for 30-day window | Datadog APM |
| `GET /v1/report` (PDF) | < 30s p99 for 10k-call window | manual + Datadog |
| Dashboard initial render | < 3s for 1k-call view | manual |

Regressions are reported in PR descriptions. A PR that pushes a budget over its target requires explicit reviewer sign-off.

### 6.5 DevEx (Makefile, hooks, secrets)

`Makefile` is the single entry point for all common commands. Any PR adding tooling MUST surface it as a `make` target:

- Lint / format / typecheck / test: `make lint`, `make format`, `make typecheck`, `make test`, `make check`.
- Run: `make run`, `make run-dashboard`.
- Database: `make migrate`, `make migrate-generate MSG=...`.
- Secrets (Doppler): `make secrets-verify`, `make sync-env-to-doppler`, `make run-doppler`.
- History hygiene: `make strip-trailers SINCE=<sha> REF=main`.
- Docker: `make docker-build`, `make docker-up`, `make docker-down`, `make docker-logs`.
- Demo / scripts: `make demo`, `make seed`, `make benchmark`, `make profile-tps`, `make report`.

Local git hooks live in `.githooks/`. Activate once per clone: `git config core.hooksPath .githooks`. The `prepare-commit-msg` hook strips forbidden trailers (`Signed-off-by`, `Co-authored-by`, `Made-with`, `Generated-by`, `Reported-by`, `Reviewed-by`, `Tested-by`).

`.gitmessage` is the local commit-message template. Activate once per clone: `git config commit.template .gitmessage`.

### 6.6 Dependency hygiene

- **Dependabot** runs weekly with `prefix: chore(deps)` for runtime, `chore(deps-dev)` for dev, and `ci(deps)` for actions. No `(deps)(deps)` doubling (fixed in subtask 7.4).
- **Manual upgrades** only for: Python minor (3.12 → 3.13 — never), `fastapi`, `sqlalchemy`, `pydantic` major bumps. These ship as their own PRs.
- **Pin floor + open ceiling** (`>=X.Y,<MAJOR+1`) for runtime deps; pin tighter for security-relevant deps.

### 6.7 Branch protection invariants

These settings are validated on every Phase-7 review and recorded here so a reviewer can `gh api` them quickly:

```
gh api repos/ishrith-gowda/overage/branches/main/protection
```

Required values:

- `required_status_checks.strict`: `true`
- `required_status_checks.contexts`: `["Lint", "Type Check", "Test", "Security Scan", "Docker Build", "CodeQL Analysis", "Dependency Review", "PR Title (final squash subject)"]`
- `required_linear_history`: `true`
- `allow_force_pushes`: `false` (relax only for the 7.5 force-push window, then re-tighten)
- `allow_deletions`: `false`
- `required_conversation_resolution`: `true`
- `enforce_admins`: `true`
- `required_pull_request_reviews.required_approving_review_count`: `0` (solo dev; raise to ≥ 1 when a second contributor onboards)

Repo settings (`gh api repos/ishrith-gowda/overage`):

- `squash_merge_commit_title`: `PR_TITLE`
- `squash_merge_commit_message`: `BLANK`
- `delete_branch_on_merge`: `true`
- `allow_merge_commit`: `false`
- `allow_rebase_merge`: `false`
- `allow_auto_merge`: `false`

Drift detection: a quarterly `gh api` audit is logged in §11 (Revision history). If any value drifts, open a `chore` PR with the corrected setting.

---

## 7. Rituals and cadence

Even as a solo project, ritualised checkpoints prevent drift. These cadences are calibrated to one developer + dependabot + an occasional reviewer.

### 7.1 Per-PR ritual (the fastest loop)

Before pushing:

1. `make check` (lint + typecheck + test + security) — must be green.
2. `git log --pretty='%s%n%b' origin/main..HEAD` — every line that is not the subject must be empty (no body, no trailers).
3. `git push origin <branch>` — force-with-lease only if the branch was rebased.
4. Open PR with template filled in: what changed, why, how to test, docs updated.
5. Wait for CI (Lint, Type Check, Test, Security Scan, Docker Build, CodeQL, Dependency Review, Commit Lint) — all green.
6. Squash merge: `gh pr merge <num> --squash --subject "<exact PR title>" --body ""`. **Never** `--auto`. **Never** click UI "Update branch" or "Enable auto-merge" — both inject `Co-authored-by:` trailers.
7. Update `docs/ROADMAP.md` (this file): Active phase pointer if the phase advanced; the relevant phase's Status field; Recent landings table.

### 7.2 Per-day ritual (when actively delivering)

- Read the Active phase pointer at the top of this document.
- Pick the highest-priority `pending` subtask from the active phase.
- Open one PR for that subtask; do not bundle.
- At end of day, push WIP if multi-day; otherwise squash-merge and update §11.

### 7.3 Per-week ritual

- Triage open dependabot PRs. Merge security-only PRs first; group runtime upgrades.
- `gh pr list --state open` review: any PR > 7 days idle gets a comment or is closed.
- Skim `docs/DB_PLANS.md` (when Phase 10 lands) for slow-query alerts.
- Review Sentry "issues" tab (when Phase 9 lands).

### 7.4 Per-phase ritual (open and close)

**Opening a phase:**

1. Set the Active phase pointer to the new phase number.
2. Mark the phase Status `active` and stamp the start date.
3. Open the first subtask PR with title `<type>(phase-N): <subject>`.
4. Reference the phase id in the PR body.

**Closing a phase:**

1. Mark the phase Status `done` and stamp the close date in the phase's section + §11.
2. If a retrospective is warranted (anything that took >2× the estimated scope), write it in §11 next to the close entry.
3. Advance the Active phase pointer to the next unblocked phase.
4. Open the first subtask of the new phase (or document why it is `blocked`).

### 7.5 Per-quarter ritual

- Branch-protection drift audit (§6.7).
- Dependency-health sweep: anything pinned ≥ 6 months gets a major-version evaluation.
- PRD §6 NFRs re-checked: latency budget, availability, security posture.
- Glossary (§10) re-read for stale terminology.

---

## 8. Risk register

Top risks across the program, ordered by current priority. Each row carries: likelihood (L/M/H), impact (L/M/H), mitigation, owner (always the maintainer in this solo phase), and review-by date (next quarterly check unless a phase change supersedes).

| # | Risk | L | I | Mitigation | Owner | Review by |
|---|------|---|---|-----------|-------|-----------|
| R1 | OpenAI / Anthropic / Gemini change reasoning-token field path silently | M | H | `extract_usage` defaults to 0 + structlog warning; weekly canary call against each provider's reasoning model; alarm on missing fields | maintainer | next Phase 12 close |
| R2 | PALACE estimation accuracy degrades vs production traffic distribution | H | M | Eval harness on every model PR (Phase 12); domain-stratified Pass@1; calibration step refits CI bounds against last 30 days of production data | maintainer | Phase 12 |
| R3 | Provider rate-limits Overage's verification calls (if Phase 12 ever calls live providers for calibration) | L | M | Calibration data is sourced from real customer traffic post-anonymisation, not from synthetic provider calls | maintainer | Phase 12 |
| R4 | Branch protection accidentally relaxed (e.g., for emergency fix) and not re-tightened | L | H | §6.7 audit + post-PR check; Phase 7.6 cleanup workflow can scrub any drift | maintainer | quarterly |
| R5 | Dependency vulnerability in a runtime dep (`fastapi`, `httpx`, `sqlalchemy`, `pydantic`) | M | H | Dependabot weekly + Trivy + Safety advisory daily; security-patch PRs auto-approved when CI green and diff < 10 LOC | maintainer | quarterly |
| R6 | Force-push on `main` loses commits (the 7.5 manoeuvre) | L | H | `pre-rewrite-2026-05-10` safety tag held indefinitely; no further force-pushes allowed; `make strip-trailers` is opt-in only | maintainer | indefinite |
| R7 | PII leak via structlog or Sentry (raw prompt content in error messages) | L | H | Privacy contract: no raw prompt/answer in logs; only hash + length; PR review checks for `prompt_text` accidentally being logged | maintainer | Phase 9 |
| R8 | Cost overrun: Sentry / Datadog / DigitalOcean exceed Student Pack credits | M | M | Per-vendor cost cap alerts (Phase 9, Phase 11); fallback to free-tier alternatives documented | maintainer | Phase 11 |
| R9 | Dependabot ratelimits or auto-rebase accidentally injects trailers (the historical bug fixed in 7.4) | L | M | `dependabot.yml` has `include: scope` removed; squash settings `BLANK`; Commit Lint blocks bad PR titles; `make strip-trailers` cleans drift | maintainer | quarterly |
| R10 | A future maintainer reverts the squash-merge discipline | M | M | This document + `CONTRIBUTING.md` + `INSTRUCTIONS.md` all repeat the rule; the cleanup tooling makes recovery cheap | maintainer | onboarding doc |
| R11 | Postgres migration deadlock or downtime during Phase 10 cutover | L | H | Rehearse on staging first; `alembic upgrade head` is the only mutation; backup taken before applying; rollback procedure tested | maintainer | Phase 10 |
| R12 | On-prem customer reports an incident with no internet egress for support | L | M | Telemetry kill-switch documented (Phase 16); customer can email logs manually; SLA terms specify "best-effort with logs provided" | maintainer | Phase 16 |
| R13 | Pricing model rejected by early customers | M | H | Pilot conversations before Phase 17 opens; pricing inspired by CloudZero (proven model); free tier reduces entry friction | maintainer | Phase 17 |
| R14 | Webhook delivery worker queue grows unbounded under recipient outage | L | M | Per-endpoint concurrency cap; dead-letter queue (Phase 15); Datadog alarm on queue depth | maintainer | Phase 15 |
| R15 | Single-developer bus factor | H | H | Documentation density (this doc + INSTRUCTIONS + ARCHITECTURE + PRD) keeps the project self-explanatory; commit history is single-line and greppable; no tribal knowledge | maintainer | onboarding |

Risks closed since last revision:

- R-CLOSED-1: "Docker build hangs >60min in CI" — closed by adding `WORKDIR /build` and `--only-binary=:all:` to `numpy/scipy/scikit-learn` install (Phase 7.0).
- R-CLOSED-2: "Trivy scan double-builds the image" — closed by moving Trivy into the same job as Docker Build in `ci.yml` (Phase 5).
- R-CLOSED-3: "Codecov `report-type` schema invalid" — closed by switching to `report_type` snake_case (Phase 7.0).

---

## 9. Open questions

These are decisions deferred to a specific phase. Each row has a "decide-by" milestone so the question does not silently linger.

| # | Question | Phase that decides | Default if undecided |
|---|----------|--------------------|----------------------|
| Q1 | Which apex domain becomes canonical: `overage.dev`, `overage.me`, or `overage.tech`? | Phase 8 | `overage.dev` (matches product name and ownership) |
| Q2 | Cloudflare TLS mode: `Full (strict)` from day one, or `Flexible` until Phase 11 origin cert? | Phase 8 | `Flexible` interim → flip on Phase 11 deploy |
| Q3 | Production deploy target: DigitalOcean App Platform vs Railway vs Render vs Fly.io? | Phase 11 | DigitalOcean App Platform (Student Pack credits) |
| Q4 | Postgres host: Supabase managed vs self-hosted on the same DigitalOcean droplet? | Phase 10 | Supabase (less ops; generous free tier) |
| Q5 | Observability primary: Sentry only, vs Sentry + Datadog, vs Sentry + Datadog + PostHog? | Phase 9 | All three (each is independently free under Student Pack); evaluate at quarterly review |
| Q6 | PALACE v0.2 training infrastructure: Colab Pro vs Chameleon Cloud? | Phase 12 | Colab Pro (faster spin-up); fall back to Chameleon for longer runs |
| Q7 | Webhook delivery substrate: in-process worker vs Celery+Redis vs SQS? | Phase 15 | In-process worker for MVP; promote to Celery+Redis when alert volume > 100/day |
| Q8 | Multi-tenant scoping at DB level: Postgres RLS vs application-level filter only? | Phase 14 | Postgres RLS (defence in depth) |
| Q9 | Billing: Stripe direct vs Stripe via Vercel Marketplace? | Phase 17 | Stripe direct (no marketplace skim) |
| Q10 | On-prem licence: subscription with maintenance, or perpetual + maintenance separately? | Phase 16 (legal — outside repo) | subscription with maintenance (predictable revenue) |
| Q11 | Should `proxy/api/auth.py::register_user` switch from SHA-256 to bcrypt for password hashing before Phase 17? | Phase 17 (or earlier) | switch to bcrypt before any paying customer; tracked as a Phase 17 prerequisite |
| Q12 | Dashboard rewrite from Streamlit to Next.js? | Post-Phase 17 (when product UX becomes a sales axis) | keep Streamlit; user-research sign-off required to spend the migration |

When a question is decided, this row moves to the relevant phase's section and is removed from this list (with a forward link in §11).

---

## 10. Glossary

Sorted alphabetically for the reviewer's benefit.

- **Aggregator** — `proxy/estimation/aggregator.py::DiscrepancyAggregator`. Combines PALACE and timing estimates into a single combined estimate plus a discrepancy percentage.
- **Alembic** — Python database-migration tool used for SQLAlchemy. Migrations live in `proxy/storage/migrations/versions/`.
- **API key (Overage)** — opaque token of the form `ovg_live_<hex64>`. Returned once at generation, stored only as SHA-256 hash. Sent via `X-API-Key` header.
- **API key (provider)** — the customer's OpenAI / Anthropic / Gemini key. Forwarded by Overage to the upstream provider unmodified. Never stored.
- **Background task** — FastAPI `BackgroundTasks` runs after the proxy response is sent to the client. Used for `_record_and_estimate` to avoid blocking the critical path.
- **Branch protection** — GitHub setting on `main` that enforces required CI checks, linear history, no force pushes, and conversation resolution before merge.
- **Combined estimate** — weighted average of PALACE and timing estimates. Default weights: 0.7 PALACE, 0.3 timing. Stored as `EstimationResult.combined_estimated_tokens`.
- **Confidence interval** — `[palace_confidence_low, palace_confidence_high]`. Currently `[estimate × 0.85, estimate × 1.15]`; refined by Phase 12 calibration.
- **Conventional commits** — `<type>(scope?): <subject>` format. Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`, `perf`, `style`, `build`.
- **Critical path** — proxy receive → auth → forward → return. Latency budget: p50 < 5ms, p99 < 10ms added.
- **Dashboard** — Streamlit app at `dashboard/app.py`. Reads from the same database as the proxy.
- **Dependabot** — GitHub bot that opens PRs for dependency upgrades. Configured in `.github/dependabot.yml`.
- **Discrepancy %** — `(reported_reasoning_tokens − combined_estimated_tokens) / combined_estimated_tokens × 100`. Positive means provider over-reported.
- **Doppler** — secret-management vault. Project `overage`, config `dev`. Never put secrets in git.
- **Dollar impact** — `discrepancy_tokens × per-token-price`. Stored as `EstimationResult.dollar_impact`.
- **Estimation pipeline** — async chain: `PALACE.predict` + `Timing.estimate` → `Aggregator.aggregate_single_call` → `EstimationResult`.
- **fpdf2** — PDF rendering library used in `proxy/reporting/pdf_audit.py`. Optional `[reporting]` extra.
- **Honoring rate** — % of calls where `palace_confidence_low ≤ reported_reasoning_tokens ≤ palace_confidence_high`. Per provider and overall.
- **httpx** — async HTTP client. Replaces `requests` for async forwarding to providers.
- **LoRA** — Low-Rank Adaptation. Used to fine-tune Qwen2.5-1.5B for PALACE. Loaded via `peft`.
- **mypy strict** — type-checking mode enforced via `[tool.mypy] strict = true` in `pyproject.toml`. Required for `proxy/`.
- **PALACE** — Prompt And Language Assessed Computation Estimator. Framework for estimating reasoning tokens from a (prompt, answer) pair using a fine-tuned small LM. Reference: arXiv:2508.00912.
- **PR_TITLE / BLANK (squash settings)** — repo settings ensuring the squash commit subject equals the PR title and the body is empty.
- **Provider** — one of `openai`, `anthropic`, `gemini`. Each has an adapter in `proxy/providers/`.
- **Provider registry** — `proxy/providers/registry.py::provider_registry`. Maps provider name to instance.
- **Reasoning tokens** — hidden tokens generated by reasoning models (OpenAI o-series, Anthropic with extended thinking, Gemini Flash Thinking) but billed as output tokens. Reported in `usage.completion_tokens_details.reasoning_tokens` (OpenAI) or `usage.thinking_tokens` (Anthropic) or `usage_metadata.thoughts_token_count` (Gemini).
- **Request ID** — UUID4 generated by `proxy/middleware/request_id.py`. Bound to structlog context; propagated to background tasks; returned in `X-Overage-Request-Id`.
- **ruff** — Rust-implemented Python linter and formatter. Replaces flake8 + black + isort.
- **Signal agreement** — `True` when PALACE and timing estimates fall within 20% of each other.
- **structlog** — structured logging library. JSON output to stdout; context binding via `logger.bind(...)`.
- **Subtask** — numbered child of a phase (e.g., `7.5`). Subtasks ship as separate PRs in Phase 7 only.
- **Timing estimator** — `proxy/estimation/timing.py::TimingEstimator`. Converts response latency to estimated tokens via profiled TPS rates.
- **TPS** — Tokens Per Second. Profiled per model in `proxy/constants.py`. Updated via `scripts/profile_tps.py` and the live `TimingEstimator.profile_update`.
- **Trivy** — Aqua Security container vulnerability scanner. Runs in CI on the built proxy image.
- **TTFT** — Time To First Token. Measured for streaming responses to separate provider queuing from generation.
- **Trailers** — Git commit message lines like `Signed-off-by:`, `Co-authored-by:`, `Made-with:`. Forbidden on Overage commits; stripped by hook + workflow.

---

## 11. Revision history

This section records every material change to this document and the program. New entries append at the top.

| Date | Event | Detail |
|------|-------|--------|
| 2026-05-10 | **`docs/ROADMAP.md` consolidated to single source of truth** | Replaced the prior 108-line product-only roadmap with this 1500+ line ledger. Stripped the phase tables from `docs/DEV_INFRASTRUCTURE.md` so it remains the canonical *account/platform inventory* but no longer competes with this doc on phase numbering. Updated `CONTRIBUTING.md` reference to point at this section. PR ref: this PR. |
| 2026-05-10 | Phase 7.6 + 7.7 landed | `make strip-trailers` + `workflow_dispatch` workflow + `CONTRIBUTING.md` rewrite to forbid `--auto` and UI "Update branch". This PR. |
| 2026-05-10 | Phase 7.5 — history rewrite | Force-pushed `main` after rewriting 23 dirty commits between `bf748dc..pre-rewrite-2026-05-10`. Safety tag `pre-rewrite-2026-05-10` retained indefinitely. No PR (force-push). |
| 2026-05-10 | Phase 7.4 landed | Dependabot scope dedup. PR #44. |
| 2026-05-10 | Phase 7.3 landed | Commit Lint workflow + CONTRIBUTING rewrite. PR #33. |
| 2026-05-10 | Phase 7.0 landed | Cursor rules enforce CONTRIBUTING/INSTRUCTIONS workflow; CI green on `main`. PR #32. |
| 2026-04-15 | Phase 7 opened | Quality Hardening / GitHub Hygiene started. |
| 2026-04-07 | Phase 6 closed | PDF audit report + SDK + dashboard polish. PR #20. |
| 2026-04-07 | Phase 5 closed | Alert acknowledge + dashboard group chart + CI Trivy. PR #19. |
| 2026-04-07 | Phase 4 closed | Summary `group_by` + alerts + SDK fixes. PR #18. |
| 2026-04-07 | Phase 3 closed | Calls list with estimation fields. PR #17. |
| 2026-04-07 | Phase 2 closed | Anthropic SDK parity + benchmark + latency docs. PR #16. |
| 2026-04-07 | Phase 1 closed | OpenAI SDK proxy path + tests + quickstart. PR #15. |
| 2026-04-07 | Phase 0 closed | Foundation + local runtime + first CI workflow. PR #14. |
| 2026-04-07 | Phase 0 opened | Repository scaffold initialised. |

### Retrospectives

**Phase 7 (running retrospective).** The hardening track took ~25 days of calendar time across five PRs and one force-push. The main lesson is that GitHub's UI auto-injects `Co-authored-by:` trailers in three different ways (UI "Enable auto-merge", UI "Update branch", `gh pr merge --auto`), all of which override the repo `BLANK` setting. The only reliable path is the explicit `gh pr merge <num> --squash --subject "..." --body ""` form, documented in `CONTRIBUTING.md` §7. The strip-trailers tooling is the safety net for any human or bot that forgets.

**Phases 0–6 (closed retrospective).** The April sprint shipped seven phases in 24 hours of effective coding (the PR timestamps suggest dense same-day work). The lesson is that the agent + maintainer pair produced clean, single-line commits when the agent followed the `CONTRIBUTING.md` rules and produced messy commits when the agent improvised. Phase 7 exists because of the latter mode. The new Cursor rules (PR #32) bind the agent more tightly going forward.

**Pre-Phase-0 (closed retrospective).** The repository was bootstrapped on a USB / exFAT volume, which surfaced two unique failure modes: AppleDouble `._*` files breaking pip metadata, and venv symlinks breaking on copy. Both are documented in `CONTRIBUTING.md` and codified in `make venv-fresh` and `make git-usb-clean`. Future contributors on similar storage setups inherit the fixes.

---

*End of `docs/ROADMAP.md`. The next maintenance action is to advance the Active phase pointer at the top of this document to **Phase 8 — Domains & DNS** as soon as Phase 7 (this PR) merges.*

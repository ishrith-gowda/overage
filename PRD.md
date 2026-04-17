# PRD.md — Overage Product Requirements Document

> **Version:** 0.1.0 (MVP)
> **Author:** Ishrith Gowda
> **Last Updated:** March 31, 2026
> **Status:** Active Development — 8-day MVP sprint

---

## 1. PRODUCT VISION

Overage is the first independent audit layer for hidden LLM reasoning token billing. It provides enterprises spending $50K+/month on LLM APIs with cryptographically verifiable proof that the reasoning tokens they are billed for correspond to actual computation performed by the provider. By combining ML-based token count estimation with response timing analysis, Overage gives FinOps teams and AI platform engineers the confidence that their LLM bills reflect reality, not inflated numbers from providers with a structural incentive to over-report.

---

## 2. USER PERSONAS

### Persona 1: Alex Chen — Enterprise AI Platform Engineer

- **Role:** Senior Platform Engineer at a Series D fintech company (1,200 employees)
- **Responsibilities:** Manages the internal AI platform, routes all LLM API calls through a centralized gateway, monitors costs, ensures SLAs
- **Goals:**
  - Verify that OpenAI's reported reasoning token counts for o3/o4-mini are accurate
  - Get per-model, per-team breakdowns of LLM spending
  - Detect anomalies (sudden spikes in reasoning tokens that don't correlate with workload changes)
  - Maintain <10ms additional latency on the API call path
- **Pain Points:**
  - Cannot independently verify any provider-reported token counts
  - Monthly LLM bill increased 40% after switching to o3, but actual output quality didn't change proportionally
  - No existing tool (Stripe billing, CloudZero, Vantage) verifies token counts — they all pass through provider numbers
  - Reasoning tokens represent 85% of total billing but are completely opaque
- **How They Use Overage:**
  - Replaces the LLM API base URL in the centralized gateway config (1-line change)
  - Views per-model discrepancy reports on the dashboard daily
  - Sets up alerting for discrepancies exceeding 15%
  - Generates monthly PDF audit reports for the finance team

### Persona 2: Sarah Rodriguez — FinOps Lead / Head of AI Cost Management

- **Role:** Director of Cloud & AI Cost Management at a Fortune 500 insurance company
- **Responsibilities:** Reports to CFO on all cloud and AI spending, negotiates contracts with providers, tracks unit economics of AI features
- **Goals:**
  - Audit LLM bills for accuracy before approving payment
  - Identify which teams and use cases are generating the most reasoning tokens
  - Use independent verification data as leverage in contract negotiations with OpenAI/Anthropic
  - Demonstrate ROI: show the board that AI spending oversight exists
- **Pain Points:**
  - LLM bills arrive as a single line item with no breakdown of reasoning vs. non-reasoning tokens
  - Cannot explain to the CFO why the bill increased by $200K/month when feature usage was flat
  - No independent benchmark exists for "how many reasoning tokens should this query cost"
  - Current FinOps tools (CloudZero, Kubecost) only track infrastructure, not LLM token-level billing
- **How They Use Overage:**
  - Reviews the weekly discrepancy summary dashboard
  - Downloads PDF audit reports for quarterly finance reviews
  - Uses aggregate discrepancy data in vendor negotiation meetings
  - Monitors provider "honoring rate" (% of calls where reported tokens fall within the estimated confidence interval)

### Persona 3: David Park — VP Engineering / CTO

- **Role:** VP Engineering at a growth-stage AI company (400 employees, $5B valuation)
- **Responsibilities:** Technical strategy, build vs. buy decisions, vendor management, security posture
- **Goals:**
  - Ensure the company has a verifiable audit trail for all LLM spending
  - Avoid vendor lock-in by maintaining independent monitoring across OpenAI, Anthropic, and Gemini
  - Protect intellectual property (prompts and responses must not leave the company's infrastructure)
  - Establish trust-but-verify posture with AI providers
- **Pain Points:**
  - Board is asking for controls over AI spending, similar to cloud cost governance
  - No tool exists that works across multiple providers for token verification
  - Security team requires that any audit tool must be deployable on-prem (no prompts sent to third parties)
  - Current "AI cost tools" are glorified dashboards that just re-display provider numbers
- **How They Use Overage:**
  - Deploys the on-prem version within the company VPC
  - Reviews monthly aggregate reports showing provider accuracy rates
  - Uses Overage data to inform build vs. buy decisions (e.g., "OpenAI o3 costs 22% more than reported — should we switch to Anthropic?")
  - Presents independent verification data to the board as part of AI governance framework

---

## 3. USER STORIES WITH ACCEPTANCE CRITERIA

### Story 1: Route OpenAI API Calls Through Proxy

**As** an AI platform engineer,
**I want** to route my existing OpenAI API calls through Overage with a 1-line code change,
**So that** every reasoning model call is automatically audited without modifying my application logic.

**Acceptance Criteria:**
- [ ] Changing the OpenAI base URL from `https://api.openai.com/v1` to `https://proxy.overage.dev/v1/proxy/openai` (or localhost equivalent) routes all calls through Overage
- [ ] The proxy forwards the request to OpenAI with the original headers and body intact
- [ ] The proxy returns the OpenAI response to the client unmodified (same JSON structure, same status code)
- [ ] The proxy adds <10ms latency to the critical request/response path (measured via benchmark script)
- [ ] Non-streaming and streaming (SSE) requests are both supported
- [ ] The request is logged in the database with: provider, model, prompt hash, response length, reported token counts, total latency, TTFT
- [ ] If OpenAI returns an error (4xx, 5xx), the error is forwarded to the client as-is (Overage does not mask provider errors)

**Priority:** P0
**Sprint:** MVP

---

### Story 2: Route Anthropic API Calls Through Proxy

**As** an AI platform engineer,
**I want** to route Anthropic API calls through Overage,
**So that** extended thinking token usage is audited alongside OpenAI reasoning tokens.

**Acceptance Criteria:**
- [ ] POST `/v1/proxy/anthropic` forwards to `https://api.anthropic.com/v1/messages`
- [ ] Anthropic-specific headers (`x-api-key`, `anthropic-version`) are forwarded correctly
- [ ] `thinking_tokens` extracted from `response.usage.thinking_tokens` when extended thinking is enabled
- [ ] When extended thinking is not enabled, `thinking_tokens` is recorded as 0
- [ ] Same latency, logging, and error forwarding requirements as OpenAI proxy

**Priority:** P0
**Sprint:** MVP

---

### Story 3: View Reported vs. Estimated Reasoning Tokens Per Call

**As** a FinOps lead,
**I want** to see a side-by-side comparison of provider-reported reasoning tokens and Overage's independent estimate for every API call,
**So that** I can identify individual calls where the discrepancy is significant.

**Acceptance Criteria:**
- [ ] GET `/v1/calls` returns a paginated list of API calls with: id, provider, model, reported_reasoning_tokens, estimated_reasoning_tokens, discrepancy_pct, timestamp
- [ ] GET `/v1/calls/{id}` returns detailed call information including both PALACE and timing estimates, confidence intervals, and the raw usage JSON from the provider
- [ ] Dashboard shows a table of recent calls sortable by discrepancy percentage
- [ ] Calls with discrepancy above 15% are highlighted in the table
- [ ] Discrepancy percentage is calculated as: `(reported - estimated) / estimated * 100`

**Priority:** P0
**Sprint:** MVP

---

### Story 4: View Cumulative Discrepancy in Dollars Over Time

**As** a FinOps lead,
**I want** to see the cumulative dollar impact of reasoning token discrepancies over a configurable time period,
**So that** I can quantify the financial impact and present it to leadership.

**Acceptance Criteria:**
- [ ] GET `/v1/summary` returns: total_calls, total_reported_tokens, total_estimated_tokens, aggregate_discrepancy_pct, total_dollar_impact, avg_discrepancy_pct, provider_breakdown
- [ ] GET `/v1/summary/timeseries` returns daily aggregated data for charting: date, reported_tokens, estimated_tokens, discrepancy_pct, dollar_impact
- [ ] Dollar impact is calculated using the model's per-token pricing (stored in constants.py)
- [ ] Dashboard shows a time-series chart of cumulative dollar discrepancy
- [ ] Filterable by provider, model, and date range

**Priority:** P0
**Sprint:** MVP

---

### Story 5: View Timing Consistency Scores

**As** an AI platform engineer,
**I want** to see timing consistency scores that show how well response times correlate with reported token counts,
**So that** I have a second independent signal beyond the ML estimation.

**Acceptance Criteria:**
- [ ] Each EstimationResult includes: timing_estimated_tokens, timing_r_squared
- [ ] R-squared value indicates how well the response time predicts the reported token count using profiled TPS rates
- [ ] Dashboard shows timing consistency as a separate column in the call table
- [ ] Calls where timing and PALACE estimates diverge by >20% are flagged for review
- [ ] API response includes both estimates so clients can implement their own alerting

**Priority:** P1
**Sprint:** MVP

---

### Story 6: Generate PDF Audit Report

**As** a FinOps lead,
**I want** to generate a PDF audit report for a billing period,
**So that** I can share independent verification results with the finance team and auditors.

**Acceptance Criteria:**
- [ ] GET `/v1/report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` generates a PDF document
- [ ] Report includes: executive summary, methodology description, per-provider summary table, per-model breakdown, top 20 highest-discrepancy calls, time-series chart, confidence interval methodology, and data limitations disclaimer
- [ ] Report is branded with Overage logo and formatted professionally
- [ ] Response is `Content-Type: application/pdf` with appropriate `Content-Disposition` header
- [ ] Report generation completes in <30 seconds for up to 10,000 calls

**Priority:** P2
**Sprint:** Post-MVP

---

### Story 7: Add API Key and Start Routing in Under 5 Minutes

**As** a new Overage user,
**I want** to register, get an API key, and start routing traffic through the proxy in under 5 minutes,
**So that** I can evaluate Overage quickly without a long setup process.

**Acceptance Criteria:**
- [x] POST `/v1/auth/register` creates a new user with email + password
- [x] POST `/v1/auth/apikey` generates a new API key (returned once, stored as hash)
- [x] API key is passed via `X-API-Key` header on all subsequent requests
- [x] README quickstart can be completed in under 5 minutes (timed by a person unfamiliar with the project)
- [x] No credit card or payment required for initial evaluation

**Priority:** P0
**Sprint:** MVP

---

### Story 8: Per-Model, Per-Endpoint Breakdown of Discrepancies

**As** a VP Engineering,
**I want** to see discrepancy breakdowns per model (o3, o4-mini, claude-3.5-sonnet) and per endpoint (chat completions, assistants API),
**So that** I can identify which models and usage patterns have the highest billing inaccuracies.

**Acceptance Criteria:**
- [ ] Summary endpoint accepts `group_by` parameter: `provider`, `model`, or `provider,model`
- [ ] Response includes grouped aggregates: call_count, avg_discrepancy_pct, total_dollar_impact per group
- [ ] Dashboard shows a bar chart or heatmap of discrepancy by model
- [ ] Models with insufficient data (<10 calls) show a "low confidence" indicator

**Priority:** P1
**Sprint:** MVP

---

### Story 9: Set Alerting Threshold for Discrepancy

**As** an AI platform engineer,
**I want** to set a discrepancy threshold (e.g., 15%) and receive alerts when the aggregate discrepancy over a sliding window exceeds it,
**So that** I'm notified proactively instead of discovering billing issues after the fact.

**Acceptance Criteria:**
- [ ] DiscrepancyAlert model stores: window_start, window_end, aggregate_discrepancy_pct, dollar_impact, confidence_level, alert_status (active/acknowledged/resolved)
- [ ] System evaluates alerts on every Nth call (configurable, default N=50)
- [ ] When threshold is breached, a DiscrepancyAlert is created with status "active"
- [ ] GET `/v1/alerts` lists active alerts for the user
- [ ] Dashboard shows an alert banner when active alerts exist
- [ ] (Post-MVP) Webhook or email notification when alert fires

**Priority:** P2
**Sprint:** Post-MVP (data model in MVP, alerting logic post-MVP)

---

### Story 10: View Provider Honoring Rate

**As** a FinOps lead,
**I want** to see the percentage of API calls where provider-reported tokens fall within Overage's estimated confidence interval,
**So that** I have a single metric for "how honest is this provider."

**Acceptance Criteria:**
- [ ] Summary endpoint includes `honoring_rate_pct`: percentage of calls where `palace_confidence_low <= reported_reasoning_tokens <= palace_confidence_high`
- [ ] Honoring rate is calculated per-provider and overall
- [ ] Dashboard shows honoring rate as a prominent metric on the overview page
- [ ] If honoring rate drops below 80%, dashboard shows a warning indicator

**Priority:** P1
**Sprint:** MVP

---

## 4. DATA MODELS

### User

```
Table: users
├── id              SERIAL PRIMARY KEY
├── email           VARCHAR(255) UNIQUE NOT NULL
├── name            VARCHAR(255) NOT NULL
├── password_hash   VARCHAR(255) NOT NULL
├── created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
└── updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()

Indexes:
  - UNIQUE INDEX idx_users_email ON users(email)
```

### APIKey

```
Table: api_keys
├── id              SERIAL PRIMARY KEY
├── user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
├── key_hash        VARCHAR(64) NOT NULL    -- SHA-256 hash of the raw key
├── name            VARCHAR(255) NOT NULL   -- Human-readable name (e.g., "Production Key")
├── created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
├── last_used_at    TIMESTAMP WITH TIME ZONE
└── is_active       BOOLEAN NOT NULL DEFAULT TRUE

Indexes:
  - UNIQUE INDEX idx_api_keys_hash ON api_keys(key_hash)
  - INDEX idx_api_keys_user_id ON api_keys(user_id)

Constraints:
  - FK user_id → users.id ON DELETE CASCADE
```

### APICallLog

```
Table: api_call_logs
├── id                        SERIAL PRIMARY KEY
├── user_id                   INTEGER NOT NULL REFERENCES users(id)
├── provider                  VARCHAR(50) NOT NULL    -- "openai" | "anthropic" | "gemini"
├── model                     VARCHAR(100) NOT NULL   -- "o3" | "o4-mini" | "claude-3.5-sonnet" | etc.
├── endpoint                  VARCHAR(255) NOT NULL   -- "/v1/chat/completions" | "/v1/messages"
├── prompt_hash               VARCHAR(64) NOT NULL    -- SHA-256 hash of prompt (privacy: never store raw)
├── prompt_length_chars        INTEGER NOT NULL        -- Character count of prompt
├── answer_length_chars        INTEGER NOT NULL        -- Character count of answer
├── reported_input_tokens      INTEGER NOT NULL
├── reported_output_tokens     INTEGER NOT NULL
├── reported_reasoning_tokens  INTEGER NOT NULL DEFAULT 0
├── total_latency_ms           FLOAT NOT NULL          -- Total request-response time
├── ttft_ms                    FLOAT                   -- Time to first token (streaming only)
├── is_streaming               BOOLEAN NOT NULL DEFAULT FALSE
├── raw_usage_json             JSONB NOT NULL          -- Verbatim usage object from provider
├── timestamp                  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
└── request_id                 VARCHAR(64) NOT NULL    -- Unique request tracking ID

Indexes:
  - INDEX idx_call_logs_user_id ON api_call_logs(user_id)
  - INDEX idx_call_logs_timestamp ON api_call_logs(timestamp DESC)
  - INDEX idx_call_logs_provider ON api_call_logs(provider)
  - INDEX idx_call_logs_model ON api_call_logs(model)
  - INDEX idx_call_logs_user_provider ON api_call_logs(user_id, provider)
  - INDEX idx_call_logs_user_timestamp ON api_call_logs(user_id, timestamp DESC)

Constraints:
  - FK user_id → users.id
  - CHECK reported_reasoning_tokens >= 0
  - CHECK total_latency_ms > 0
```

### EstimationResult

```
Table: estimation_results
├── id                        SERIAL PRIMARY KEY
├── call_id                   INTEGER UNIQUE NOT NULL REFERENCES api_call_logs(id)
├── palace_estimated_tokens   INTEGER NOT NULL       -- PALACE model estimate
├── palace_confidence_low     INTEGER NOT NULL       -- Lower bound of confidence interval
├── palace_confidence_high    INTEGER NOT NULL       -- Upper bound of confidence interval
├── palace_model_version      VARCHAR(50) NOT NULL   -- e.g., "v0.1.0"
├── timing_estimated_tokens   INTEGER NOT NULL       -- Timing-based estimate
├── timing_tps_used           FLOAT NOT NULL         -- TPS rate used for estimation
├── timing_r_squared          FLOAT                  -- R² correlation score
├── combined_estimated_tokens INTEGER NOT NULL       -- Weighted combination of both signals
├── discrepancy_pct           FLOAT NOT NULL         -- (reported - combined_estimated) / combined_estimated * 100
├── dollar_impact             FLOAT NOT NULL DEFAULT 0.0  -- Estimated dollar impact of discrepancy
├── signals_agree             BOOLEAN NOT NULL       -- True if PALACE and timing agree within 20%
├── domain_classification     VARCHAR(100)           -- Prompt domain (math, code, reasoning, creative)
├── estimated_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()

Indexes:
  - UNIQUE INDEX idx_estimation_call_id ON estimation_results(call_id)
  - INDEX idx_estimation_discrepancy ON estimation_results(discrepancy_pct)
  - INDEX idx_estimation_estimated_at ON estimation_results(estimated_at DESC)

Constraints:
  - FK call_id → api_call_logs.id ON DELETE CASCADE
  - UNIQUE call_id (one estimation per call)
  - CHECK palace_confidence_low <= palace_estimated_tokens
  - CHECK palace_estimated_tokens <= palace_confidence_high
```

### DiscrepancyAlert

```
Table: discrepancy_alerts
├── id                        SERIAL PRIMARY KEY
├── user_id                   INTEGER NOT NULL REFERENCES users(id)
├── window_start              TIMESTAMP WITH TIME ZONE NOT NULL
├── window_end                TIMESTAMP WITH TIME ZONE NOT NULL
├── call_count                INTEGER NOT NULL        -- Number of calls in the window
├── aggregate_discrepancy_pct FLOAT NOT NULL
├── dollar_impact             FLOAT NOT NULL
├── confidence_level          VARCHAR(20) NOT NULL    -- "high" | "medium" | "low"
├── threshold_pct             FLOAT NOT NULL          -- The threshold that was breached
├── alert_status              VARCHAR(20) NOT NULL DEFAULT 'active'  -- "active" | "acknowledged" | "resolved"
├── acknowledged_at           TIMESTAMP WITH TIME ZONE
├── created_at                TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()

Indexes:
  - INDEX idx_alerts_user_id ON discrepancy_alerts(user_id)
  - INDEX idx_alerts_status ON discrepancy_alerts(alert_status)
  - INDEX idx_alerts_user_status ON discrepancy_alerts(user_id, alert_status)

Constraints:
  - FK user_id → users.id
  - CHECK alert_status IN ('active', 'acknowledged', 'resolved')
  - CHECK confidence_level IN ('high', 'medium', 'low')
  - CHECK window_start < window_end
```

---

## 5. API CONTRACT

### POST /v1/proxy/openai

Proxy an OpenAI API call through Overage.

- **Auth:** Required (X-API-Key header)
- **Rate Limit:** Per API key (default 100/min)

**Request:** Identical to OpenAI Chat Completions API. Pass-through.

```json
{
  "model": "o3",
  "messages": [
    {"role": "user", "content": "Solve: what is 2+2?"}
  ],
  "max_completion_tokens": 5000
}
```

**Response:** Identical to OpenAI response. Pass-through with additional header.

```
HTTP/1.1 200 OK
X-Overage-Request-Id: req_abc123
X-Overage-Latency-Added-Ms: 4.2

{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "o3",
  "choices": [...],
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 1500,
    "total_tokens": 1550,
    "completion_tokens_details": {
      "reasoning_tokens": 1200
    }
  }
}
```

**Error Codes:**
- 401: Invalid or missing API key
- 429: Rate limit exceeded
- 502: OpenAI returned an error
- 504: OpenAI request timed out

---

### POST /v1/proxy/anthropic

Proxy an Anthropic API call through Overage.

- **Auth:** Required (X-API-Key header)
- **Rate Limit:** Per API key (default 100/min)

**Request:** Identical to Anthropic Messages API. Pass-through.

```json
{
  "model": "claude-sonnet-4-20250514",
  "max_tokens": 16000,
  "thinking": {"type": "enabled", "budget_tokens": 10000},
  "messages": [{"role": "user", "content": "Analyze this code..."}]
}
```

**Response:** Identical to Anthropic response. Pass-through.

**Anthropic-Specific Headers Forwarded:**
- `x-api-key` → Anthropic's auth header
- `anthropic-version` → API version header

**Thinking Token Location:** `response.usage.thinking_tokens`

---

### POST /v1/proxy/gemini

Proxy a Google Gemini API call through Overage.

- **Auth:** Required (X-API-Key header)

**Thinking Token Location:** `response.usage_metadata.thoughts_token_count`

---

### GET /v1/calls

List API calls for the authenticated user.

- **Auth:** Required

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `provider` | string | No | — | Filter by provider |
| `model` | string | No | — | Filter by model |
| `start_date` | date | No | 30 days ago | Start of date range |
| `end_date` | date | No | today | End of date range |
| `min_discrepancy_pct` | float | No | — | Only calls above this discrepancy |
| `limit` | int | No | 50 | Results per page (max 200) |
| `offset` | int | No | 0 | Pagination offset |

**Response:**

```json
{
  "calls": [
    {
      "id": 1,
      "provider": "openai",
      "model": "o3",
      "reported_reasoning_tokens": 10000,
      "estimated_reasoning_tokens": 8200,
      "discrepancy_pct": 21.95,
      "dollar_impact": 0.036,
      "signals_agree": true,
      "timestamp": "2026-03-31T12:00:00Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

---

### GET /v1/calls/{id}

Get detailed information about a specific API call.

- **Auth:** Required

**Response:**

```json
{
  "id": 1,
  "provider": "openai",
  "model": "o3",
  "endpoint": "/v1/chat/completions",
  "prompt_hash": "a1b2c3...",
  "prompt_length_chars": 1500,
  "answer_length_chars": 3200,
  "reported_input_tokens": 50,
  "reported_output_tokens": 1500,
  "reported_reasoning_tokens": 10000,
  "total_latency_ms": 18500.0,
  "ttft_ms": 1200.0,
  "is_streaming": false,
  "raw_usage_json": { "...original provider usage object..." },
  "timestamp": "2026-03-31T12:00:00Z",
  "request_id": "req_abc123",
  "estimation": {
    "palace_estimated_tokens": 8200,
    "palace_confidence_low": 7800,
    "palace_confidence_high": 8600,
    "palace_model_version": "v0.1.0",
    "timing_estimated_tokens": 8525,
    "timing_tps_used": 55.0,
    "timing_r_squared": 0.992,
    "combined_estimated_tokens": 8350,
    "discrepancy_pct": 19.76,
    "dollar_impact": 0.033,
    "signals_agree": true,
    "domain_classification": "math_reasoning",
    "estimated_at": "2026-03-31T12:00:05Z"
  }
}
```

**Error Codes:**
- 401: Invalid API key
- 404: Call not found or does not belong to this user

---

### GET /v1/summary

Get aggregate discrepancy statistics.

- **Auth:** Required

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | date | No | 30 days ago | Start of date range |
| `end_date` | date | No | today | End of date range |
| `provider` | string | No | — | Filter by provider |
| `model` | string | No | — | Filter by model |
| `group_by` | string | No | — | Group by: `provider`, `model`, or `provider,model` |

**Response:**

```json
{
  "total_calls": 5432,
  "total_reported_reasoning_tokens": 54320000,
  "total_estimated_reasoning_tokens": 45890000,
  "aggregate_discrepancy_pct": 18.37,
  "total_dollar_impact": 1684.00,
  "avg_discrepancy_pct": 15.2,
  "honoring_rate_pct": 72.4,
  "provider_breakdown": [
    {
      "provider": "openai",
      "model": "o3",
      "call_count": 3200,
      "avg_discrepancy_pct": 19.8,
      "dollar_impact": 1200.00,
      "honoring_rate_pct": 68.5
    },
    {
      "provider": "anthropic",
      "model": "claude-sonnet-4-20250514",
      "call_count": 2232,
      "avg_discrepancy_pct": 8.1,
      "dollar_impact": 484.00,
      "honoring_rate_pct": 81.2
    }
  ],
  "period": {
    "start_date": "2026-03-01",
    "end_date": "2026-03-31"
  }
}
```

---

### GET /v1/summary/timeseries

Get daily aggregated data for time-series charting.

- **Auth:** Required

**Query Parameters:** Same as GET /v1/summary.

**Response:**

```json
{
  "data": [
    {
      "date": "2026-03-01",
      "call_count": 180,
      "reported_reasoning_tokens": 1800000,
      "estimated_reasoning_tokens": 1520000,
      "discrepancy_pct": 18.4,
      "dollar_impact": 56.00,
      "honoring_rate_pct": 71.1
    },
    {
      "date": "2026-03-02",
      "call_count": 195,
      "...": "..."
    }
  ],
  "period": {
    "start_date": "2026-03-01",
    "end_date": "2026-03-31"
  }
}
```

---

### GET /v1/report

Generate a PDF audit report.

- **Auth:** Required

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | date | Yes | — | Report start date |
| `end_date` | date | Yes | — | Report end date |
| `format` | string | No | `pdf` | Output format: `pdf` or `json` |

**Response:** `application/pdf` binary stream with `Content-Disposition: attachment; filename="overage-audit-2026-03.pdf"`

**Error Codes:**
- 401: Invalid API key
- 422: Invalid date range

---

### POST /v1/auth/register

Create a new Overage user account.

- **Auth:** Not required

**Request:**

```json
{
  "email": "alex@company.com",
  "name": "Alex Chen",
  "password": "securepassword123"
}
```

**Response:**

```json
{
  "id": 1,
  "email": "alex@company.com",
  "name": "Alex Chen",
  "created_at": "2026-03-31T12:00:00Z"
}
```

**Validation Rules:**
- email: valid email format, unique
- name: 1-255 characters
- password: minimum 8 characters

**Error Codes:**
- 409: Email already registered
- 422: Validation error

---

### POST /v1/auth/apikey

Generate a new API key for the authenticated user.

- **Auth:** Required (existing API key or session token)

**Request:**

```json
{
  "name": "Production Key"
}
```

**Response:**

```json
{
  "key": "ovg_live_abc123def456...",
  "name": "Production Key",
  "created_at": "2026-03-31T12:00:00Z",
  "note": "This key will only be shown once. Store it securely."
}
```

The raw key is returned exactly once. Only the SHA-256 hash is stored.

---

### GET /health

Health check endpoint. No auth required.

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-03-31T12:00:00Z",
  "checks": {
    "database": "ok",
    "palace_model": "loaded",
    "openai_reachable": true,
    "anthropic_reachable": true
  }
}
```

If any check fails:

```json
{
  "status": "degraded",
  "version": "0.1.0",
  "timestamp": "2026-03-31T12:00:00Z",
  "checks": {
    "database": "ok",
    "palace_model": "not_loaded",
    "openai_reachable": true,
    "anthropic_reachable": false
  }
}
```

---

## 6. NON-FUNCTIONAL REQUIREMENTS

### Latency
- The proxy MUST add <10ms to the critical request-response path
- This means: receive request → validate auth → forward to provider → return response
- All estimation, logging, and storage happen asynchronously via background tasks AFTER the response is sent
- Measured via `scripts/benchmark.py`: 100 sequential requests, p50 < 5ms, p99 < 10ms overhead

### Availability
- Target: 99.9% uptime for the proxy endpoint
- Proxy is stateless: if one instance fails, traffic routes to another
- Database outage should not block proxying (degrade gracefully: proxy without recording)
- Model not loaded should not block proxying (degrade gracefully: proxy without estimation)

### Security
- All communication over HTTPS (enforced via Cloudflare)
- API key authentication on all non-health endpoints
- API keys are hashed with SHA-256 before storage (raw key never persisted)
- Rate limiting: 100 requests/minute/API key (configurable)
- No prompt or response content is stored in cloud mode (only metadata: hashes, lengths, token counts)
- On-prem mode: prompts/responses may be stored locally per customer policy
- CORS: configurable allowed origins (default: dashboard URL only)
- SQL injection: prevented by SQLAlchemy ORM (no raw SQL)
- Secret scanning: detect-secrets pre-commit hook

### Scalability
- Proxy is stateless: horizontal scaling via load balancer
- Database: PostgreSQL handles 10K+ concurrent connections with pooling
- Estimation pipeline: background tasks run in the same process for MVP; can be extracted to Celery/Redis for scale
- Model inference: single GPU instance for MVP; can be scaled to vLLM/TGI cluster

### Privacy
- Cloud mode: NEVER store raw prompts or responses. Only: prompt hash (SHA-256), prompt length (chars), answer length (chars), token counts
- On-prem mode: all data stays within customer VPC, storage policy configurable
- No data is sent to Overage servers in on-prem mode
- GDPR: user can request deletion of all their data via API (POST /v1/auth/delete-account, post-MVP)

---

## 7. MVP SCOPE

### IN (8-day sprint)

1. **FastAPI proxy server** with OpenAI and Anthropic adapters
2. **Request forwarding** with <10ms overhead (non-streaming + streaming SSE)
3. **Usage extraction** from provider responses (including reasoning/thinking tokens)
4. **Timing recording** (total latency, TTFT for streaming)
5. **Background estimation pipeline** (PALACE model + timing analysis)
6. **Signal aggregation** (combine PALACE + timing, compute discrepancy %)
7. **SQLite database** with all data models via SQLAlchemy + Alembic
8. **API endpoints:** proxy (OpenAI + Anthropic), calls listing, call detail, summary, health
9. **Auth:** user registration, API key generation, API key validation middleware
10. **Streamlit dashboard v0:** overview page with metrics, call table, time-series chart
11. **demo_data.py script** for generating synthetic discrepancy data at zero API cost
12. **CI/CD pipeline:** ruff, mypy, pytest, bandit in GitHub Actions
13. **Docker support:** Dockerfile + docker-compose for local development
14. **README with quickstart** that can be followed in <5 minutes

### EXPLICITLY OUT (with reasons)

| Feature | Reason |
|---------|--------|
| **Gemini provider adapter** | Only 2 providers needed for demo credibility. Gemini is third priority. |
| **PDF report generation** | Nice-to-have for FinOps persona but not needed for demo or pilot. |
| **Alerting system** | Data model will exist, but alerting logic and notifications are post-MVP. |
| **On-prem deployment automation** | Enterprise deployment is a sales conversation, not a demo requirement. |
| **User management UI** | API-only auth is sufficient for MVP. Dashboard can be added later. |
| **Webhook notifications** | Requires external infrastructure. Post-MVP. |
| **Multi-tenant isolation** | Single-tenant is sufficient for MVP. Tenant isolation is architectural, already designed. |
| **Model A/B testing** | Requires multiple model versions. Post-MVP once v0.1 baseline is established. |
| **Caching layer** | Premature optimization. Add when latency testing shows need. |
| **Email verification** | Not needed for pilot users who are hand-onboarded. |
| **Rate limiting per endpoint** | Global per-key rate limit is sufficient for MVP. |

---

## 8. SUCCESS METRICS

### Technical Metrics (must be demonstrated in the April 6 demo)

| Metric | Target | How Measured |
|--------|--------|--------------|
| Proxy latency overhead | p50 < 5ms, p99 < 10ms | `scripts/benchmark.py` |
| Estimation completion time | < 5 seconds async | Timing logs in structlog output |
| API throughput | 500+ calls processed without error | Load test script |
| Test coverage | > 80% line coverage | pytest-cov report |
| CI pipeline | Green on every merge to main | GitHub Actions status |
| Dashboard load time | < 3 seconds for 1000 calls | Streamlit metrics |

### Business Metrics (targets for the next 30 days)

| Metric | Target | How Measured |
|--------|--------|--------------|
| Validation conversations | 5+ conversations with potential customers | Tracked manually |
| Pilot users | 1+ company routing real traffic through proxy | Usage in database |
| Letters of intent | 1+ LOI from a pilot user | Signed document |
| Demo completions | 3+ successful demo walkthroughs | Meeting notes |
| Time to value (new user) | < 5 minutes from clone to working dashboard | Timed by external person |

---

## 9. PRICING MODEL (Draft)

### Free Tier
- Up to 1,000 API calls/month audited
- Single user
- Basic dashboard
- Community support
- Intended for: individual developers evaluating Overage

### Growth Tier — $X/month (% of monitored LLM spend, similar to CloudZero/Vantage model)
- Unlimited API calls audited
- Up to 5 users
- Full dashboard + PDF reports
- Email alerts
- Priority support
- Intended for: startups and mid-market companies ($50K-$200K/month LLM spend)

### Enterprise Tier — Custom pricing
- Everything in Growth
- On-prem / VPC deployment
- Unlimited users
- SSO / SAML integration
- Dedicated support + SLA
- Custom model fine-tuning for customer's specific prompt domains
- Intended for: large enterprises ($200K+/month LLM spend)

**Pricing rationale:** Usage-based pricing (% of monitored LLM spend) aligns Overage's revenue with customer value. If Overage detects a 15% overcharge on a $100K/month bill, the customer saves $15K/month. Charging 1-3% of monitored spend ($1K-$3K/month) is a clear 5-15x ROI. This model is proven by CloudZero and Vantage in the cloud FinOps space.

---

## APPENDIX A: Token Pricing Reference (for Dollar Impact Calculation)

| Provider | Model | Reasoning Token Price (per 1M tokens) |
|----------|-------|--------------------------------------|
| OpenAI | o3 | $60.00 (output token rate, reasoning tokens counted as output) |
| OpenAI | o4-mini | $12.00 |
| OpenAI | o3-mini | $4.40 |
| Anthropic | claude-sonnet-4 | $15.00 (thinking tokens billed at output rate) |
| Anthropic | claude-3.5-sonnet | $15.00 |
| Google | gemini-2.0-flash-thinking | $3.50 |

These rates are stored in `src/overage/constants.py` and must be updated when providers change pricing.

---

## APPENDIX B: Competitive Landscape

| Tool | What It Does | Why It's Not Overage |
|------|-------------|---------------------|
| **Stripe LLM Billing** | Bills based on provider-reported token counts | Pass-through, no verification |
| **CloudZero** | Cloud cost optimization (infrastructure) | Doesn't audit LLM token counts |
| **Vantage** | Cloud cost analytics | Infrastructure-level, no token verification |
| **Helicone** | LLM observability (logging, analytics) | Displays provider numbers, doesn't verify them |
| **LangSmith** | LLM application debugging/tracing | Development tool, not billing audit |
| **IMMACULATE** | Cryptographic verification of LLM computation | Requires provider cooperation (not available for commercial APIs) |
| **CoIn** | Computation integrity via instrumentation | Requires provider-side changes (not viable as independent audit) |

**Overage's moat:** The only tool that independently verifies LLM reasoning token counts without requiring any provider cooperation. Works as a drop-in proxy.

# Doppler and 1Password — setup guide (Overage)

This guide walks through installing the CLIs, authenticating, and wiring secrets for local development. **Secrets never belong in git** — use Doppler and/or 1Password; keep `.env` generated or injected, not hand-edited long term.

**CLIs installed on this machine (via Homebrew):**

- **Doppler:** `doppler` (`brew install dopplerhq/cli/doppler`)
- **1Password CLI:** `op` (`brew install --cask 1password-cli`)

Verify:

```bash
doppler --version
op --version
```

---

## Architecture choice (read once)

| Role | Recommendation |
|------|----------------|
| **Day-to-day dev commands** | **Doppler** — `doppler run -- <cmd>` injects env vars for a selected **config** (`dev`, `stg`, `prd`). |
| **Human backup / recovery / team** | **1Password** — same secret names in a vault item (or use **1Password inject** with `op://` references). |
| **GitHub Actions** | **GitHub Secrets** and/or **Doppler** service token — not 1Password in the runner unless you use a 1Password Connect server (advanced). |

You can use **both**: 1Password as source of truth for humans, Doppler as the runtime injector after you copy values into a Doppler config (or use Doppler’s dashboard as primary and export a backup to 1Password periodically).

---

## Part 1 — Doppler (web + CLI)

### 1.1 Create the Doppler account and project (browser)

1. Open [https://dashboard.doppler.com](https://dashboard.doppler.com) and sign in (GitHub SSO is fine).
2. Create a **project** named `overage` (or `ishrith-gowda-overage`).
3. Inside the project, create **configs**: at minimum **`dev`**. Add **`stg`** and **`prd`** when you deploy.

### 1.2 Add secrets in Doppler (match `.env.example`)

For each config (`dev` first), add **secret names** exactly as in [`.env.example`](../.env.example), for example:

- `OVERAGE_ENV`, `DEBUG`, `LOG_LEVEL`
- `DATABASE_URL`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
- `API_KEY_SECRET`, `RATE_LIMIT_PER_MINUTE`, `CORS_ORIGINS`
- `ESTIMATION_ENABLED`, `PALACE_MODEL_PATH`, `PALACE_MODEL_VERSION`
- `SENTRY_DSN`, `POSTHOG_API_KEY`

Use the Doppler UI **Secrets** tab, or the CLI after login (Part 1.4):

```bash
doppler secrets set OPENAI_API_KEY="your-value-here" --project overage --config dev
```

(Repeat per key; avoid pasting secrets into shell history — prefer the dashboard for bulk paste, or use `doppler secrets upload` from a local file that you delete immediately.)

### 1.3 Log in with the Doppler CLI

```bash
doppler login
```

This opens a browser to authorize the CLI.

### 1.4 Link this repository to the project (`doppler.yaml`)

From the **repository root**:

```bash
cd /path/to/overage
doppler setup --no-interactive -p overage -c dev
```

This repo includes a committed **`doppler.yaml`** (no secret values) so every clone uses project **`overage`** and config **`dev`**:

```yaml
setup:
  project: overage
  config: dev
```

Commit this file when you add or change it:

```bash
git add doppler.yaml
git commit -m "chore: add doppler project link for dev config"
```

### 1.5 Run commands with secrets injected

```bash
doppler run -- printenv OVERAGE_ENV
doppler run -- make check
doppler run -- python -m uvicorn proxy.main:app --reload
```

**Makefile wrappers** (same thing, less typing):

| Target | Purpose |
|--------|---------|
| `make secrets-verify` | Quick check that Doppler injects `OVERAGE_ENV` |
| `make check-doppler` | `doppler run -- make check` (lint, types, tests, security) |
| `make run-doppler` | `doppler run -- make run` (proxy with secrets) |
| `make sync-env-to-doppler` | Upload local `.env` to Doppler **`dev`** with **`--silent`** (avoids printing values in the terminal) |

Re-sync local `.env` → Doppler after editing `.env`:

```bash
make sync-env-to-doppler
```

If `doppler run` fails, run `doppler setup --no-interactive -p overage -c dev` again from the repo root.

### 1.6 Optional: download a local `.env` for tools that ignore Doppler

Only if a tool **requires** a literal `.env` file:

```bash
doppler secrets download --no-file --format env > .env
```

**Warning:** This overwrites `.env`. Remove the file or avoid committing it (`.env` is gitignored). Prefer `doppler run` so secrets stay in Doppler.

---

## Part 2 — 1Password (CLI + vault)

### 2.1 Prerequisites

- A **1Password** account (you have the student/developer offering).
- **1Password 8** desktop app recommended on macOS (integrates with the CLI for biometric unlock).

### 2.2 Sign in to the CLI

**Option A — Integrated with 1Password app (simplest on Mac)**

1. Open the **1Password** app and sign in.
2. In Terminal:

```bash
eval $(op signin)
```

Follow prompts; you may use the app to approve.

**Option B — Standalone CLI (account URL + email + Secret Key)**

You need your **1Password account URL** (e.g. `my.1password.com`), **email**, and **Secret Key** (from your emergency kit — store safely).

```bash
eval $(op signin)
```

### 2.3 Create a vault or use an existing one

Example: create a vault **Overage** (or use **Private** while solo).

```bash
op vault list
# op vault create "Overage"   # if your plan allows creating vaults via CLI
```

If `vault create` is restricted, create the vault in the 1Password app, then continue.

### 2.4 Store one structured item for Overage

In the **1Password app**, create an item type **API Credential** or **Secure Note** named **Overage — env (dev)**.

Add **fields** whose names match environment variable names (`OPENAI_API_KEY`, `DATABASE_URL`, …), or paste a full `.env` body in one note (less convenient for rotation).

Alternatively via CLI (example — adjust vault name):

```bash
op item create --category=SecureNote --title="Overage env template" --vault="Private" 'notesPlain=Paste key=value lines here in the app'
```

Most people edit the rich item in the app after a minimal CLI create.

### 2.5 Inject secrets into a process (optional advanced pattern)

1Password supports **inject** from a template file using `op://` references. Example template `env.tpl` (do **not** commit real references without reviewing):

```dotenv
OPENAI_API_KEY=op://Private/Overage-env/OPENAI_API_KEY
```

Then:

```bash
op inject -i env.tpl -o .env
```

Use this only if you standardize on 1Password as the single injector; otherwise **Doppler** + `doppler run` is simpler for this repo.

---

## Part 3 — Order of operations (checklist)

1. [ ] Doppler: project + `dev` config + all keys from `.env.example`
2. [ ] `doppler login` → `doppler setup` in repo root → committed `doppler.yaml`
3. [ ] Secrets uploaded (dashboard, `make sync-env-to-doppler`, or `doppler secrets upload .env --silent`)
4. [ ] `make secrets-verify` and `make check-doppler` succeed
5. [ ] 1Password backup: run `./scripts/backup_doppler_env_to_1password.sh` (set `OP_VAULT` first) or copy from Doppler dashboard
6. [ ] (Optional) Rotate any key that was ever exposed; update **both** Doppler and 1Password

### 3.1 One-command backup to 1Password

After `op signin`, create a **document** in your vault containing the current Doppler `dev` export:

```bash
export OP_VAULT="Private"   # or your vault name
./scripts/backup_doppler_env_to_1password.sh
```

This uses `doppler secrets download` and `op document create` — it does **not** print secret values.

---

## Part 4 — GitHub Actions (later)

- Keep using **GitHub repository secrets** for `CODECOV_TOKEN` and deploy tokens.
- For syncing CI with Doppler, use a **Doppler service token** (read-only for `stg`/`prd`) stored as a GitHub secret and `doppler run` in the workflow — add only when you are ready to wire deployment.

---

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `doppler: command not found` | `brew install dopplerhq/cli/doppler` |
| `op: command not found` | `brew install --cask 1password-cli` |
| Doppler wrong project | `doppler setup` again in repo root |
| 1Password session expired | `eval $(op signin)` again |

---

## References

- Doppler: [Install](https://docs.doppler.com/docs/install-cli), [CLI](https://docs.doppler.com/docs/cli)
- 1Password CLI: [Get started](https://developer.1password.com/docs/cli/)

# Contributing to Overage

Thank you for contributing to Overage! This guide walks you through the development setup, coding standards, and PR process. For comprehensive coding patterns and anti-patterns, see [INSTRUCTIONS.md](./INSTRUCTIONS.md).

---

## Prerequisites

- **Python 3.12+** — [download](https://www.python.org/downloads/)
- **Docker** — [download](https://www.docker.com/products/docker-desktop/) (for local PostgreSQL)
- **Git** — [download](https://git-scm.com/)
- **VS Code** (recommended) — extensions auto-suggested on first open

---

## Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/ishrith-gowda/overage.git
cd overage

# 2. Create and activate a virtual environment
# Use --copies: exfat, some smb mounts, and usb sticks often break venv symlinks.
python3.12 -m venv --copies .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install all dependencies (production + development)
# COPYFILE_DISABLE=1 avoids macOS AppleDouble "._*" files beside wheels on removable media.
COPYFILE_DISABLE=1 make install-dev
# If pip still shows "Ignoring invalid distribution" or imports fail: make venv-fresh

# 4. Install pre-commit hooks
make pre-commit-install

# 4b. Use repo git hooks (strips Made-with / Co-authored-by trailers from messages)
git config core.hooksPath .githooks

# 5. Copy environment template and configure
cp .env.example .env
# Edit .env with your API keys (optional — demo mode works without them)

# 6. Start the database (PostgreSQL via Docker)
make docker-up

# 7. Apply database migrations
make migrate

# If you see "table ... already exists" on first `make migrate` after pulling Alembic:
# older checkouts only used ORM `create_all`. Delete local `overage_dev.db` once and re-run
# `make migrate` (or remove the conflicting SQLite file in `DATABASE_URL`).

# 8. Verify everything works (Python 3.12+ required — `make verify-python` checks this)
make check  # Runs verify-python, lint, typecheck, test, security
```

If `make check` passes, you're ready to contribute.

### Cloning or working on a USB / exFAT volume (macOS)

macOS can drop AppleDouble `._*` files next to real files. They break Git pack indexes (`non-monotonic index .git/objects/pack/._pack-…`) and pip metadata (`Ignoring invalid distribution -packagename`). After any Finder copy onto the drive, run `make git-usb-clean` in the repo root. `make venv-fresh` runs `dot_clean` plus a `find` pass on `.venv` to remove those sidecars after install.

---

## Branch Naming

Create a feature branch from `main`. Use the following prefixes:

```
feat/proxy-gemini-adapter          # New feature
fix/timing-estimation-overflow     # Bug fix
refactor/provider-base-interface   # Code restructuring
docs/update-architecture-diagram   # Documentation
test/proxy-integration-tests       # Test additions
ci/add-codecov-upload              # CI/CD changes
chore/update-dependencies          # Maintenance
```

---

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) with stricter project rules so that `git log` on `main` is a single-line, machine-greppable changelog.

```
<type>(scope?): <lowercase imperative subject>
```

### Hard rules (enforced by the `Commit Lint` workflow on every PR)

- **Single line only.** No body, no blank line, no trailers.
- **All lowercase** subject.
- **No trailing period.**
- **Subject length** ≤ 72 characters; PR title length ≤ 80.
- **No trailers** of any kind: `Signed-off-by:`, `Co-authored-by:`, `Made-with:`, `Generated-by:` are all forbidden.
- **One logical change per PR.** PRs are merged with **squash** only; the **PR title becomes the commit subject** on `main` (the body is stripped to BLANK by repo settings — verify in *Settings → General → Pull Requests*).

**Allowed types:** `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`, `perf`, `style`, `build`.

### Examples

```
feat: add anthropic provider adapter with thinking token extraction
feat(estimation): implement timing-based token estimation for o3
fix: handle missing reasoning_tokens field in openai response
fix(proxy): prevent division by zero in discrepancy percentage
refactor: extract provider registration into factory pattern
docs: add sequence diagram to architecture.md
test: add parametrized tests for tps lookup table
ci: add commit-message lint workflow
chore: update fastapi to 0.115.6
perf: reduce proxy overhead by removing redundant header copy
```

### Local enforcement

Activate the project commit template once per clone so `git commit` reminds you of the rules:

```bash
git config commit.template .gitmessage
git config core.hooksPath .githooks   # also strips forbidden trailers
```

If you need to clean up multi-line dev commits before opening a PR, squash them locally with `git rebase -i origin/main`. The lint workflow only **blocks** on PR title format; per-commit warnings are advisory because squash normalises them anyway.

---

## PR Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Write code** following [INSTRUCTIONS.md](./INSTRUCTIONS.md) conventions:
   - Full type annotations on every function
   - Google-style docstrings on every public function
   - Structured logging via `structlog` (never `print()`)
   - Specific exception handling (never bare `except:`)

3. **Run all checks locally**:
   ```bash
   make check  # lint + typecheck + test + security
   ```

4. **Push and open a PR** against `main`:
   ```bash
   git push origin feat/my-feature
   ```
   Fill in the PR template completely.

5. **Wait for CI** to pass — all required checks (`Lint`, `Type Check`, `Test`, `Security Scan`, `Docker Build`, `CodeQL Analysis`, `Dependency Review`, `Commit Lint`) must be green; `main` is branch-protected and rejects merges otherwise.

   **Duplicate `CodeQL` check (GitHub Advanced Security):** If the PR shows a second check named **`CodeQL`** (from app **`github-advanced-security`**) failing in a few seconds while **`CodeQL Analysis`** (Actions workflow `security.yml`) is green, branch protection or **Default code scanning setup** is out of sync with the custom workflow. Fix in **GitHub → Repository → Settings → Code security and analysis → Code scanning**: disable **Default setup** if you use the `security.yml` workflow, **or** remove the stray **`CodeQL`** required status from **Rules / Branch protection** so only **`CodeQL Analysis`** is required (see `docs/CODECOV.md` / this file for CI job names).

6. **Request review** (or self-merge if solo development with CI green).

7. **Squash merge** into `main`:

   ```bash
   gh pr merge <num> --squash --subject "<exact PR title>" --body ""
   ```

   - Pass `--subject` and an empty `--body ""` explicitly. Repo settings (`squash_merge_commit_title=PR_TITLE`, `squash_merge_commit_message=BLANK`) cover the default case but the explicit form is the only one that *also* prevents GitHub from inheriting `Signed-off-by:` / `Co-authored-by:` trailers from Dependabot's source commits.
   - **Do not** use `gh pr merge --auto` and **do not** click "Enable auto-merge" or "Update branch" in the GitHub UI. Both add `Co-authored-by: <whoever-clicked>` to the squash commit. Branch protection's `strict` flag is satisfied by `gh pr update-branch` from CLI; if dependabot's branch is stale ask `@dependabot rebase` in a comment and wait, do not click Update.
   - Branch deletion is automatic (`delete_branch_on_merge=true`).

If a `Signed-off-by:` or `Co-authored-by:` trailer ever lands on `main` despite this process, scrub it:

```bash
make strip-trailers SINCE=<last-clean-sha> REF=main   # local rewrite, dry run-ish
# … or, in the GitHub UI: Actions → "Strip Trailers" → Run workflow with confirm=YES
```

This is documented in [`docs/ROADMAP.md`](./docs/ROADMAP.md) §5 (Phase 7, subtask 7.6) and uses the safety tag `pre-rewrite-2026-05-10` as the recovery point. The same document is the canonical phase / task ledger for everything Overage is building, has built, and plans to build — start there for any non-trivial change.

---

## Code Review Expectations

Reviewers will check for:

- **Correctness:** Does the code do what the PR description says?
- **Type safety:** Are all functions fully annotated? Does `make typecheck` pass?
- **Test coverage:** Are there tests for the new code? Does it meet the CI floor (see `ci.yml`)?
- **Error handling:** Are exceptions caught specifically and logged with structlog?
- **Performance:** Does the change impact proxy latency (<10ms critical path)?
- **Security:** No hardcoded secrets, no raw SQL, no unsafe deserialization?
- **Naming:** Do function/variable/file names follow the conventions in INSTRUCTIONS.md?
- **Documentation:** Are docstrings complete? Is the API contract updated if endpoints changed?

---

## Testing Requirements

- Meet the **pytest-cov** floor in `.github/workflows/ci.yml` on `proxy/`; prefer higher on new modules.
- Mock all external services (OpenAI, Anthropic, database for unit tests)
- Follow the test naming convention: `test_<function>_<scenario>_<expected_result>`
- Every test MUST contain at least one `assert` statement
- Use `pytest.mark.asyncio` for async tests
- Use `pytest.mark.integration` for tests that require a database
- Use `pytest.mark.slow` for tests that take >5 seconds

See [INSTRUCTIONS.md Section 8](./INSTRUCTIONS.md) for complete test examples.

---

## Adding a New LLM Provider

1. Create `proxy/providers/newprovider.py` implementing `BaseProvider` (see `proxy/providers/base.py`)
2. Implement all abstract methods: `forward_request()`, `extract_usage()`, `get_model_from_response()`
3. Register in `proxy/providers/registry.py`: `_PROVIDERS["newprovider"] = NewProvider`
4. Add TPS rates to `proxy/constants.py` for timing estimation
5. Write unit tests in `proxy/tests/unit/test_providers/test_newprovider.py`
6. Write integration tests in `proxy/tests/integration/test_proxy_newprovider.py`
7. Update `PRD.md` API contract section with the new proxy endpoint
8. Update `.env.example` with the new provider's API key variable
9. Update `README.md` if the provider is user-facing

---

## Adding a New API Endpoint

1. Create or update the route file in `proxy/api/` (follow the pattern in `proxy/api/calls.py`)
2. Create Pydantic request/response models in `proxy/schemas/`
3. Add the router to `proxy/api/router.py`
4. Write unit tests for the endpoint logic
5. Write integration tests with the FastAPI test client
6. Update `PRD.md` with the endpoint contract (method, path, request/response schema, error codes)
7. If the endpoint requires a new database model, create it and generate an Alembic migration

---

## Questions?

- Check [INSTRUCTIONS.md](./INSTRUCTIONS.md) for coding patterns
- Check [ARCHITECTURE.md](./ARCHITECTURE.md) for system design questions
- Check [PRD.md](./PRD.md) for product requirements
- Open an issue for anything not covered

---

Thank you for helping build Overage!

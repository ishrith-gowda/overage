# Codecov — troubleshooting (Overage)

This document explains how **Codecov** is wired in CI and how to fix common issues (deactivated repo, missing GitHub secret, empty dashboard).

## How CI uploads coverage

The workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs:

- **`codecov/codecov-action@v5`** with `coverage.xml` from pytest.
- **`codecov/test-results-action@v1`** with `junit.xml` for Test Analytics.

Both steps use:

```yaml
token: ${{ secrets.CODECOV_TOKEN }}
```

So **GitHub must have a repository secret** named exactly **`CODECOV_TOKEN`**. If the secret is missing, uploads will not authenticate correctly.

## Fix: GitHub secret (required)

1. In **Codecov**, open **`ishrith-gowda/overage`** → **Configuration** → **General**.
2. Under **Repository upload token**, copy the **upload token** (UUID format).
3. In **GitHub**: **Repository → Settings → Secrets and variables → Actions → Secrets** → **New repository secret**.
4. **Name:** `CODECOV_TOKEN`  
5. **Value:** paste the upload token → **Add secret**.

Do **not** commit the token into the repo. Do **not** confuse it with the **badge/graph** token shown under **Badges & Graphs** (that is a different, public-facing token for embeds).

## Fix: “Deactivated” repository

If the repo list shows **Deactivated** or uploads fail with a deactivation message:

1. Codecov → **Configuration** → **General**.
2. In **Danger zone**, use **Activate** (not **Deactivate**).  
   If the repo is already active, you will see **Deactivate** instead — then activation is already done.

A deactivated repo **blocks uploads** until it is activated again.

## Fix: empty Coverage tab / “merge to default branch”

Codecov’s **Coverage** overview often fills after:

- A successful **upload** from CI on the **default branch** (`main`), **and**
- The repo is **active** and the upload token is valid.

Until then, **Commits** / **Pulls** may show **patch coverage: —** for PRs. After the first good upload to `main`, PR coverage comments should start working.

## Optional: `codecov.yml` in the repo

You can add a root **`codecov.yml`** in git for coverage thresholds, PR comments, and flags. The UI **Repository YAML** editor on Codecov is optional if you prefer version-controlled config.

## Codecov CLI (local uploads)

For manual uploads from your machine (optional):

```bash
pip install codecov-cli
# from repo root, with coverage.xml present:
codecovcli upload-process -t "$CODECOV_TOKEN" -f coverage.xml
```

Use the same **repository upload token** as `CODECOV_TOKEN`. Prefer **`doppler run`** or a local env var — never paste the token into git or chat.

## “Current bot: none” (PR comments)

If PRs never get Codecov comments, install the **Codecov GitHub App** on the org/account and grant access to this repository (Codecov → **Settings** / integration). The upload token alone does not install the GitHub App.

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-19 | Initial troubleshooting for deactivated repo + missing `CODECOV_TOKEN` |

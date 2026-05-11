---
name: Phase 4 regression
about: Track alert persistence, summary/group_by, or dashboard API contract failures
labels: phase-4, regression
---

## What broke

Describe the failure (CI job **Phase 4 regression**, `make test-phase4`, or `make check`).

## Failing test or job

- Test name(s) or workflow link:
- Log excerpt or traceback:

## Scope

- [ ] `DiscrepancyAlert` / sliding window (`proxy/estimation/alert_persistence.py`, `aggregator.py`)
- [ ] `_record_and_estimate` background path (`proxy/api/routes.py`)
- [ ] Summary / `group_by` / timeseries (`GET /v1/summary`, `GET /v1/summary/timeseries`)
- [ ] Dashboard HTTP contract (`proxy/tests/test_phase4_dashboard_api_contract.py`)

## Environment

- Commit / branch:
- Local or GitHub Actions:

## Notes

Link related PRs or provider-key staging runs if relevant.

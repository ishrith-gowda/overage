# Estimation Engine

This document is a **stub** for the ML and signal-processing side of Overage. The authoritative design lives in **[ARCHITECTURE.md](../ARCHITECTURE.md) — Section 7 (Estimation Pipeline)**.

## Scope

Overage combines model-based token estimation with timing analysis and aggregation to surface discrepancies between independently estimated reasoning usage and provider-reported counts. Implementation code lives primarily under `proxy/estimation/`.

The **PALACE** path runs inference over request/response text to produce token-oriented estimates; the **timing** path uses observed latency and request metadata. **Aggregation** merges these into discrepancy scores suitable for dashboards and alerts. Together they form the pipeline described in the architecture document—this stub does not duplicate full math or hyperparameters.

## Sections (see Architecture §7)

1. **§7.1 — PALACE inference:** primary estimator for token-related signals.
2. **§7.2 — Timing estimation:** correlates latency with expected compute.
3. **§7.3 — Signal aggregation:** combines estimators into comparable metrics.
4. **§7.4 — Sliding window analysis:** trend and anomaly detection over time.
5. **§7.5 — Domain classification:** optional routing of behavior by workload type.

## Related code

Key modules: `proxy/estimation/palace.py`, `timing.py`, `aggregator.py`. Model weights and tokenizer assets belong under `model/`; see `model/data/README.md` for dataset notes.

## Next steps for this doc

- Add diagrams aligned with **ARCHITECTURE.md** Section 7.
- Document model artifacts under `model/`, versioning, and rollout.
- Link to benchmarks and evaluation methodology when available.

## Evaluation (stub)

Offline metrics (calibration, interval coverage, latency overhead) should be summarized here once the evaluation harness is stable; until then, treat **ARCHITECTURE.md** §7 and internal experiment logs as the source of truth.

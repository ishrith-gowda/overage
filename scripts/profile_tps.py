#!/usr/bin/env python3
"""Profile tokens-per-second for a model via the Overage proxy.

Records (reported_tokens, latency_ms) pairs and computes mean TPS, std,
and linear-regression R² for timing calibration.
"""
from __future__ import annotations

import argparse, asyncio, json, sys, time
from typing import Any
import httpx, structlog

structlog.configure(
    processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(structlog._log_levels.NAME_TO_LEVEL["info"]),
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger(__name__)

PROMPTS: list[str] = [
    "Explain quicksort step by step with complexity analysis.",
    "Derive Euler's identity from Taylor series.",
    "Write a Python function for Dijkstra's shortest path algorithm.",
    "Prove that there are infinitely many prime numbers.",
    "Explain how a B-tree works and why databases use them.",
    "Describe the Byzantine Generals Problem and its implications.",
]

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description="Profile TPS via the Overage proxy", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--provider", choices=["openai", "anthropic"], required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--count", type=int, default=20, help="Profiling calls")
    p.add_argument("--proxy-url", default="http://localhost:8000")
    p.add_argument("--api-key", required=True, help="Provider API key")
    p.add_argument("--overage-key", default=None, help="Overage API key (X-API-Key)")
    p.add_argument("--output", default="tps_profiles.json")
    return p.parse_args()

def _stats(samples: list[dict[str, float]]) -> dict[str, Any]:
    """Compute TPS mean, std, and linear-regression R²."""
    v = [s for s in samples if s["latency_ms"] > 0 and s["tokens"] > 0]
    n = len(v)
    if n == 0:
        return {"mean_tps": 0.0, "std_tps": 0.0, "r_squared": 0.0, "n": 0}
    tps = [s["tokens"] / (s["latency_ms"] / 1000.0) for s in v]
    m = sum(tps) / n
    std = (sum((t - m) ** 2 for t in tps) / n) ** 0.5
    xs, ys = [s["tokens"] for s in v], [s["latency_ms"] for s in v]
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    r2 = (sxy ** 2) / (sxx * syy) if sxx > 0 and syy > 0 else 0.0
    return {"mean_tps": round(m, 2), "std_tps": round(std, 2), "r_squared": round(r2, 6), "n": n}

async def main() -> int:
    """Run TPS profiling and write results to JSON."""
    args = parse_args()
    url, hdr = f"{args.proxy_url}/v1/proxy/{args.provider}", {"Content-Type": "application/json"}
    if args.provider == "openai":
        hdr["Authorization"] = f"Bearer {args.api_key}"
    else:
        hdr["x-api-key"] = args.api_key
    if args.overage_key:
        hdr["X-API-Key"] = args.overage_key
    samples: list[dict[str, float]] = []
    log.info("profiling_started", provider=args.provider, model=args.model, count=args.count)
    async with httpx.AsyncClient(timeout=300.0) as client:
        for i in range(args.count):
            body: dict[str, Any] = {"model": args.model, "messages": [{"role": "user", "content": PROMPTS[i % len(PROMPTS)]}]}
            if args.provider == "anthropic":
                body["max_tokens"] = 4096
            t0 = time.perf_counter()
            try:
                resp = await client.post(url, json=body, headers=hdr)
                ms = (time.perf_counter() - t0) * 1000.0
                resp.raise_for_status()
                tok = float(resp.json().get("usage", {}).get("completion_tokens" if args.provider == "openai" else "output_tokens", 0))
                samples.append({"tokens": tok, "latency_ms": round(ms, 1)})
                log.info("sample", call=i + 1, of=args.count, tokens=int(tok), latency_ms=round(ms, 1))
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                log.error("profile_call_failed", call=i + 1, error=str(exc))
    st = _stats(samples)
    with open(args.output, "w") as fh:
        json.dump({"provider": args.provider, "model": args.model, "samples": samples, "stats": st}, fh, indent=2)
    log.info("profiling_complete", output=args.output, **st)
    return 0
if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

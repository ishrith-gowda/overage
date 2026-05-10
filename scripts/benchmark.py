#!/usr/bin/env python3
"""Measure HTTP latency to the Overage proxy (wire round-trip).

Repeated requests to ``GET /health`` (or another path / method) yield
min/max/mean and percentiles in milliseconds. Default ``/health`` measures how
responsive the FastAPI process is on your machine (no auth, no DB write).
Use ``--method POST`` with ``--path`` and ``--json`` to approximate proxy RTT
when the server is running with a valid ``X-API-Key`` (still excludes upstream
provider latency when the provider is mocked or very fast).

End-to-end LLM latency includes provider time; for TPS-style calibration see
``scripts/profile_tps.py``.

Usage:
    make run   # terminal 1
    python scripts/benchmark.py
    python scripts/benchmark.py --base-url http://127.0.0.1:8000 --iterations 500
    python scripts/benchmark.py --path /v1/proxy/openai --method POST \\
      --header "X-API-Key: ovg_live_..." --header "Authorization: Bearer sk-..." \\
      --json '{"model":"o3","messages":[{"role":"user","content":"hi"}],"stream":false}'
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from typing import Any

import httpx
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(structlog._log_levels.NAME_TO_LEVEL["info"]),
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark HTTP latency to the Overage proxy",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Proxy base URL (no trailing slash)",
    )
    parser.add_argument(
        "--path",
        default="/health",
        help="URL path to request (e.g. /health or /v1/proxy/openai)",
    )
    parser.add_argument(
        "--method",
        default="GET",
        choices=("GET", "POST"),
        help="HTTP method (POST requires --json for a JSON body)",
    )
    parser.add_argument(
        "--json",
        dest="json_body",
        default=None,
        metavar="BODY",
        help='JSON body for POST (e.g. \'{"model":"o3","messages":[]}\')',
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        metavar="KEY:VALUE",
        help="Request header (repeatable), e.g. --header 'X-API-Key: ovg_live_...'",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Samples after warmup",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=20,
        help="Warmup requests (discarded)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds",
    )
    return parser.parse_args()


def _linear_percentile(sorted_samples: list[float], p: float) -> float:
    """Return the p-th percentile (0–100) using linear interpolation."""
    n = len(sorted_samples)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_samples[0]
    if p <= 0:
        return sorted_samples[0]
    if p >= 100:
        return sorted_samples[-1]
    rank = (p / 100.0) * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_samples[lo] + frac * (sorted_samples[hi] - sorted_samples[lo])


def _percentiles_ms(samples: list[float]) -> dict[str, float]:
    """Compute min, max, mean, stdev, and p50/p95/p99 in milliseconds."""
    if not samples:
        return {}
    s = sorted(samples)
    mean = statistics.mean(s)
    stdev = statistics.stdev(s) if len(s) > 1 else 0.0
    return {
        "min_ms": s[0],
        "max_ms": s[-1],
        "mean_ms": mean,
        "stdev_ms": stdev,
        "p50_ms": _linear_percentile(s, 50.0),
        "p95_ms": _linear_percentile(s, 95.0),
        "p99_ms": _linear_percentile(s, 99.0),
    }


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    """Run timed HTTP requests and return summary statistics.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Dict suitable for logging and display.
    """
    url = args.base_url.rstrip("/") + (args.path if args.path.startswith("/") else f"/{args.path}")
    times_ms: list[float] = []

    headers: dict[str, str] = {}
    for raw in args.header:
        if ":" not in raw:
            msg = f"Invalid --header (expected KEY:VALUE): {raw!r}"
            raise ValueError(msg)
        key, _, value = raw.partition(":")
        headers[key.strip()] = value.strip()

    json_payload: dict[str, Any] | None = None
    if args.method == "POST":
        if not args.json_body:
            msg = "--method POST requires --json with a JSON object string"
            raise ValueError(msg)
        json_payload = json.loads(args.json_body)

    with httpx.Client(timeout=args.timeout) as client:
        for _ in range(args.warmup):
            if args.method == "GET":
                client.get(url, headers=headers).raise_for_status()
            else:
                client.post(url, headers=headers, json=json_payload).raise_for_status()

        for _ in range(args.iterations):
            t0 = time.perf_counter()
            if args.method == "GET":
                response = client.get(url, headers=headers)
            else:
                response = client.post(url, headers=headers, json=json_payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            times_ms.append(elapsed_ms)
            response.raise_for_status()

    stats = _percentiles_ms(times_ms)
    stats["url"] = url
    stats["method"] = args.method
    stats["iterations"] = args.iterations
    stats["warmup"] = args.warmup
    return stats


def main() -> int:
    """Entry point."""
    args = parse_args()
    try:
        summary = run_benchmark(args)
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        logger.error("benchmark_request_failed", error=str(exc))
        return 1

    p50 = summary["p50_ms"]
    p99 = summary["p99_ms"]
    logger.info(
        "benchmark_complete",
        url=summary["url"],
        method=summary["method"],
        iterations=summary["iterations"],
        warmup=summary["warmup"],
        min_ms=round(summary["min_ms"], 3),
        max_ms=round(summary["max_ms"], 3),
        mean_ms=round(summary["mean_ms"], 3),
        stdev_ms=round(summary["stdev_ms"], 3),
        p50_ms=round(p50, 3),
        p95_ms=round(summary["p95_ms"], 3),
        p99_ms=round(p99, 3),
    )

    print()
    print(f"  URL:         {summary['url']}")
    print(f"  Method:      {summary['method']}")
    print(f"  Iterations:  {summary['iterations']} (warmup {summary['warmup']} discarded)")
    print(f"  min / max:   {summary['min_ms']:.3f} / {summary['max_ms']:.3f} ms")
    print(f"  mean ± σ:    {summary['mean_ms']:.3f} ± {summary['stdev_ms']:.3f} ms")
    print(f"  p50 / p95:   {summary['p50_ms']:.3f} / {summary['p95_ms']:.3f} ms")
    print(f"  p99:         {summary['p99_ms']:.3f} ms")
    print()
    print("  PRD proxy overhead targets (critical path): p50 < 5 ms, p99 < 10 ms")
    print("  (Those apply to added latency on top of the upstream provider.)")
    print("  Default /health measures local process + routing only.")
    print("  Use --method POST --path /v1/proxy/... to measure wire RTT through the proxy route.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

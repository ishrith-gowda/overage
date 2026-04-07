#!/usr/bin/env python3
"""Generate an audit report from the Overage proxy API.

Fetches summary statistics and call-level data, computes per-model
breakdowns, and outputs a structured report in JSON or text format.

Usage:
    python scripts/generate_report.py --api-key ovg_live_... --format text
    python scripts/generate_report.py --api-key ovg_live_... --start-date 2026-03-01 --end-date 2026-03-31
    python scripts/generate_report.py --api-key ovg_live_... --format json --output audit.json
"""
from __future__ import annotations

import argparse, asyncio, json, sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx, structlog

structlog.configure(
    processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(structlog.get_level_from_name("INFO")),
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description="Generate an audit report from the Overage API", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
    p.add_argument("--proxy-url", default="http://localhost:8000", help="Overage proxy base URL")
    p.add_argument("--api-key", required=True, help="Overage API key (X-API-Key)")
    p.add_argument("--output", default="report.json", help="Output file path")
    p.add_argument("--format", choices=["json", "text"], default="json", dest="fmt")
    return p.parse_args()


async def _fetch_summary(client: httpx.AsyncClient, base: str, hdr: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
    """Fetch aggregate summary from ``/v1/summary``."""
    resp = await client.get(f"{base}/v1/summary", headers=hdr, params=params)
    resp.raise_for_status()
    return resp.json()


async def _fetch_all_calls(client: httpx.AsyncClient, base: str, hdr: dict[str, str], params: dict[str, str]) -> list[dict[str, Any]]:
    """Fetch every matching call from ``/v1/calls`` with auto-pagination."""
    all_calls: list[dict[str, Any]] = []
    offset, limit = 0, 200
    while True:
        resp = await client.get(f"{base}/v1/calls", headers=hdr, params={**params, "limit": str(limit), "offset": str(offset)})
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("calls", [])
        all_calls.extend(batch)
        if len(batch) < limit or offset + limit >= data.get("total", 0):
            break
        offset += limit
    return all_calls


def _model_breakdown(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate call data into per-model statistics."""
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "rtok": 0, "lat": 0.0})
    for c in calls:
        b = buckets[f"{c.get('provider', '?')}/{c.get('model', '?')}"]
        b["n"] += 1
        b["rtok"] += c.get("reported_reasoning_tokens", 0)
        b["lat"] += c.get("total_latency_ms", 0.0)
    result: list[dict[str, Any]] = []
    for key in sorted(buckets):
        prov, model = key.split("/", 1)
        b = buckets[key]
        result.append({"provider": prov, "model": model, "call_count": b["n"],
                        "total_reasoning_tokens": b["rtok"], "avg_latency_ms": round(b["lat"] / b["n"], 1) if b["n"] else 0.0})
    return result


def _format_text(report: dict[str, Any]) -> str:
    """Render the report as a human-readable text table."""
    lines: list[str] = []
    sep = "=" * 66
    lines += [sep, "  OVERAGE AUDIT REPORT", sep]
    per = report.get("period", {})
    lines.append(f"  Period:    {per.get('start_date', 'all')}  to  {per.get('end_date', 'all')}")
    lines.append(f"  Generated: {report.get('generated_at', 'N/A')}")
    lines.append("")
    s = report.get("summary", {})
    lines += ["  SUMMARY", "-" * 66]
    lines.append(f"  Total calls:               {s.get('total_calls', 0):>10,}")
    lines.append(f"  Reported reasoning tokens:  {s.get('total_reported_reasoning_tokens', 0):>10,}")
    lines.append(f"  Estimated reasoning tokens: {s.get('total_estimated_reasoning_tokens', 0):>10,}")
    lines.append(f"  Aggregate discrepancy:      {s.get('aggregate_discrepancy_pct', 0):>9.2f}%")
    lines.append(f"  Avg discrepancy:            {s.get('avg_discrepancy_pct', 0):>9.2f}%")
    lines.append(f"  Total $ impact:             ${s.get('total_dollar_impact', 0):>9,.2f}")
    lines.append(f"  Honoring rate:              {s.get('honoring_rate_pct', 0):>9.1f}%")
    lines.append("")
    lines += ["  PER-MODEL BREAKDOWN", "-" * 66]
    lines.append(f"  {'Provider':<12} {'Model':<26} {'Calls':>7} {'Reasoning':>12} {'Avg ms':>9}")
    lines.append(f"  {'--------':<12} {'-----':<26} {'-----':>7} {'---------':>12} {'------':>9}")
    for m in report.get("model_breakdown", []):
        lines.append(f"  {m['provider']:<12} {m['model']:<26} {m['call_count']:>7,} "
                      f"{m['total_reasoning_tokens']:>12,} {m['avg_latency_ms']:>9.1f}")
    lines += ["", sep]
    return "\n".join(lines)


async def main() -> int:
    """Fetch data from the Overage API and produce an audit report."""
    args = parse_args()
    hdr: dict[str, str] = {"X-API-Key": args.api_key}
    params: dict[str, str] = {}
    if args.start_date:
        params["start_date"] = args.start_date
    if args.end_date:
        params["end_date"] = args.end_date

    log.info("report_generation_started", fmt=args.fmt, output=args.output)
    async with httpx.AsyncClient(timeout=60.0) as client:
        summary = await _fetch_summary(client, args.proxy_url, hdr, params)
        calls = await _fetch_all_calls(client, args.proxy_url, hdr, params)

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {"start_date": args.start_date or "all", "end_date": args.end_date or "all"},
        "summary": summary,
        "model_breakdown": _model_breakdown(calls),
        "total_calls_fetched": len(calls),
    }

    if args.fmt == "json":
        with open(args.output, "w") as fh:
            json.dump(report, fh, indent=2)
        log.info("report_written", path=args.output, format="json", calls=len(calls))
    else:
        text = _format_text(report)
        if args.output != "report.json":
            with open(args.output, "w") as fh:
                fh.write(text + "\n")
            log.info("report_written", path=args.output, format="text", calls=len(calls))
        else:
            sys.stdout.write(text + "\n")
            log.info("report_printed", format="text", calls=len(calls))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

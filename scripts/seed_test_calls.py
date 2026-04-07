#!/usr/bin/env python3
"""Send real API calls through the Overage proxy to build a demo dataset.

Sends diverse prompts across math, code, logic, creative, and general
domains through the proxy, recording token counts and latencies.

Usage:
    python scripts/seed_test_calls.py --provider openai --model o3 --api-key sk-...
    python scripts/seed_test_calls.py --provider anthropic --model claude-sonnet-4-20250514 --api-key sk-ant-...
"""
from __future__ import annotations

import argparse, asyncio, sys, time
from typing import Any

import httpx, structlog

structlog.configure(
    processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(structlog.get_level_from_name("INFO")),
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger(__name__)

PROMPTS: list[str] = [
    "Prove that the square root of 2 is irrational.",
    "Solve the integral of x^2 * e^x dx step by step.",
    "Find all solutions to x^3 - 6x^2 + 11x - 6 = 0.",
    "Explain the Monty Hall problem with a rigorous probability proof.",
    "Derive the quadratic formula from ax^2 + bx + c = 0.",
    "Prove by induction that the sum of first n odd numbers equals n^2.",
    "Compute the eigenvalues and eigenvectors of [[2,1],[1,3]].",
    "Write a Python function to find the longest palindromic substring.",
    "Implement a thread-safe LRU cache in Python with O(1) get and put.",
    "Design a rate limiter using the token bucket algorithm in Python.",
    "Write a function to serialize and deserialize a binary tree.",
    "Implement merge sort with detailed comments explaining each step.",
    "Write a Python async generator that implements exponential backoff retry.",
    "Implement a trie with insert, search, and starts_with methods in Python.",
    "Solve the river crossing puzzle with a fox, chicken, and grain.",
    "A bat and ball cost $1.10. The bat costs $1 more than the ball. Explain.",
    "12 balls, one heavier, balance scale — find it in 3 weighings.",
    "Explain the prisoner's dilemma and derive the Nash equilibrium.",
    "Solve the Tower of Hanoi for 5 disks and explain the recursive pattern.",
    "Three people check into a $30 hotel room. Solve the missing dollar riddle.",
    "Write a short story about an AI that discovers it is being audited.",
    "Compose a poem about the relationship between computation and truth.",
    "Create a dialogue between two scientists debating consciousness.",
    "Write a blog post intro about reasoning token billing transparency.",
    "Describe a futuristic world where every API call is independently verified.",
    "Write a haiku for each season and explain the imagery.",
    "Explain how transformers work in ML from first principles.",
    "Compare and contrast REST, GraphQL, and gRPC for API design.",
    "What are the tradeoffs between SQL and NoSQL databases? Give examples.",
    "Explain the CAP theorem and how distributed systems handle it.",
    "Describe the history and evolution of cryptographic hash functions.",
    "How does TCP congestion control work? Explain slow start and AIMD.",
    "Explain zero-knowledge proofs with a simple, intuitive example.",
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description="Send real API calls through the Overage proxy", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--provider", choices=["openai", "anthropic"], required=True)
    p.add_argument("--model", required=True, help="Model name (o3, o4-mini, claude-sonnet-4-20250514)")
    p.add_argument("--count", type=int, default=50, help="Number of calls to send")
    p.add_argument("--proxy-url", default="http://localhost:8000", help="Overage proxy base URL")
    p.add_argument("--api-key", required=True, help="Provider API key forwarded to the LLM")
    p.add_argument("--overage-key", default=None, help="Overage API key for proxy auth (X-API-Key)")
    return p.parse_args()


async def main() -> int:
    """Send calls through the proxy and report aggregate results."""
    args = parse_args()
    url = f"{args.proxy_url}/v1/proxy/{args.provider}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if args.provider == "openai":
        headers["Authorization"] = f"Bearer {args.api_key}"
    else:
        headers["x-api-key"] = args.api_key
    if args.overage_key:
        headers["X-API-Key"] = args.overage_key

    total_tokens, errors = 0, 0
    latencies: list[float] = []
    log.info("seed_started", provider=args.provider, model=args.model, count=args.count)
    async with httpx.AsyncClient(timeout=300.0) as client:
        for i in range(args.count):
            body: dict[str, Any] = {"model": args.model, "messages": [{"role": "user", "content": PROMPTS[i % len(PROMPTS)]}]}
            if args.provider == "anthropic":
                body["max_tokens"] = 4096
            t0 = time.perf_counter()
            try:
                resp = await client.post(url, json=body, headers=headers)
                ms = (time.perf_counter() - t0) * 1000.0
                resp.raise_for_status()
                usage = resp.json().get("usage", {})
                tokens = int(usage.get("completion_tokens" if args.provider == "openai" else "output_tokens", 0))
                total_tokens += tokens
                latencies.append(ms)
                log.info("call_complete", call=i + 1, of=args.count, tokens=tokens, latency_ms=round(ms, 1))
            except httpx.HTTPStatusError as exc:
                errors += 1
                log.error("call_failed", call=i + 1, status=exc.response.status_code)
            except httpx.RequestError as exc:
                errors += 1
                log.error("call_error", call=i + 1, error=str(exc))

    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    log.info("seed_complete", total_calls=args.count, successful=args.count - errors, errors=errors,
             total_reported_tokens=total_tokens, avg_latency_ms=round(avg_lat, 1))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

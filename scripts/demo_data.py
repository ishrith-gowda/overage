#!/usr/bin/env python3
"""Generate synthetic demo data for Overage demos and investor walkthroughs.

Produces realistic-looking API call logs and estimation results with
configurable discrepancy patterns — at zero API cost. The generated
data mimics real production traffic patterns:
  - Multiple providers (OpenAI, Anthropic)
  - Multiple models (o3, o4-mini, claude-sonnet-4)
  - Realistic latency distributions tied to token counts
  - Deliberate discrepancy patterns (systematic overcounting, model-specific)
  - Time distribution across the specified day range

Usage:
    python scripts/demo_data.py --calls 500 --days 30
    python scripts/demo_data.py --calls 1000 --days 90 --seed 42 --discrepancy-pct 18
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Configure logging before importing app modules
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Provider and model configurations for realistic data generation
# ---------------------------------------------------------------------------

PROVIDER_CONFIGS: list[dict[str, Any]] = [
    {
        "provider": "openai",
        "model": "o3",
        "weight": 0.40,  # 40% of traffic
        "tps": 55.0,
        "reasoning_range": (2000, 25000),
        "input_range": (50, 500),
        "output_range": (100, 3000),
        "price_per_million": 60.0,
        "base_discrepancy_pct": 18.0,  # o3 has the highest systematic overcounting
        "discrepancy_noise_std": 8.0,
    },
    {
        "provider": "openai",
        "model": "o4-mini",
        "weight": 0.25,
        "tps": 80.0,
        "reasoning_range": (500, 15000),
        "input_range": (30, 300),
        "output_range": (50, 2000),
        "price_per_million": 12.0,
        "base_discrepancy_pct": 12.0,
        "discrepancy_noise_std": 6.0,
    },
    {
        "provider": "openai",
        "model": "o3-mini",
        "weight": 0.10,
        "tps": 90.0,
        "reasoning_range": (200, 8000),
        "input_range": (20, 200),
        "output_range": (30, 1000),
        "price_per_million": 4.40,
        "base_discrepancy_pct": 8.0,
        "discrepancy_noise_std": 5.0,
    },
    {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "weight": 0.20,
        "tps": 65.0,
        "reasoning_range": (1000, 20000),
        "input_range": (50, 400),
        "output_range": (100, 2500),
        "price_per_million": 15.0,
        "base_discrepancy_pct": 6.0,  # Anthropic is more honest in our story
        "discrepancy_noise_std": 4.0,
    },
    {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "weight": 0.05,
        "tps": 65.0,
        "reasoning_range": (500, 12000),
        "input_range": (40, 350),
        "output_range": (80, 2000),
        "price_per_million": 15.0,
        "base_discrepancy_pct": 5.0,
        "discrepancy_noise_std": 3.5,
    },
]

DOMAINS = [
    "math_reasoning",
    "code_generation",
    "logical_reasoning",
    "creative_writing",
    "general_qa",
]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic demo data for Overage",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--calls", type=int, default=500, help="Number of API call logs to generate"
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Number of days of history to simulate"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--discrepancy-pct",
        type=float,
        default=None,
        help="Override base discrepancy %% for all models (default: use per-model configs)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL override (default: from .env / settings)",
    )
    return parser.parse_args()


def _pick_provider_config(rng: random.Random) -> dict[str, Any]:
    """Weighted random selection of a provider/model configuration."""
    weights = [c["weight"] for c in PROVIDER_CONFIGS]
    return rng.choices(PROVIDER_CONFIGS, weights=weights, k=1)[0]


def _generate_call(
    rng: random.Random,
    config: dict[str, Any],
    timestamp: datetime,
    user_id: int,
    discrepancy_override: float | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate a single synthetic call log and estimation result.

    Returns:
        Tuple of (call_log_dict, estimation_dict).
    """
    # Generate "true" reasoning tokens (what the model actually computed)
    r_min, r_max = config["reasoning_range"]
    true_reasoning = rng.randint(r_min, r_max)

    # Apply discrepancy to get "reported" tokens (what the provider claims)
    base_disc = discrepancy_override if discrepancy_override is not None else config["base_discrepancy_pct"]
    noise = rng.gauss(0, config["discrepancy_noise_std"])
    actual_discrepancy_pct = base_disc + noise
    # Some calls are accurate (no discrepancy) — about 30%
    if rng.random() < 0.30:
        actual_discrepancy_pct = rng.gauss(0, 3.0)
    reported_reasoning = max(0, int(true_reasoning * (1 + actual_discrepancy_pct / 100.0)))

    # Input/output tokens
    i_min, i_max = config["input_range"]
    o_min, o_max = config["output_range"]
    input_tokens = rng.randint(i_min, i_max)
    output_tokens = rng.randint(o_min, o_max)

    # Latency derived from true token count and TPS (with noise)
    tps = config["tps"] * rng.uniform(0.85, 1.15)  # ±15% TPS variation
    total_output = output_tokens + true_reasoning
    latency_ms = (total_output / tps) * 1000.0
    # Add network overhead (50-200ms)
    latency_ms += rng.uniform(50, 200)

    is_streaming = rng.random() < 0.3
    ttft_ms = rng.uniform(200, 1500) if is_streaming else None

    prompt_text = f"synthetic_prompt_{rng.randint(1, 100000)}"
    prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
    request_id = f"req_demo_{rng.randint(100000, 999999)}"

    # PALACE estimation: close to true but with its own noise
    palace_noise = rng.gauss(0, 0.08)  # ±8% estimation noise
    palace_estimated = max(0, int(true_reasoning * (1 + palace_noise)))
    palace_low = max(0, int(palace_estimated * 0.85))
    palace_high = int(palace_estimated * 1.15)

    # Timing estimation: latency-based
    timing_estimated = max(0, int((latency_ms / 1000.0) * tps) - output_tokens)

    # Combined (weighted average)
    combined = int(0.7 * palace_estimated + 0.3 * timing_estimated)
    if combined == 0:
        combined = true_reasoning

    disc_pct = (reported_reasoning - combined) / combined * 100.0 if combined > 0 else 0.0
    token_diff = reported_reasoning - combined
    dollar_impact = token_diff * (config["price_per_million"] / 1_000_000.0)

    # Signals agree?
    if palace_estimated > 0 and timing_estimated > 0:
        ratio = abs(palace_estimated - timing_estimated) / max(palace_estimated, timing_estimated)
        signals_agree = ratio <= 0.20
    else:
        signals_agree = True

    domain = rng.choice(DOMAINS)

    # Check honoring
    honoring = palace_low <= reported_reasoning <= palace_high

    call_dict = {
        "user_id": user_id,
        "provider": config["provider"],
        "model": config["model"],
        "endpoint": "/v1/chat/completions" if config["provider"] == "openai" else "/v1/messages",
        "prompt_hash": prompt_hash,
        "prompt_length_chars": rng.randint(100, 5000),
        "answer_length_chars": rng.randint(200, 10000),
        "reported_input_tokens": input_tokens,
        "reported_output_tokens": output_tokens,
        "reported_reasoning_tokens": reported_reasoning,
        "total_latency_ms": round(latency_ms, 1),
        "ttft_ms": round(ttft_ms, 1) if ttft_ms else None,
        "is_streaming": is_streaming,
        "raw_usage_json": json.dumps({
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "reasoning_tokens": reported_reasoning,
        }),
        "timestamp": timestamp,
        "request_id": request_id,
    }

    estimation_dict = {
        "palace_estimated_tokens": palace_estimated,
        "palace_confidence_low": palace_low,
        "palace_confidence_high": palace_high,
        "palace_model_version": "v0.1.0",
        "timing_estimated_tokens": timing_estimated,
        "timing_tps_used": round(tps, 2),
        "timing_r_squared": round(rng.uniform(0.95, 0.999), 4),
        "combined_estimated_tokens": combined,
        "discrepancy_pct": round(disc_pct, 2),
        "dollar_impact": round(dollar_impact, 4),
        "signals_agree": signals_agree,
        "domain_classification": domain,
        "estimated_at": timestamp + timedelta(seconds=rng.uniform(1, 5)),
    }

    return call_dict, estimation_dict


async def main() -> int:
    """Generate demo data and insert into the database."""
    args = parse_args()
    rng = random.Random(args.seed)

    logger.info(
        "demo_generation_started",
        calls=args.calls,
        days=args.days,
        seed=args.seed,
    )

    # Import app modules after args are parsed
    import os
    if args.db_url:
        os.environ["DATABASE_URL"] = args.db_url

    from proxy.demo_constants import DEMO_PLAINTEXT_API_KEY
    from proxy.storage.database import get_session_factory, init_db, init_engine
    from proxy.storage.models import APICallLog, APIKey, EstimationResult, User

    init_engine(args.db_url)
    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        # Create demo user
        demo_user = User(
            email="demo@overage.dev",
            name="Demo User",
            password_hash=hashlib.sha256(b"demopassword").hexdigest(),
        )
        session.add(demo_user)
        await session.flush()

        # Create demo API key
        raw_key = DEMO_PLAINTEXT_API_KEY
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = APIKey(user_id=demo_user.id, key_hash=key_hash, name="Demo Key")
        session.add(api_key)
        await session.flush()

        # Generate timestamps distributed across the date range
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=args.days)

        total_dollars = 0.0
        total_discrepancy = 0.0

        for i in range(args.calls):
            # Distribute calls with slight weekday bias (more on weekdays)
            ts = start + timedelta(
                seconds=rng.uniform(0, args.days * 86400)
            )
            # Add weekday bias: 70% chance of being a weekday
            while ts.weekday() >= 5 and rng.random() < 0.5:
                ts += timedelta(days=rng.choice([1, 2]))

            config = _pick_provider_config(rng)
            call_dict, est_dict = _generate_call(
                rng, config, ts, demo_user.id, args.discrepancy_pct
            )

            call_log = APICallLog(**call_dict)
            session.add(call_log)
            await session.flush()

            estimation = EstimationResult(call_id=call_log.id, **est_dict)
            session.add(estimation)

            total_dollars += est_dict["dollar_impact"]
            total_discrepancy += est_dict["discrepancy_pct"]

            if (i + 1) % 100 == 0:
                logger.info("demo_progress", calls_generated=i + 1, total=args.calls)

        await session.commit()

    avg_discrepancy = total_discrepancy / args.calls if args.calls > 0 else 0

    logger.info(
        "demo_generation_complete",
        calls_generated=args.calls,
        days=args.days,
        total_dollar_impact=round(total_dollars, 2),
        avg_discrepancy_pct=round(avg_discrepancy, 2),
        demo_api_key=raw_key[:20] + "...",
    )

    print(f"\n{'=' * 60}")
    print(f"  Demo data generated successfully!")
    print(f"  Calls: {args.calls}")
    print(f"  Date range: {args.days} days")
    print(f"  Avg discrepancy: {avg_discrepancy:.1f}%")
    print(f"  Total $ impact: ${total_dollars:,.2f}")
    print(f"  Demo API key: {raw_key}")
    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

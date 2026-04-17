"""Overage quickstart — route OpenAI through the proxy and read discrepancy data.

Requires: ``pip install -e ".[dev]"`` from repo root (or ``overage`` + ``openai`` from PyPI),
``OVERAGE_API_KEY`` (from ``POST /v1/auth/register`` or ``make demo``), and ``OPENAI_API_KEY``.
"""

import os

from openai import OpenAI

from overage import OverageClient


def main() -> None:
    # 1. Create your OpenAI client as usual.
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # 2. One-line change: patch the client to route through Overage.
    overage = OverageClient(api_key=os.environ["OVERAGE_API_KEY"])
    overage.patch_openai(openai_client)

    # 3. Use OpenAI exactly as before — all calls now flow through the
    #    Overage proxy, which records reasoning-token usage.
    response = openai_client.chat.completions.create(
        model="o3-mini",
        messages=[{"role": "user", "content": "Explain quantum tunneling briefly."}],
    )
    print("=== Model response ===")
    print(response.choices[0].message.content)

    # 4. Check the discrepancy summary to see billed vs. observed tokens.
    summary = overage.get_summary()
    print("\n=== Overage discrepancy summary ===")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # 5. Browse individual call logs (GET /v1/calls → ``calls`` + ``total``).
    calls = overage.get_calls(limit=5)
    rows = calls.get("calls", [])
    print(f"\n=== Last {len(rows)} recorded calls ===")
    for record in rows:
        model = record.get("model")
        reported = record.get("reported_reasoning_tokens")
        estimated = record.get("estimated_reasoning_tokens")
        print(f"  {model}  reported_reasoning={reported}  estimated={estimated}")

    overage.close()


if __name__ == "__main__":
    main()

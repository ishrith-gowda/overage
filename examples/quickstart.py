"""Overage quickstart — audit your OpenAI reasoning-token billing in 1 line.

Install dependencies first:
    pip install overage openai
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

    # 5. Browse individual call logs.
    calls = overage.get_calls(limit=5)
    print(f"\n=== Last {len(calls.get('records', []))} recorded calls ===")
    for record in calls.get("records", []):
        print(
            f"  {record.get('model')}  billed={record.get('billed_tokens')}  "
            f"observed={record.get('observed_tokens')}"
        )

    overage.close()


if __name__ == "__main__":
    main()

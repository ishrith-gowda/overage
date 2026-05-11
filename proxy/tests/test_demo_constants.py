"""Regression guard for the seeded demo API key (demo_data + screenshot tooling)."""

from __future__ import annotations

from proxy.demo_constants import DEMO_PLAINTEXT_API_KEY


def test_demo_plaintext_api_key_has_expected_prefix_and_length() -> None:
    assert DEMO_PLAINTEXT_API_KEY.startswith("ovg_live_demo_key_")
    assert len(DEMO_PLAINTEXT_API_KEY) >= 32

"""Overage Streamlit Dashboard — 5-panel audit interface.

Panels:
  1. Summary metrics row (KPIs)
  2. Time-series discrepancy chart
  3. Per-call table with color-coded discrepancy
  4. Timing scatter plot with regression line
  5. Cost impact calculator

Reference: PRD.md Section 3 (User Stories), ARCHITECTURE.md Section 2.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration and custom CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Overage — Reasoning Token Audit",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom dark-theme accent styling
st.markdown(
    """
    <style>
    /* Accent color: electric blue */
    .stMetric > div > div > div > div {
        color: #4FC3F7;
    }
    .stMetric label {
        font-size: 0.9rem !important;
    }
    /* Highlight overcharged rows */
    .high-discrepancy {
        background-color: rgba(244, 67, 54, 0.15);
    }
    /* Footer */
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        text-align: center;
        padding: 8px;
        font-size: 0.75rem;
        color: #888;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🔍 Overage — Reasoning Token Audit Dashboard")

# ---------------------------------------------------------------------------
# Sidebar — configuration and filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Configuration")

    api_url = st.text_input(
        "Proxy API URL",
        value="http://localhost:8000",
        help="Base URL for the Overage proxy API",
    )
    api_key = st.text_input(
        "API Key",
        value="",
        type="password",
        help="Your Overage API key (X-API-Key header)",
    )

    st.divider()
    st.header("Filters")

    date_range = st.date_input(
        "Date Range",
        value=(date.today() - timedelta(days=30), date.today()),
        max_value=date.today(),
    )

    provider_filter = st.multiselect(
        "Providers",
        options=["openai", "anthropic", "gemini"],
        default=[],
        help="Leave empty for all providers",
    )

    model_filter = st.multiselect(
        "Models",
        options=[
            "o3",
            "o4-mini",
            "o3-mini",
            "claude-sonnet-4-20250514",
            "gemini-2.0-flash-thinking",
        ],
        default=[],
        help="Leave empty for all models",
    )

    st.divider()
    auto_refresh = st.toggle("Auto-refresh (30s)", value=False)
    if auto_refresh:
        st.caption("Dashboard refreshes every 30 seconds")


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    """Build request headers with the API key."""
    h: dict[str, str] = {}
    if api_key:
        h["X-API-Key"] = api_key
    return h


def _params() -> dict[str, str]:
    """Build common query parameters from sidebar filters."""
    p: dict[str, str] = {}
    if isinstance(date_range, tuple) and len(date_range) == 2:
        p["start_date"] = str(date_range[0])
        p["end_date"] = str(date_range[1])
    if provider_filter:
        p["provider"] = provider_filter[0]  # API supports single provider for now
    if model_filter:
        p["model"] = model_filter[0]
    return p


@st.cache_data(ttl=30 if auto_refresh else 300)
def fetch_summary(url: str, key: str, params_key: str) -> dict[str, Any] | None:
    """Fetch aggregate summary stats from the API."""
    try:
        resp = httpx.get(
            f"{url}/v1/summary",
            headers=_headers(),
            params=_params(),
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


@st.cache_data(ttl=30 if auto_refresh else 300)
def fetch_calls(url: str, key: str, params_key: str) -> list[dict[str, Any]]:
    """Fetch recent call logs from the API."""
    try:
        resp = httpx.get(
            f"{url}/v1/calls",
            headers=_headers(),
            params={**_params(), "limit": "200"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("calls", [])
    except Exception:
        return []


@st.cache_data(ttl=30 if auto_refresh else 300)
def fetch_timeseries(url: str, key: str, params_key: str) -> list[dict[str, Any]]:
    """Fetch time-series data from the API."""
    try:
        resp = httpx.get(
            f"{url}/v1/summary/timeseries",
            headers=_headers(),
            params=_params(),
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except Exception:
        return []


# Cache key includes filters so data refreshes when filters change
_cache_key = f"{api_url}|{api_key}|{date_range!s}|{provider_filter!s}|{model_filter!s}"

# ---------------------------------------------------------------------------
# Fetch data
# ---------------------------------------------------------------------------

if not api_key:
    st.info(
        "👈 Enter your **API Key** in the sidebar to connect to the Overage proxy. "
        "If you're running locally, generate one with `POST /v1/auth/register`."
    )
    st.stop()

with st.spinner("Fetching data from Overage API..."):
    summary = fetch_summary(api_url, api_key, _cache_key)
    calls = fetch_calls(api_url, api_key, _cache_key)
    timeseries = fetch_timeseries(api_url, api_key, _cache_key)

if summary is None:
    st.error(
        f"❌ Could not connect to the Overage API at `{api_url}`. "
        "Check that the proxy is running and the API key is valid."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Panel 1: Summary Metrics (KPIs)
# ---------------------------------------------------------------------------

st.header("📊 Summary")

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric("Total Calls", f"{summary.get('total_calls', 0):,}")
with col2:
    reported = summary.get("total_reported_reasoning_tokens", 0)
    st.metric("Reported Tokens", f"{reported:,}")
with col3:
    estimated = summary.get("total_estimated_reasoning_tokens", 0)
    st.metric("Estimated Tokens", f"{estimated:,}")
with col4:
    disc = summary.get("aggregate_discrepancy_pct", 0)
    st.metric("Discrepancy", f"{disc:+.1f}%", delta=f"{disc:+.1f}%", delta_color="inverse")
with col5:
    dollars = summary.get("total_dollar_impact", 0)
    st.metric("$ Impact", f"${dollars:,.2f}")
with col6:
    honoring = summary.get("honoring_rate_pct", 0)
    st.metric("Honoring Rate", f"{honoring:.1f}%")

st.divider()

# ---------------------------------------------------------------------------
# Panel 2: Time-Series Discrepancy Chart
# ---------------------------------------------------------------------------

st.header("📈 Discrepancy Over Time")

if timeseries:
    ts_df = pd.DataFrame(timeseries)
    ts_df["date"] = pd.to_datetime(ts_df["date"])

    fig_ts = go.Figure()
    fig_ts.add_trace(
        go.Scatter(
            x=ts_df["date"],
            y=ts_df["reported_reasoning_tokens"],
            mode="lines+markers",
            name="Reported Tokens",
            line={"color": "#EF5350", "width": 2},
        )
    )
    fig_ts.add_trace(
        go.Scatter(
            x=ts_df["date"],
            y=ts_df["estimated_reasoning_tokens"],
            mode="lines+markers",
            name="Estimated Tokens",
            line={"color": "#4FC3F7", "width": 2},
        )
    )
    # Shaded area between reported and estimated
    fig_ts.add_trace(
        go.Scatter(
            x=pd.concat([ts_df["date"], ts_df["date"][::-1]]),
            y=pd.concat(
                [ts_df["reported_reasoning_tokens"], ts_df["estimated_reasoning_tokens"][::-1]]
            ),
            fill="toself",
            fillcolor="rgba(244, 67, 54, 0.1)",
            line={"color": "rgba(0,0,0,0)"},
            name="Gap (Potential Overcharge)",
            showlegend=True,
        )
    )
    fig_ts.update_layout(
        xaxis_title="Date",
        yaxis_title="Reasoning Tokens",
        height=400,
        template="plotly_dark",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    st.plotly_chart(fig_ts, use_container_width=True)
else:
    st.info("No time-series data available for the selected period.")

st.divider()

# ---------------------------------------------------------------------------
# Panel 3: Per-Call Table
# ---------------------------------------------------------------------------

st.header("📋 Recent Calls")

if calls:
    df = pd.DataFrame(calls)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    display_cols = [
        "id",
        "provider",
        "model",
        "reported_reasoning_tokens",
        "estimated_reasoning_tokens",
        "discrepancy_pct",
        "timing_r_squared",
        "signals_agree",
        "total_latency_ms",
        "is_streaming",
        "timestamp",
    ]
    available_cols = [c for c in display_cols if c in df.columns]

    display_df = df[available_cols].copy()

    def _highlight_high_discrepancy(row: pd.Series) -> list[str]:
        """Highlight rows where |discrepancy_pct| >= 15 (PRD Story 3)."""
        n = len(row)
        if "discrepancy_pct" not in row.index:
            return [""] * n
        disc = row["discrepancy_pct"]
        if pd.notna(disc) and abs(float(disc)) >= 15.0:
            return ["background-color: rgba(244, 67, 54, 0.2)"] * n
        return [""] * n

    if "discrepancy_pct" in display_df.columns and not display_df.empty:
        st.dataframe(
            display_df.style.apply(_highlight_high_discrepancy, axis=1),
            use_container_width=True,
            height=400,
        )
    else:
        st.dataframe(display_df, use_container_width=True, height=400)
    st.caption(f"Showing {len(df)} calls. Use sidebar filters to narrow results.")
else:
    st.info("No calls recorded yet. Start proxying API calls through Overage.")

st.divider()

# ---------------------------------------------------------------------------
# Panel 4: Timing Scatter Plot
# ---------------------------------------------------------------------------

st.header("⏱️ Timing Analysis")

if calls:
    timing_df = pd.DataFrame(calls)
    if "total_latency_ms" in timing_df.columns and "reported_reasoning_tokens" in timing_df.columns:
        timing_df = timing_df[
            (timing_df["total_latency_ms"] > 0) & (timing_df["reported_reasoning_tokens"] > 0)
        ]

        if len(timing_df) > 5:
            fig_scatter = px.scatter(
                timing_df,
                x="total_latency_ms",
                y="reported_reasoning_tokens",
                color="provider" if "provider" in timing_df.columns else None,
                hover_data=["model", "id"] if "model" in timing_df.columns else None,
                title="Response Time vs. Reported Reasoning Tokens",
                labels={
                    "total_latency_ms": "Response Time (ms)",
                    "reported_reasoning_tokens": "Reported Reasoning Tokens",
                },
                template="plotly_dark",
            )

            # Add regression line
            x_vals = timing_df["total_latency_ms"].values
            y_vals = timing_df["reported_reasoning_tokens"].values
            if len(x_vals) > 2:
                coeffs = np.polyfit(x_vals, y_vals, 1)
                r_squared = 1 - (
                    np.sum((y_vals - np.polyval(coeffs, x_vals)) ** 2)
                    / np.sum((y_vals - np.mean(y_vals)) ** 2)
                )
                x_line = np.linspace(x_vals.min(), x_vals.max(), 100)
                y_line = np.polyval(coeffs, x_line)
                fig_scatter.add_trace(
                    go.Scatter(
                        x=x_line,
                        y=y_line,
                        mode="lines",
                        name=f"Regression (R²={r_squared:.3f})",
                        line={"color": "#FFD54F", "dash": "dash", "width": 2},
                    )
                )

            fig_scatter.update_layout(height=400)
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Need at least 5 data points for timing analysis.")
    else:
        st.info("Timing data not available.")
else:
    st.info("No calls available for timing analysis.")

st.divider()

# ---------------------------------------------------------------------------
# Panel 5: Cost Impact Calculator
# ---------------------------------------------------------------------------

st.header("💰 Cost Impact Calculator")

st.markdown(
    "Estimate the annual cost of unverified reasoning token billing at different discrepancy rates."
)

calc_col1, calc_col2 = st.columns([1, 2])

with calc_col1:
    monthly_spend = st.number_input(
        "Monthly LLM Spend ($)",
        min_value=0,
        max_value=10_000_000,
        value=100_000,
        step=10_000,
        help="Your total monthly LLM API spend",
    )
    reasoning_pct = st.slider(
        "Reasoning Token % of Bill",
        min_value=0,
        max_value=100,
        value=70,
        help="Percentage of your bill that is reasoning/thinking tokens",
    )

with calc_col2:
    reasoning_spend = monthly_spend * (reasoning_pct / 100.0)

    scenarios = {
        "5% discrepancy": reasoning_spend * 0.05,
        "10% discrepancy": reasoning_spend * 0.10,
        "15% discrepancy": reasoning_spend * 0.15,
        "20% discrepancy": reasoning_spend * 0.20,
    }

    scenario_df = pd.DataFrame(
        {
            "Scenario": list(scenarios.keys()),
            "Monthly Overcharge": [f"${v:,.0f}" for v in scenarios.values()],
            "Annual Overcharge": [f"${v * 12:,.0f}" for v in scenarios.values()],
        }
    )

    st.dataframe(scenario_df, use_container_width=True, hide_index=True)

    # Highlight the actual observed discrepancy
    actual_disc = abs(summary.get("aggregate_discrepancy_pct", 0))
    if actual_disc > 0:
        actual_monthly = reasoning_spend * (actual_disc / 100.0)
        st.success(
            f"**Your actual observed discrepancy: {actual_disc:.1f}%**  \n"
            f"Estimated monthly overcharge: **${actual_monthly:,.0f}**  \n"
            f"Estimated annual overcharge: **${actual_monthly * 12:,.0f}**"
        )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="footer">Powered by <strong>Overage</strong> — '
    "Independent audit layer for LLM reasoning token billing</div>",
    unsafe_allow_html=True,
)

# Auto-refresh
if auto_refresh:
    import time

    time.sleep(30)
    st.rerun()

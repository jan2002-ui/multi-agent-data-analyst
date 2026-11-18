"""Streamlit dashboard for the Multi-Agent Data Analyst.  Run with: streamlit run app.py"""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from analyst import AnalysisConfig, __version__, run_analysis
from analyst.io import DataLoadError
from analyst.llm import llm_available
from ui import tabs
from ui.components import hero
from ui.styles import CSS

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "data" / "sample" / "sales_dataset.csv"

st.set_page_config(page_title="Multi-Agent Data Analyst", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)


def execute(source, name: str, config: AnalysisConfig) -> None:
    """Run the pipeline with live progress and store the result in session state."""
    bar = st.progress(0.0, text="Starting agents…")

    def on_progress(i: int, n: int, result) -> None:
        bar.progress(i / n, text=f"{result.title} · {result.status}")

    try:
        st.session_state["ctx"] = run_analysis(source, config, progress=on_progress, source_name=name)
        st.session_state.pop("error", None)
    except (DataLoadError, ValueError) as exc:
        st.session_state["error"] = str(exc)
        st.session_state.pop("ctx", None)
    finally:
        bar.empty()


# ───────────────────────────── Sidebar ─────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-brand">📊 Multi-Agent Analyst</div>'
                f'<div class="sidebar-sub">v{__version__} · 10 specialised agents</div>', unsafe_allow_html=True)
    mode = st.radio("Data source", ["Sample dataset", "Upload CSV"], label_visibility="collapsed")
    upload = st.file_uploader("CSV file", type=["csv"]) if mode == "Upload CSV" else None

    with st.expander("⚙️ Analysis settings"):
        contamination = st.slider("Anomaly sensitivity", 0.5, 10.0, 2.0, 0.5, format="%.1f%%",
                                  help="Expected share of unusual order lines.") / 100
        horizon = st.slider("Forecast horizon (months)", 1, 12, 3)
        top_n = st.slider("Rows in top-N tables", 5, 50, 15, 5)
        use_llm = st.toggle("LLM-polished summary", value=False, disabled=not llm_available(),
                            help="Requires ANTHROPIC_API_KEY. Only aggregated figures are sent, never rows.")
    run_clicked = st.button("▶ Run analysis", type="primary")
    st.divider()
    st.caption("Agents: Quality · Profiling · Cleaning · EDA · Anomalies · Customers · Forecasting · "
               "Insights · Summary · Report")

config = AnalysisConfig(contamination=contamination, forecast_horizon=horizon, top_n=top_n, use_llm=use_llm)
fingerprint = (mode, hashlib.md5(upload.getvalue()).hexdigest() if upload else None, contamination, horizon, top_n, use_llm)

# Auto-run on first load / whenever inputs change (sample) or when the user clicks Run (upload).
needs_run = st.session_state.get("fingerprint") != fingerprint
if mode == "Sample dataset" and (needs_run or run_clicked):
    if SAMPLE.exists():
        execute(SAMPLE, SAMPLE.name, config)
        st.session_state["fingerprint"] = fingerprint
    else:
        st.session_state["error"] = f"Sample dataset not found at {SAMPLE}."
elif mode == "Upload CSV" and upload is not None and (needs_run or run_clicked):
    execute(upload.getvalue(), upload.name, config)
    st.session_state["fingerprint"] = fingerprint

# ───────────────────────────── Main ─────────────────────────────
ctx = st.session_state.get("ctx")

if "error" in st.session_state:
    st.error(st.session_state["error"])

if ctx is None:
    hero("Multi-Agent Data Analyst", "Upload a sales CSV to run a ten-agent analysis: quality, KPIs, anomalies, "
         "customer segments, forecasts and ranked business insights.", ["pandas", "scikit-learn", "Plotly", "Streamlit"])
    st.info("Choose **Upload CSV** in the sidebar and drop in a file, or switch to the sample dataset. "
            "Columns are detected automatically (e.g. `net_sales`, `sales` or `revenue` all work).")
    st.stop()

hero("Multi-Agent Data Analyst", f"{ctx.source_name} · {len(ctx.raw):,} rows × {ctx.raw.shape[1]} columns",
     [f"{sum(r.ok for r in ctx.results.values())}/{len(ctx.results)} agents succeeded",
      f"{ctx.total_duration_ms / 1000:.1f}s runtime", f"revenue field: {ctx.schema.get('revenue') or 'not found'}",
      f"currency: {ctx.schema.currency or 'unknown'}"])

failed = [r for r in ctx.results.values() if r.status == "failed"]
for r in failed:
    st.warning(f"{r.title} failed: {r.message}")

names = ["Overview", "Sales", "Customers", "Anomalies", "Forecast", "Data quality", "Agents & export"]
for tab, render in zip(st.tabs(names), (tabs.overview, tabs.sales, tabs.customers, tabs.anomalies,
                                         tabs.forecast, tabs.quality, tabs.pipeline), strict=True):
    with tab:
        render(ctx)

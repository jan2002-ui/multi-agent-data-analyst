"""One render function per dashboard tab. All functions are read-only over the AnalysisContext."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analyst import viz
from analyst.context import AnalysisContext
from analyst.utils import money, pct
from ui.components import insight_card, kpi_grid, pill, section, show_chart, show_table


def _unavailable(ctx: AnalysisContext, agent: str) -> bool:
    result = ctx.results.get(agent)
    if result and result.ok:
        return False
    st.info(f"This section needs the {result.title if result else agent}, which was "
            f"{result.status if result else 'not run'}: {result.message if result else ''}")
    return True


def overview(ctx: AnalysisContext) -> None:
    sym = ctx.schema.symbol
    summary = ctx.data("summary")
    if summary:
        tag = "written by an LLM" if summary["source"] == "llm" else "rule-based summary"
        st.markdown(f'<div class="summary">{summary["text"]}<br><small>Executive summary · {tag}</small></div>',
                    unsafe_allow_html=True)
    k, dq = ctx.data("eda").get("kpis", {}), ctx.data("data_quality")
    if k:
        items = [("Revenue", money(k["revenue"], sym), f"{k.get('date_start', '')} → {k.get('date_end', '')}"),
                 ("Orders", f"{k['orders']:,}", f"{k['order_lines']:,} order lines"),
                 ("Avg order value", money(k["aov"], sym), "revenue ÷ orders")]
        if "profit" in k:
            items += [("Profit", money(k["profit"], sym), f"{k['loss_making_lines']} loss-making lines"),
                      ("Margin", pct(k["margin_pct"]), "profit ÷ revenue")]
        if "customers" in k:
            items.append(("Customers", f"{k['customers']:,}", "unique buyers"))
        if "return_rate_pct" in k:
            items.append(("Return rate", pct(k["return_rate_pct"]), "of order lines"))
        if dq:
            items.append(("Data quality", f"{dq['score']:.0f}/100", dq["status"]))
        kpi_grid(items)

    insights = ctx.data("insights").get("insights", [])
    if insights:
        section("Key findings", "Ranked by severity. Each finding links evidence to a suggested next step.")
        for item in insights[:6]:
            insight_card(item)
        if len(insights) > 6:
            with st.expander(f"Show all {len(insights)} findings"):
                for item in insights[6:]:
                    insight_card(item)

    monthly = ctx.data("eda").get("monthly")
    if monthly:
        show_chart(viz.revenue_trend(monthly, ctx.data("forecasting") or None, sym), "ov_trend")


def sales(ctx: AnalysisContext) -> None:
    if _unavailable(ctx, "eda"):
        return
    eda, sym = ctx.data("eda"), ctx.schema.symbol
    blocks = eda["breakdowns"]
    if blocks:
        section("Performance breakdown", "Bar length = revenue, colour = profit margin.")
        role = st.radio("Break down by", list(blocks), format_func=lambda r: blocks[r]["label"],
                        horizontal=True, label_visibility="collapsed")
        block = blocks[role]
        left, right = st.columns([3, 2])
        with left:
            show_chart(viz.breakdown_bar(block["rows"], block["label"], sym), f"sales_{role}")
        with right:
            show_table(block["rows"], column_config={"name": block["label"], "revenue": st.column_config.NumberColumn(
                "Revenue", format=f"{sym}%.0f"), "margin_pct": st.column_config.NumberColumn("Margin %", format="%.1f"),
                "share_pct": st.column_config.NumberColumn("Share %", format="%.1f")},
                column_order=[c for c in ("name", "revenue", "margin_pct", "share_pct") if c in block["rows"][0]])
    if eda["discount_bands"]:
        section("Discount impact", "How margin erodes as discount depth increases.")
        left, right = st.columns([3, 2])
        with left:
            show_chart(viz.discount_chart(eda["discount_bands"]), "sales_discount")
        with right:
            show_table(eda["discount_bands"], column_order=["band", "lines", "revenue", "margin_pct"])
    left, right = st.columns(2)
    with left:
        if eda["top_products"]:
            section("Top products")
            show_table(eda["top_products"], column_order=["name", "revenue", "profit", "margin_pct", "orders"])
    with right:
        if eda["leakage"]:
            section("Revenue leakage", "Revenue on cancelled, refunded or failed orders.")
            show_table(eda["leakage"])
        if eda["returns"].get("top_reasons"):
            section("Return reasons")
            show_table(eda["returns"]["top_reasons"])


def customers(ctx: AnalysisContext) -> None:
    if _unavailable(ctx, "customers"):
        return
    c, sym = ctx.data("customers"), ctx.schema.symbol
    conc = c["concentration"]
    kpi_grid([("Customers", f"{conc['customers']:,}", "unique buyers"),
              ("Top customer share", pct(conc["top_customer_share_pct"]), conc["top_customer"]),
              ("Top 10% of customers", pct(conc["top_10pct_customers_share_pct"]), "share of revenue"),
              ("Repeat rate", pct(conc["repeat_customer_rate_pct"]), "ordered 2+ times"),
              ("Revenue / customer", money(conc["avg_revenue_per_customer"], sym), f"{conc['avg_orders_per_customer']:.1f} orders avg")])
    left, right = st.columns(2)
    with left:
        if c["segments"]:
            show_chart(viz.rfm_chart(c["segments"]), "cust_rfm")
        else:
            st.info(c.get("rfm_note") or "RFM unavailable.")
    with right:
        show_chart(viz.pareto_chart(c["pareto"]), "cust_pareto")
    if c["segments"]:
        section("Segment definitions", "RFM scores each customer 1-5 on recency, frequency and monetary value.")
        show_table(c["segments"], column_order=["segment", "customers", "revenue", "revenue_share_pct",
                                                "avg_recency_days", "avg_orders"])
    section("Top customers by revenue")
    show_table(c["top_customers"])


def anomalies(ctx: AnalysisContext) -> None:
    if _unavailable(ctx, "anomalies"):
        return
    a, sym = ctx.data("anomalies"), ctx.schema.symbol
    kpi_grid([("Flagged order lines", f"{a['flagged']:,}", f"{pct(a['flagged_pct'])} of {a['total_records']:,}"),
              ("Revenue in flagged lines", money(a["revenue_in_flagged"], sym), "worth reviewing first"),
              ("Model", "Isolation Forest", f"contamination {a['contamination']:.0%}"),
              ("Features used", str(len(a["features"])), "business measures only")])
    flags = ctx.artifacts["anomaly_flags"]
    f = a["features"]
    x = ctx.schema.get("revenue")
    y = ctx.schema.get("profit") or next(c for c in f if c != x)
    show_chart(viz.anomaly_scatter(ctx.df, flags, x, y), "anom_scatter")
    section("Most unusual order lines", "“Drivers” show which measures deviate most from the median (robust σ).")
    show_table(a["top_records"])
    left, right = st.columns(2)
    with left:
        if a["validation"]:
            section("Agreement with source-system flags",
                    "How many rows already flagged in the data are also caught by the model. Low overlap means "
                    "those flags capture signals other than unusual order values.")
            show_table([{"flag": k, **v} for k, v in a["validation"].items()])
    with right:
        if a["excluded_leakage_columns"]:
            section("Leakage guard", "Pre-computed model outputs were excluded so the model cannot learn from them.")
            st.code(", ".join(a["excluded_leakage_columns"]), language=None)
    with st.expander("Univariate IQR screening"):
        show_table(a["iqr"])


def forecast(ctx: AnalysisContext) -> None:
    if _unavailable(ctx, "forecasting"):
        return
    fc, sym = ctx.data("forecasting"), ctx.schema.symbol
    kpi_grid([("Selected model", fc["model"], f"best of {len(fc['backtest'])} on backtest"),
              ("Backtest error", pct(fc["backtest"][0]["mape_pct"]), f"MAPE over last {fc['backtest_months']} months"),
              (f"Next {len(fc['forecast'])} months", money(fc["forecast_total"], sym), "projected total"),
              ("Long-run trend", f"{fc['trend_pct_per_month']:+.1f}% / month", "linear fit over history")])
    show_chart(viz.revenue_trend(ctx.data("eda")["monthly"], fc, sym), "fc_trend")
    left, right = st.columns(2)
    with left:
        section("Forecast", "Shaded band is an 80% prediction interval from backtest error.")
        show_table(fc["forecast"])
    with right:
        show_chart(viz.backtest_chart(fc["backtest"]), "fc_backtest")
    if fc["excluded_partial_month"]:
        st.caption(f"{fc['excluded_partial_month']} is incomplete and was excluded from training.")
    st.caption(fc["disclaimer"])


def quality(ctx: AnalysisContext) -> None:
    if _unavailable(ctx, "data_quality"):
        return
    dq = ctx.data("data_quality")
    left, right = st.columns(2)
    with left:
        show_chart(viz.quality_gauge(dq["score"]), "dq_gauge")
    with right:
        show_chart(viz.dimension_bars(dq["dimensions"]), "dq_dims")
    st.caption("Score = 35% completeness (core fields) + 30% validity (business rules) + 20% uniqueness + 15% consistency.")
    section("Findings")
    icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}
    for i in dq["issues"]:
        st.markdown(f"{icon[i['severity']]} **{i['check'].replace('_', ' ').title()}** — {i['message']}")
    cleaning = ctx.data("cleaning")
    if cleaning:
        section("Cleaning log", cleaning["note"])
        show_table(cleaning["actions"] or [{"action": "none", "detail": "No changes were necessary.", "count": 0}])
    if dq["missing_by_column"]:
        with st.expander("Missing values by column"):
            show_table(dq["missing_by_column"])
    profile = ctx.data("profiling")
    if profile:
        with st.expander(f"Column profile ({profile['columns']} columns, {profile['memory_mb']} MB)"):
            show_table(profile["column_profile"])
        with st.expander("Detected business roles"):
            st.json(profile["schema"]["roles"])


def pipeline(ctx: AnalysisContext) -> None:
    section("Agent pipeline", "Each agent reads the shared context, publishes its findings, and fails in isolation.")
    rows = "".join(
        f"<tr><td>{i}</td><td><b>{r.title}</b></td><td>{pill(r.status)}</td>"
        f"<td>{r.duration_ms:,.0f} ms</td><td>{r.message or ''}</td></tr>" for i, r in enumerate(ctx.results.values(), 1))
    st.markdown(f"<table style='width:100%'><tr><th>#</th><th>Agent</th><th>Status</th><th>Time</th><th>Note</th></tr>{rows}</table>",
                unsafe_allow_html=True)
    st.caption(f"Total pipeline time: {ctx.total_duration_ms / 1000:.2f}s")
    dot = ("digraph { rankdir=LR; bgcolor=transparent; node [shape=box style='rounded,filled' fillcolor='#1E293B' "
           "fontcolor='#E2E8F0' color='#6366F1' fontname=Helvetica]; edge [color='#64748B']; "
           "Data [shape=cylinder fillcolor='#312E81']; Context [label='Shared\\ncontext' shape=component fillcolor='#0E7490']; "
           "Data -> Context; Context -> {Quality Profiling Cleaning} -> EDA; EDA -> {Anomalies Customers Forecasting} "
           "-> Insights -> Summary -> Report; }")
    st.graphviz_chart(dot)

    section("Export")
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇ HTML executive report", ctx.artifacts.get("report_html", ""), "analysis_report.html",
                       "text/html", disabled="report_html" not in ctx.artifacts, key="dl_html")
    c2.download_button("⬇ JSON results", ctx.artifacts.get("report_json", ""), "analysis_results.json",
                       "application/json", disabled="report_json" not in ctx.artifacts, key="dl_json")
    clean: pd.DataFrame = ctx.df.drop(columns=[c for c in ctx.df.columns if c.startswith("_")])
    c3.download_button("⬇ Cleaned dataset (CSV)", clean.to_csv(index=False), "cleaned_dataset.csv", "text/csv", key="dl_csv")

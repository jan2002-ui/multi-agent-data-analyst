"""One render function per dashboard tab. All functions are read-only over the AnalysisContext."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analyst import viz
from analyst.context import AnalysisContext
from analyst.dashboard import (
    Filters,
    apply_filters,
    group_revenue,
    matrix,
    month_over_month,
    monthly_frame,
    slicer_options,
    sparkline_values,
    totals,
)
from analyst.utils import money, pct
from ui.components import (
    feature_tiles,
    insight_card,
    kpi_grid,
    panel_title,
    pbi_cards,
    pill,
    section,
    show_chart,
    show_table,
)


def _unavailable(ctx: AnalysisContext, agent: str) -> bool:
    result = ctx.results.get(agent)
    if result and result.ok:
        return False
    st.info(f"This section needs the {result.title if result else agent}, which was "
            f"{result.status if result else 'not run'}: {result.message if result else ''}")
    return True


def _highlights(ctx: AnalysisContext) -> list[tuple[str, str, str, str]]:
    """Feature tiles whose numbers come from the actual run, so they are always truthful."""
    ok, n = sum(r.ok for r in ctx.results.values()), len(ctx.results)
    roles = ctx.schema.columns
    tiles = [("🧩", "10-agent blackboard pipeline",
              "Independent agents share one context, are individually timed, and a failure in one never stops the rest.",
              f"{ok}/{n} agents · {ctx.total_duration_ms / 1000:.1f}s")]
    tiles.append(("🔎", "Schema auto-detection",
                  "Business roles are matched to columns automatically, so no configuration or renaming is needed.",
                  f"revenue = {roles.get('revenue', 'n/a')} · {len(roles)} roles"))
    a = ctx.data("anomalies")
    if a:
        tiles.append(("🛡️", "Leakage-safe anomaly model",
                      "Pre-computed scores and fraud labels are excluded, and every flagged row explains its top drivers.",
                      f"{a['flagged']} flagged · {len(a['excluded_leakage_columns'])} columns excluded"))
    fc = ctx.data("forecasting")
    if fc:
        tiles.append(("📈", "Backtested forecasting",
                      "Five models compete on a rolling backtest; partial months are excluded and uncertainty is shown.",
                      f"{fc['model']} · {fc['backtest'][0]['mape_pct']:.1f}% MAPE"))
    c = ctx.data("customers")
    if c:
        risk = next((s for s in c["segments"] if s["segment"] == "At Risk"), None)
        tiles.append(("👥", "RFM customer segmentation",
                      "Customers are scored on recency, frequency and value, with Pareto concentration analysis.",
                      f"{c['concentration']['customers']} customers"
                      + (f" · {risk['customers']} at risk" if risk else "")))
    dq = ctx.data("data_quality")
    if dq:
        tiles.append(("✅", "Data quality scoring",
                      "Completeness, validity, uniqueness and consistency are scored, with business-rule checks.",
                      f"{dq['score']:.0f}/100 · {dq['status']}"))
    ins = ctx.data("insights")
    if ins:
        tiles.append(("💡", "Actionable insights",
                      "Findings are ranked by severity and pair each number with a suggested next step.",
                      f"{len(ins['insights'])} findings · {ins['counts'].get('warning', 0)} warnings"))
    tiles.append(("🧪", "Tested and reproducible",
                  "Unit tests, a real-data regression suite and a UI smoke test run in CI on Python 3.10-3.12.",
                  "pytest · ruff · Docker"))
    return tiles


def overview(ctx: AnalysisContext) -> None:
    sym, schema, df = ctx.schema.symbol, ctx.schema, ctx.df
    if not schema.has("revenue"):
        st.info("An overview needs a revenue column; none was detected in this dataset.")
        return

    summary = ctx.data("summary")
    if summary:
        tag = "written by an LLM" if summary["source"] == "llm" else "rule-based summary"
        st.markdown(f'<div class="summary">{summary["text"]}<br><small>Executive summary · {tag}</small></div>',
                    unsafe_allow_html=True)

    # ── Slicers ────────────────────────────────────────────────────────────────
    options = slicer_options(df, schema)
    months = sorted(df["_month"].dropna().unique()) if "_month" in df.columns else []
    picked: dict[str, tuple] = {}
    with st.container(border=True):
        st.markdown('<div class="panel-title">🎚️ Slicers</div><div class="panel-sub">Filter every visual below '
                    '(like a Power BI slicer pane). Leave empty to include everything.</div>', unsafe_allow_html=True)
        cols = st.columns(len(options) + (1 if len(months) >= 2 else 0) or 1)
        for col, (role, values) in zip(cols, options.items(), strict=False):
            with col:
                st.markdown(f'<div class="slicer-label">{role.replace("_", " ")}</div>', unsafe_allow_html=True)
                picked[role] = tuple(st.multiselect(role, values, key=f"sl_{role}", label_visibility="collapsed",
                                                    placeholder="All"))
        month_from = month_to = None
        if len(months) >= 2:
            with cols[-1]:
                st.markdown('<div class="slicer-label">period</div>', unsafe_allow_html=True)
                month_from, month_to = st.select_slider("period", months, value=(months[0], months[-1]), key="sl_period",
                                                        label_visibility="collapsed")
    flt = Filters(month_from=month_from, month_to=month_to, **picked)
    view = apply_filters(df, schema, flt)
    if view.empty:
        st.warning("No rows match the selected slicers. Clear a filter to continue.")
        return
    st.markdown(f'<div class="report-bar"><span>📄 <b>Sales report</b> · page 1 of 1</span>'
                f'<span>Showing <b>{len(view):,}</b> of {len(df):,} order lines</span></div>', unsafe_allow_html=True)

    # ── KPI cards ──────────────────────────────────────────────────────────────
    last_day = df[schema.get("date")].max() if schema.has("date") else None
    monthly = monthly_frame(view, schema, last_day)
    t = totals(view, schema)
    spec = [("Revenue", "revenue", money(t["revenue"], sym), "#6366F1", False),
            ("Profit", "profit", money(t.get("profit"), sym) if "profit" in t else None, "#34D399", False),
            ("Margin", "margin_pct", pct(t.get("margin_pct")) if "margin_pct" in t else None, "#F59E0B", True),
            ("Orders", "orders", f"{t['orders']:,}", "#22D3EE", False),
            ("Avg order value", "aov", money(t["aov"], sym), "#A78BFA", False),
            ("Customers", "customers", f"{t['customers']:,}" if "customers" in t else None, "#F472B6", False)]
    pbi_cards([{"label": label, "value": value, "color": color, "spark": sparkline_values(monthly, metric),
                "delta": month_over_month(monthly, metric, points=is_ratio), "unit": " pts" if is_ratio else "%"}
               for label, metric, value, color, is_ratio in spec if value is not None])

    # ── Visual grid ────────────────────────────────────────────────────────────
    left, right = st.columns([2, 1])
    with left, st.container(border=True):
        panel_title("Revenue, profit and margin by month", "Faded bar = incomplete month")
        if len(monthly):
            show_chart(viz.combo_chart(monthly, sym), "ov_combo")
    with right, st.container(border=True):
        dim = "channel" if schema.has("channel") else "region"
        g = group_revenue(view, schema, dim)
        panel_title(f"Revenue by {dim}", "Share of filtered revenue")
        if len(g):
            show_chart(viz.donut(g["name"], g["revenue"], sym, height=340), "ov_donut")

    c1, c2, c3 = st.columns(3)
    with c1, st.container(border=True):
        g = group_revenue(view, schema, "category")
        panel_title("Revenue by category", "Label shows revenue · margin; brighter = higher margin")
        if len(g):
            show_chart(viz.rank_bar(g["name"], g["revenue"], sym, height=300,
                                    margins=g["margin_pct"] if "margin_pct" in g else None), "ov_cat")
    with c2, st.container(border=True):
        g = group_revenue(view, schema, "region")
        panel_title("Revenue by region")
        if len(g):
            show_chart(viz.rank_bar(g["name"], g["revenue"], sym, height=300), "ov_region")
    with c3, st.container(border=True):
        g = group_revenue(view, schema, "product", top=6)
        panel_title("Top products", "By revenue")
        if len(g):
            show_chart(viz.rank_bar(g["name"], g["revenue"], sym, height=300), "ov_products")

    m_col, f_col = st.columns([3, 2])
    with m_col, st.container(border=True):
        pivot = matrix(view, schema)
        panel_title("Revenue matrix: category × region", "Brighter = higher revenue")
        if not pivot.empty:
            show_chart(viz.heatmap(pivot, sym, height=max(260, 46 * len(pivot) + 70)), "ov_matrix")
    with f_col, st.container(border=True):
        panel_title("Key findings", "From the full dataset, ranked by severity")
        for item in ctx.data("insights").get("insights", [])[:3]:
            insight_card(item)

    # ── Project highlights ─────────────────────────────────────────────────────
    section("What makes this project different", "Every figure below is read live from this analysis run.")
    feature_tiles(_highlights(ctx))


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

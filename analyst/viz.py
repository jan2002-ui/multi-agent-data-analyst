"""Plotly figure factory shared by the Streamlit app and the HTML report."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

PALETTE = ["#6366F1", "#22D3EE", "#F59E0B", "#34D399", "#F472B6", "#A78BFA", "#FB7185"]
ACCENT, WARN, GOOD, BAD = "#6366F1", "#F59E0B", "#34D399", "#FB7185"


def _style(fig: go.Figure, title: str | None = None, height: int = 380, light: bool = False) -> go.Figure:
    text, grid = ("#334155", "rgba(15,23,42,.08)") if light else ("#CBD5E1", "rgba(148,163,184,.14)")
    fig.update_layout(
        template="plotly_white" if light else "plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=height,
        font=dict(family="Inter, system-ui, -apple-system, Segoe UI, sans-serif", color=text, size=13),
        title=dict(text=title, x=0, font=dict(size=16, color="#0F172A" if light else "#F1F5F9")) if title else None,
        margin=dict(l=8, r=8, t=56 if title else 16, b=8),
        legend=dict(orientation="h", y=1.12, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"),
        colorway=PALETTE, hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=grid, zeroline=False, linecolor=grid)
    fig.update_yaxes(gridcolor=grid, zeroline=False, linecolor=grid)
    return fig


def revenue_trend(monthly: list[dict], forecast: dict | None = None, sym: str = "", light: bool = False) -> go.Figure:
    df = pd.DataFrame(monthly)
    fig = go.Figure()
    colors = [ACCENT if c else "rgba(99,102,241,.35)" for c in df["complete"]]
    fig.add_bar(x=df["_month"], y=df["revenue"], marker_color=colors, name="Revenue",
                hovertemplate=f"{sym}%{{y:,.0f}}<extra>Revenue</extra>")
    if "profit" in df:
        fig.add_scatter(x=df["_month"], y=df["profit"], mode="lines+markers", name="Profit",
                        line=dict(color=GOOD, width=2.5), hovertemplate=f"{sym}%{{y:,.0f}}<extra>Profit</extra>")
    if forecast:
        f = pd.DataFrame(forecast["forecast"])
        x_band = list(f["month"]) + list(f["month"])[::-1]
        fig.add_scatter(x=x_band, y=list(f["upper"]) + list(f["lower"])[::-1], fill="toself",
                        fillcolor="rgba(245,158,11,.18)", line=dict(width=0), name="80% range", hoverinfo="skip")
        last = df[df["complete"]].iloc[-1]
        fig.add_scatter(x=[last["_month"]] + list(f["month"]), y=[last["revenue"]] + list(f["forecast"]),
                        mode="lines+markers", name="Forecast", line=dict(color=WARN, width=2.5, dash="dash"),
                        hovertemplate=f"{sym}%{{y:,.0f}}<extra>Forecast</extra>")
    fig.update_yaxes(tickprefix=sym, tickformat="~s")
    return _style(fig, "Monthly revenue, profit and forecast", 400, light)


def breakdown_bar(rows: list[dict], label: str, sym: str = "", light: bool = False, top: int = 12) -> go.Figure:
    df = pd.DataFrame(rows).head(top).iloc[::-1]
    has_margin = "margin_pct" in df
    fig = go.Figure(go.Bar(
        y=df["name"], x=df["revenue"], orientation="h",
        marker=dict(color=df["margin_pct"] if has_margin else ACCENT, colorscale="Tealgrn" if has_margin else None,
                    colorbar=dict(title="Margin %", thickness=10) if has_margin else None),
        text=[f"{sym}{v:,.0f}  ·  {s:.0f}%" for v, s in zip(df["revenue"], df["share_pct"])],
        textposition="auto", hovertemplate="%{y}<br>" + sym + "%{x:,.0f}<extra></extra>"))
    fig.update_xaxes(tickprefix=sym, tickformat="~s")
    fig.update_layout(hovermode="closest")
    return _style(fig, f"Revenue by {label.lower()} (colour = margin)" if has_margin else f"Revenue by {label.lower()}",
                  max(260, 34 * len(df) + 90), light)


def discount_chart(bands: list[dict], light: bool = False) -> go.Figure:
    df = pd.DataFrame(bands)
    fig = go.Figure()
    fig.add_bar(x=df["band"], y=df["margin_pct"], name="Margin %", marker_color=ACCENT,
                text=[f"{v:.1f}%" for v in df["margin_pct"]], textposition="outside")
    fig.add_scatter(x=df["band"], y=df["lines"], name="Order lines", yaxis="y2", mode="lines+markers",
                    line=dict(color=WARN, width=2.5))
    fig.update_layout(yaxis=dict(title="Margin %"), yaxis2=dict(title="Order lines", overlaying="y", side="right",
                                                              showgrid=False))
    return _style(fig, "Margin by discount level", 360, light)


def rfm_chart(segments: list[dict], light: bool = False) -> go.Figure:
    df = pd.DataFrame(segments)
    fig = go.Figure()
    fig.add_bar(x=df["segment"], y=df["customers"], name="Customers", marker_color=ACCENT)
    fig.add_scatter(x=df["segment"], y=df["revenue_share_pct"], name="Revenue share %", yaxis="y2",
                    mode="lines+markers", line=dict(color=WARN, width=2.5))
    fig.update_layout(yaxis=dict(title="Customers"),
                      yaxis2=dict(title="Revenue share %", overlaying="y", side="right", showgrid=False))
    return _style(fig, "RFM customer segments", 360, light)


def pareto_chart(points: list[dict], light: bool = False) -> go.Figure:
    df = pd.DataFrame(points)
    fig = go.Figure()
    fig.add_scatter(x=df["customer_pct"], y=df["revenue_pct"], mode="lines", fill="tozeroy", name="Cumulative revenue",
                    line=dict(color=ACCENT, width=3), fillcolor="rgba(99,102,241,.18)")
    fig.add_scatter(x=[0, 100], y=[0, 100], mode="lines", name="Perfect equality",
                    line=dict(color="rgba(148,163,184,.6)", dash="dot"))
    fig.update_xaxes(title="% of customers (largest first)", ticksuffix="%")
    fig.update_yaxes(title="% of revenue", ticksuffix="%")
    return _style(fig, "Revenue concentration (Pareto)", 360, light)


def anomaly_scatter(df: pd.DataFrame, flags: pd.Series, x: str, y: str, light: bool = False) -> go.Figure:
    normal, odd = df[~flags], df[flags]
    normal = normal.sample(min(len(normal), 3000), random_state=1)
    fig = go.Figure()
    fig.add_scatter(x=normal[x], y=normal[y], mode="markers", name="Normal",
                    marker=dict(color="rgba(99,102,241,.45)", size=5))
    fig.add_scatter(x=odd[x], y=odd[y], mode="markers", name="Flagged",
                    marker=dict(color=BAD, size=9, line=dict(color="white", width=1)))
    fig.update_xaxes(title=x.replace("_", " "))
    fig.update_yaxes(title=y.replace("_", " "))
    fig.update_layout(hovermode="closest")
    return _style(fig, "Isolation Forest: flagged order lines", 420, light)


def quality_gauge(score: float, light: bool = False) -> go.Figure:
    color = GOOD if score >= 85 else WARN if score >= 70 else BAD
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(suffix="/100", font=dict(size=40)),
        gauge=dict(axis=dict(range=[0, 100]), bar=dict(color=color, thickness=0.28), bgcolor="rgba(148,163,184,.15)",
                   borderwidth=0)))
    return _style(fig, None, 250, light)


def dimension_bars(dimensions: dict, light: bool = False) -> go.Figure:
    names, vals = list(dimensions), list(dimensions.values())
    fig = go.Figure(go.Bar(x=vals, y=[n.title() for n in names], orientation="h",
                           marker_color=[GOOD if v >= 95 else WARN if v >= 80 else BAD for v in vals],
                           text=[f"{v:.1f}" for v in vals], textposition="auto"))
    fig.update_xaxes(range=[0, 100])
    fig.update_layout(hovermode="closest")
    return _style(fig, "Quality dimensions", 250, light)


def backtest_chart(backtest: list[dict], light: bool = False) -> go.Figure:
    df = pd.DataFrame(backtest).iloc[::-1]
    colors = [GOOD if i == len(df) - 1 else "rgba(99,102,241,.55)" for i in range(len(df))]
    fig = go.Figure(go.Bar(y=df["model"], x=df["mape_pct"], orientation="h", marker_color=colors,
                           text=[f"{v:.1f}%" for v in df["mape_pct"]], textposition="auto"))
    fig.update_layout(hovermode="closest")
    return _style(fig, "Backtest error by model (MAPE, lower is better)", 300, light)

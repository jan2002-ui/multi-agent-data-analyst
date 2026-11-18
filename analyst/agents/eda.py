"""EDA Agent: KPIs, segment breakdowns, trend, discount and return analysis."""

from __future__ import annotations

import pandas as pd

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext
from analyst.utils import safe_div

DIMENSIONS = {"category": "Category", "region": "Region", "channel": "Sales channel",
              "segment": "Customer segment", "sub_category": "Sub-category"}


def _group(df: pd.DataFrame, by: str, rev: str, profit: str | None, order_col: str | None) -> list[dict]:
    agg = {"revenue": (rev, "sum"), "lines": (rev, "size")}
    if profit:
        agg["profit"] = (profit, "sum")
    if order_col:
        agg["orders"] = (order_col, "nunique")
    out = df.groupby(by, dropna=False).agg(**agg).reset_index().rename(columns={by: "name"})
    total = out["revenue"].sum()
    out["share_pct"] = (100 * out["revenue"] / total).round(2) if total else 0.0
    if profit:
        out["margin_pct"] = (100 * out["profit"] / out["revenue"].where(out["revenue"] != 0)).round(2)
    out["name"] = out["name"].astype(str)
    return out.sort_values("revenue", ascending=False).round(2).to_dict("records")


class EDAAgent(BaseAgent):
    name = "eda"
    title = "EDA Agent"
    description = "Computes KPIs and breakdowns by category, region, channel, segment, time and discount."
    requires = ("revenue",)

    def run(self, ctx: AnalysisContext) -> dict:
        df, s = ctx.df, ctx.schema
        rev, profit = s.get("revenue"), s.get("profit")
        order_col = s.get("order_id")

        revenue_total = float(df[rev].sum())
        orders = int(df[order_col].nunique()) if order_col else len(df)
        kpis = {
            "revenue": round(revenue_total, 2),
            "orders": orders,
            "order_lines": len(df),
            "aov": round(safe_div(revenue_total, orders), 2),
        }
        if profit:
            kpis["profit"] = round(float(df[profit].sum()), 2)
            kpis["margin_pct"] = round(100 * safe_div(kpis["profit"], revenue_total), 2)
            kpis["loss_making_lines"] = int((df[profit] < 0).sum())
            kpis["loss_amount"] = round(float(df.loc[df[profit] < 0, profit].sum()), 2)
        if s.has("quantity"):
            kpis["units"] = int(df[s.get("quantity")].sum())
        if s.has("customer_id"):
            kpis["customers"] = int(df[s.get("customer_id")].nunique())
        if s.has("gross_revenue", "discount_amount"):
            kpis["avg_discount_pct"] = round(
                100 * safe_div(df[s.get("discount_amount")].sum(), df[s.get("gross_revenue")].sum()), 2)
        if s.has("return_flag"):
            kpis["return_rate_pct"] = round(100 * float(df[s.get("return_flag")].mean()), 2)
        if s.has("date"):
            dates = df[s.get("date")].dropna()
            if not dates.empty:
                kpis["date_start"], kpis["date_end"] = dates.min().date().isoformat(), dates.max().date().isoformat()

        breakdowns = {}
        for role, label in DIMENSIONS.items():
            if s.has(role):
                breakdowns[role] = {"label": label, "rows": _group(df, s.get(role), rev, profit, order_col)}

        top_products = []
        if s.has("product"):
            top_products = _group(df, s.get("product"), rev, profit, order_col)[:ctx.config.top_n]

        monthly = []
        if "_month" in df.columns:
            agg = {"revenue": (rev, "sum"), "lines": (rev, "size")}
            if profit:
                agg["profit"] = (profit, "sum")
            if order_col:
                agg["orders"] = (order_col, "nunique")
            m = df.dropna(subset=["_month"]).groupby("_month").agg(**agg).reset_index()
            m["revenue_mom_pct"] = (m["revenue"].pct_change() * 100).round(2)
            last_day = df[s.get("date")].max()
            m["complete"] = True
            if len(m) and last_day < last_day.to_period("M").to_timestamp("M").normalize() - pd.Timedelta(days=2):
                m.loc[m.index[-1], "complete"] = False
            monthly = m.round(2).to_dict("records")

        discount_bands = []
        if s.has("discount_pct") and profit:
            d = df[[s.get("discount_pct"), rev, profit]].copy()
            d.columns = ["discount", "revenue", "profit"]
            d["band"] = d["discount"].round(0).astype(int).astype(str) + "%"
            if d["discount"].nunique() > 12:
                d["band"] = pd.qcut(d["discount"], 5, duplicates="drop").astype(str)
            g = d.groupby("band", sort=False).agg(lines=("revenue", "size"), revenue=("revenue", "sum"),
                                                  profit=("profit", "sum"), discount=("discount", "mean"))
            g["margin_pct"] = (100 * g["profit"] / g["revenue"]).round(2)
            discount_bands = g.sort_values("discount").reset_index().round(2).to_dict("records")

        returns = {}
        if s.has("return_flag"):
            returns["rate_pct"] = kpis["return_rate_pct"]
            returns["returned_lines"] = int(df[s.get("return_flag")].sum())
            if s.has("return_reason"):
                reasons = df[s.get("return_reason")].dropna().value_counts()
                returns["top_reasons"] = [{"reason": str(k), "count": int(v)} for k, v in reasons.head(6).items()]
            if s.has("category"):
                by_cat = df.groupby(s.get("category"))[s.get("return_flag")].mean().mul(100).round(2)
                returns["by_category"] = [{"name": str(k), "rate_pct": float(v)}
                                          for k, v in by_cat.sort_values(ascending=False).items()]

        leakage = []
        if "_leakage" in df.columns and df["_leakage"].notna().any():
            g = df[df["_leakage"].notna()].groupby("_leakage").agg(lines=(rev, "size"), revenue=(rev, "sum"))
            leakage = [{"type": str(k), "lines": int(r.lines), "revenue": round(float(r.revenue), 2),
                        "share_pct": round(100 * safe_div(r.revenue, revenue_total), 2)}
                       for k, r in g.sort_values("revenue", ascending=False).iterrows()]
        kpis["leakage_revenue"] = round(sum(x["revenue"] for x in leakage), 2)

        measures = [c for c in (rev, profit, s.get("quantity"), s.get("unit_price")) if c]
        numeric_summary = df[measures].describe().round(2).to_dict()

        return {"kpis": kpis, "breakdowns": breakdowns, "top_products": top_products,
                "monthly": monthly, "discount_bands": discount_bands, "returns": returns,
                "leakage": leakage, "numeric_summary": numeric_summary}

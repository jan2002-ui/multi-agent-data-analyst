"""Customer Agent: value ranking, RFM segmentation and revenue concentration."""

from __future__ import annotations

import numpy as np
import pandas as pd

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext

MIN_CUSTOMERS_FOR_RFM = 20
SEGMENT_ORDER = ["Champions", "Loyal", "Promising", "Needs Attention", "At Risk", "Lost"]


def score_quintile(series: pd.Series, ascending: bool = True) -> pd.Series:
    """1-5 score from percentile rank; tied customers receive identical scores."""
    pct_rank = series.rank(method="average", pct=True, ascending=ascending)
    return np.ceil(pct_rank * 5).clip(1, 5).astype(int)


def rfm_segment(r: int, f: int, m: int) -> str:
    fm = (f + m) / 2
    if r >= 4 and fm >= 4:
        return "Champions"
    if r >= 3 and fm >= 4:
        return "Loyal"
    if r >= 4:
        return "Promising"
    if r <= 2 and fm >= 3.5:
        return "At Risk"
    if r <= 2 and fm <= 2.5:
        return "Lost"
    return "Needs Attention"


class CustomerAgent(BaseAgent):
    name = "customers"
    title = "Customer Analytics Agent"
    description = "Ranks customers, segments them with RFM and measures revenue concentration."
    requires = ("revenue", "customer_id")

    def run(self, ctx: AnalysisContext) -> dict:
        df, s = ctx.df, ctx.schema
        cid, rev, profit = s.get("customer_id"), s.get("revenue"), s.get("profit")
        base = df.dropna(subset=[cid])

        agg = {"revenue": (rev, "sum"), "lines": (rev, "size")}
        if profit:
            agg["profit"] = (profit, "sum")
        if s.has("order_id"):
            agg["orders"] = (s.get("order_id"), "nunique")
        if s.has("date"):
            agg["first_order"] = (s.get("date"), "min")
            agg["last_order"] = (s.get("date"), "max")
        cust = base.groupby(cid).agg(**agg)
        if "orders" not in cust:
            cust["orders"] = cust["lines"]

        total = float(cust["revenue"].sum())
        cust["share_pct"] = 100 * cust["revenue"] / total if total else 0.0
        cust = cust.sort_values("revenue", ascending=False)
        n = len(cust)

        # ---- Concentration.
        cumulative = cust["revenue"].cumsum() / total if total else cust["revenue"] * 0
        top10pct = max(1, int(np.ceil(0.10 * n)))
        concentration = {
            "customers": n,
            "top_customer": str(cust.index[0]),
            "top_customer_share_pct": round(float(cust["share_pct"].iloc[0]), 2),
            "top_10_share_pct": round(float(cust["share_pct"].head(10).sum()), 2),
            "top_10pct_customers_share_pct": round(float(cust["share_pct"].head(top10pct).sum()), 2),
            "customers_for_80pct_revenue": int((cumulative < 0.8).sum() + 1),
            "repeat_customer_rate_pct": round(100 * float((cust["orders"] >= 2).mean()), 2),
            "avg_orders_per_customer": round(float(cust["orders"].mean()), 2),
            "avg_revenue_per_customer": round(float(cust["revenue"].mean()), 2),
        }

        # ---- RFM segmentation.
        segments, rfm_note = [], None
        if s.has("date") and n >= MIN_CUSTOMERS_FOR_RFM:
            snapshot = base[s.get("date")].max() + pd.Timedelta(days=1)
            cust["recency_days"] = (snapshot - cust["last_order"]).dt.days
            cust["R"] = score_quintile(cust["recency_days"], ascending=False)
            cust["F"] = score_quintile(cust["orders"])
            cust["M"] = score_quintile(cust["revenue"])
            cust["segment"] = [rfm_segment(r, f, m) for r, f, m in zip(cust["R"], cust["F"], cust["M"])]
            grouped = cust.groupby("segment").agg(customers=("revenue", "size"), revenue=("revenue", "sum"),
                                                  avg_recency_days=("recency_days", "mean"),
                                                  avg_orders=("orders", "mean"))
            grouped["revenue_share_pct"] = 100 * grouped["revenue"] / total
            segments = [{"segment": seg, **grouped.loc[seg].round(2).to_dict(),
                         "customers": int(grouped.loc[seg, "customers"])}
                        for seg in SEGMENT_ORDER if seg in grouped.index]
        else:
            rfm_note = f"RFM needs a date column and at least {MIN_CUSTOMERS_FOR_RFM} customers."

        ctx.artifacts["customers_df"] = cust.reset_index()

        top_cols = [c for c in ("revenue", "profit", "orders", "share_pct", "segment", "last_order") if c in cust]
        top = cust.head(ctx.config.top_n)[top_cols].reset_index().rename(columns={cid: "customer_id"})
        num_cols = top.select_dtypes("number").columns
        top[num_cols] = top[num_cols].round(2)
        return {
            "concentration": concentration,
            "segments": segments,
            "top_customers": top.to_dict("records"),
            "pareto": [{"customer_pct": round(100 * (i + 1) / n, 2), "revenue_pct": round(100 * float(v), 2)}
                       for i, v in enumerate(cumulative) if (i + 1) % max(1, n // 50) == 0 or i == n - 1],
            "rfm_note": rfm_note,
        }

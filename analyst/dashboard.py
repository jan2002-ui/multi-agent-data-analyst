"""Pure-pandas logic behind the Power BI-style overview: slicers, KPI cards and matrix.

Kept free of Streamlit so every number on the page can be unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from analyst.schema import Schema
from analyst.utils import safe_div

SLICER_ROLES = ("category", "region", "channel")


@dataclass(frozen=True)
class Filters:
    category: tuple[str, ...] = ()
    region: tuple[str, ...] = ()
    channel: tuple[str, ...] = ()
    month_from: str | None = None       # "YYYY-MM", inclusive
    month_to: str | None = None


def slicer_options(df: pd.DataFrame, schema: Schema) -> dict[str, list[str]]:
    return {role: sorted(df[schema.get(role)].dropna().astype(str).unique())
            for role in SLICER_ROLES if schema.has(role)}


def apply_filters(df: pd.DataFrame, schema: Schema, flt: Filters) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    for role in SLICER_ROLES:
        values = getattr(flt, role)
        if values and schema.has(role):
            mask &= df[schema.get(role)].astype(str).isin(values)
    if "_month" in df.columns:
        if flt.month_from:
            mask &= df["_month"] >= flt.month_from
        if flt.month_to:
            mask &= df["_month"] <= flt.month_to
    return df[mask]


def totals(df: pd.DataFrame, schema: Schema) -> dict:
    rev = float(df[schema.get("revenue")].sum())
    orders = int(df[schema.get("order_id")].nunique()) if schema.has("order_id") else len(df)
    out = {"revenue": rev, "orders": orders, "aov": safe_div(rev, orders)}
    if schema.has("profit"):
        out["profit"] = float(df[schema.get("profit")].sum())
        out["margin_pct"] = 100 * safe_div(out["profit"], rev)
    if schema.has("customer_id"):
        out["customers"] = int(df[schema.get("customer_id")].nunique())
    return out


def monthly_frame(df: pd.DataFrame, schema: Schema, last_day: pd.Timestamp | None = None) -> pd.DataFrame:
    """Month-level metrics; ``complete`` is False for a trailing partial month."""
    if "_month" not in df.columns or df.empty:
        return pd.DataFrame()
    g = df.dropna(subset=["_month"]).groupby("_month")
    out = pd.DataFrame({"revenue": g[schema.get("revenue")].sum()})
    out["orders"] = g[schema.get("order_id")].nunique() if schema.has("order_id") else g.size()
    out["aov"] = out["revenue"] / out["orders"].where(out["orders"] > 0)
    if schema.has("profit"):
        out["profit"] = g[schema.get("profit")].sum()
        out["margin_pct"] = 100 * out["profit"] / out["revenue"].where(out["revenue"] != 0)
    if schema.has("customer_id"):
        out["customers"] = g[schema.get("customer_id")].nunique()
    out = out.reset_index().rename(columns={"_month": "month"})
    out["complete"] = True
    if last_day is not None and len(out):
        month_end = last_day.to_period("M").to_timestamp("M").normalize()
        if last_day < month_end - pd.Timedelta(days=2) and out["month"].iloc[-1] == str(last_day.to_period("M")):
            out.loc[out.index[-1], "complete"] = False
    return out


def month_over_month(monthly: pd.DataFrame, metric: str, points: bool = False) -> float | None:
    """Change of the last complete month vs the one before (percent, or points for ratios)."""
    if monthly.empty or metric not in monthly:
        return None
    values = monthly.loc[monthly["complete"], metric].dropna()
    if len(values) < 2:
        return None
    last, prev = float(values.iloc[-1]), float(values.iloc[-2])
    if points:
        return last - prev
    return 100 * safe_div(last - prev, abs(prev)) if prev else None


def sparkline_values(monthly: pd.DataFrame, metric: str, n: int = 12) -> list[float]:
    if monthly.empty or metric not in monthly:
        return []
    return [float(v) for v in monthly.loc[monthly["complete"], metric].dropna().tail(n)]


def matrix(df: pd.DataFrame, schema: Schema, rows: str = "category", cols: str = "region") -> pd.DataFrame:
    """Revenue pivot (Power BI 'matrix' visual)."""
    if not (schema.has(rows) and schema.has(cols)):
        return pd.DataFrame()
    pivot = df.pivot_table(index=schema.get(rows), columns=schema.get(cols), values=schema.get("revenue"),
                           aggfunc="sum", fill_value=0)
    return pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]


def group_revenue(df: pd.DataFrame, schema: Schema, role: str, top: int | None = None) -> pd.DataFrame:
    if not schema.has(role):
        return pd.DataFrame(columns=["name", "revenue", "margin_pct"])
    agg = {"revenue": (schema.get("revenue"), "sum")}
    if schema.has("profit"):
        agg["profit"] = (schema.get("profit"), "sum")
    g = df.groupby(schema.get(role)).agg(**agg).reset_index().rename(columns={schema.get(role): "name"})
    if "profit" in g:
        g["margin_pct"] = 100 * g["profit"] / g["revenue"].where(g["revenue"] != 0)
    g["name"] = g["name"].astype(str)
    g = g.sort_values("revenue", ascending=False)
    return g.head(top) if top else g

"""Data Understanding Agent: structure, column typing and date coverage."""

from __future__ import annotations

import pandas as pd

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext
from analyst.utils import is_text_series, to_datetime


def classify_column(name: str, series: pd.Series, n: int) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "binary" if series.dropna().nunique() <= 2 else "numeric"
    if not is_text_series(series):
        return "other"
    if "date" in name or name.endswith("_at"):
        if to_datetime(series.dropna().head(100)).notna().mean() >= 0.8:
            return "datetime"
    unique = series.nunique()
    if name.endswith("_id") or (n > 20 and unique / n > 0.9):
        return "identifier"
    return "categorical" if unique <= max(50, 0.05 * n) else "text"


class ProfilingAgent(BaseAgent):
    name = "profiling"
    title = "Data Understanding Agent"
    description = "Profiles shape, column types, cardinality and the date range."

    def run(self, ctx: AnalysisContext) -> dict:
        df, n = ctx.raw, len(ctx.raw)
        columns, type_counts = [], {}
        for col in df.columns:
            kind = classify_column(col, df[col], n)
            type_counts[kind] = type_counts.get(kind, 0) + 1
            sample = df[col].dropna()
            columns.append({
                "column": col, "type": kind, "dtype": str(df[col].dtype),
                "missing_pct": round(100 * float(df[col].isna().mean()), 2),
                "unique": int(df[col].nunique()),
                "example": str(sample.iloc[0]) if not sample.empty else "",
            })

        date_range = {}
        if ctx.schema.has("date"):
            dates = to_datetime(df[ctx.schema.get("date")]).dropna()
            if not dates.empty:
                date_range = {"start": dates.min().date().isoformat(), "end": dates.max().date().isoformat(),
                              "span_days": int((dates.max() - dates.min()).days) + 1,
                              "distinct_days": int(dates.dt.normalize().nunique())}

        return {
            "rows": n, "columns": df.shape[1],
            "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1024**2, 2),
            "type_counts": type_counts, "column_profile": columns,
            "date_range": date_range, "schema": ctx.schema.as_dict(),
            "detected_roles": len(ctx.schema.columns),
        }

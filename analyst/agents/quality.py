"""Data Quality Agent: dimension scores, business-rule validation and an issue log."""

from __future__ import annotations

import numpy as np
import pandas as pd

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext
from analyst.utils import is_text_series, to_datetime, to_numeric

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
WEIGHTS = {"completeness": 0.35, "validity": 0.30, "uniqueness": 0.20, "consistency": 0.15}


def _status(score: float) -> str:
    if score >= 95:
        return "Excellent"
    if score >= 85:
        return "Good"
    if score >= 70:
        return "Fair"
    return "Poor"


class DataQualityAgent(BaseAgent):
    name = "data_quality"
    title = "Data Quality Agent"
    description = ("Scores completeness, validity, uniqueness and consistency and checks "
                   "business rules such as profit = revenue - cost.")

    def run(self, ctx: AnalysisContext) -> dict:
        df, s = ctx.raw, ctx.schema
        n = len(df)
        issues: list[dict] = []

        def add(severity: str, check: str, message: str, count: int) -> None:
            issues.append({"severity": severity, "check": check, "message": message, "count": int(count)})

        # ---- Completeness: judged on the core business fields, not on optional/conditional ones.
        core_roles = ("order_id", "date", "customer_id", "revenue", "profit", "quantity")
        core = [s.get(r) for r in core_roles if s.has(r)]
        completeness = 1 - float((df[core] if core else df).isna().mean().mean())
        for col in core:
            missing = int(df[col].isna().sum())
            if missing:
                add("warning", "completeness", f"Core field '{col}' has {missing:,} missing values "
                    f"({missing / n:.1%}).", missing)

        missing_by_col = df.isna().sum()
        sparse = [c for c, m in missing_by_col.items() if m / n > 0.5]
        if sparse:
            add("info", "completeness",
                f"{len(sparse)} optional column(s) are mostly empty "
                f"({', '.join(sparse[:4])}{'...' if len(sparse) > 4 else ''}); "
                "this is normal for conditional fields such as return or coupon details.", len(sparse))

        # ---- Validity: row-level business rules.
        failing: list[np.ndarray] = []

        def rule(check: str, mask: pd.Series, message: str, severity: str = "critical") -> None:
            mask = mask.fillna(False)
            count = int(mask.sum())
            if count:
                add(severity, check, message.format(count=count), count)
                failing.append(mask.to_numpy())

        if s.has("quantity"):
            rule("quantity", to_numeric(df[s.get("quantity")]) <= 0, "{count:,} rows have quantity <= 0.")
        if s.has("revenue"):
            rule("revenue", to_numeric(df[s.get("revenue")]) < 0, "{count:,} rows have negative revenue.")
        if s.has("unit_price"):
            rule("unit_price", to_numeric(df[s.get("unit_price")]) <= 0, "{count:,} rows have price <= 0.")

        parsed: dict[str, pd.Series] = {}
        for role in ("date", "ship_date", "delivery_date"):
            if s.has(role):
                col = s.get(role)
                parsed[role] = to_datetime(df[col])
                rule(f"{role}_format", df[col].notna() & parsed[role].isna(),
                     f"{{count:,}} values in '{col}' are not valid dates.")
        if "date" in parsed and "ship_date" in parsed:
            rule("ship_before_order", parsed["ship_date"] < parsed["date"],
                 "{count:,} orders ship before they were placed.")
        if "ship_date" in parsed and "delivery_date" in parsed:
            rule("delivery_before_ship", parsed["delivery_date"] < parsed["ship_date"],
                 "{count:,} orders are delivered before they shipped.")
        if s.has("revenue", "cost", "profit"):
            gap = (to_numeric(df[s.get("revenue")]) - to_numeric(df[s.get("cost")])
                   - to_numeric(df[s.get("profit")])).abs()
            rule("profit_arithmetic", gap > 0.05, "{count:,} rows where profit != revenue - cost.", "warning")
        if s.has("gross_revenue", "discount_amount", "revenue"):
            gap = (to_numeric(df[s.get("gross_revenue")]) - to_numeric(df[s.get("discount_amount")])
                   - to_numeric(df[s.get("revenue")])).abs()
            rule("net_arithmetic", gap > 0.05, "{count:,} rows where net != gross - discount.", "warning")

        validity = 1 - (float(np.logical_or.reduce(failing).mean()) if failing else 0.0)

        # ---- Uniqueness.
        duplicate_rows = int(df.duplicated().sum())
        duplicate_ids = int(df[s.get("line_id")].duplicated().sum()) if s.has("line_id") else 0
        if duplicate_rows:
            add("warning", "uniqueness", f"{duplicate_rows:,} exact duplicate rows.", duplicate_rows)
        if duplicate_ids:
            add("critical", "uniqueness", f"{duplicate_ids:,} duplicate line identifiers.", duplicate_ids)
        uniqueness = 1 - min(1.0, (duplicate_rows + duplicate_ids) / n)

        # ---- Consistency: case / whitespace variants of the same label.
        checked, inconsistent = 0, []
        for col in df.columns:
            series = df[col]
            if not is_text_series(series) or series.nunique() > 200 or col.endswith("_id"):
                continue
            checked += 1
            text = series.dropna().astype(str)
            if text.str.strip().str.lower().nunique() < text.nunique():
                inconsistent.append(col)
        if inconsistent:
            add("warning", "consistency",
                f"Inconsistent spelling/casing in: {', '.join(inconsistent[:5])}.", len(inconsistent))
        consistency = 1 - len(inconsistent) / max(1, checked)

        # ---- Flags supplied by the source system.
        source_flags: dict[str, int] = {}
        if s.has("source_quality_flag"):
            flags = df[s.get("source_quality_flag")].astype(str)
            source_flags = {k: int(v) for k, v in flags[flags.str.upper() != "OK"].value_counts().items()}
            if source_flags:
                add("info", "source_flags", "Source system flagged rows: "
                    + ", ".join(f"{k} ({v:,})" for k, v in source_flags.items()) + ".",
                    sum(source_flags.values()))

        dims = {"completeness": completeness, "validity": validity,
                "uniqueness": uniqueness, "consistency": consistency}
        score = round(100 * sum(WEIGHTS[k] * v for k, v in dims.items()), 1)
        issues.sort(key=lambda i: (SEVERITY_ORDER[i["severity"]], -i["count"]))
        if not issues:
            add("info", "summary", "No data quality issues detected.", 0)

        missing_table = [
            {"column": c, "missing": int(m), "missing_pct": round(100 * m / n, 2), "core": c in core}
            for c, m in missing_by_col.sort_values(ascending=False).items() if m > 0
        ][:15]

        return {
            "score": score,
            "status": _status(score),
            "dimensions": {k: round(100 * v, 1) for k, v in dims.items()},
            "weights": WEIGHTS,
            "rows": n,
            "columns": df.shape[1],
            "missing_cells": int(missing_by_col.sum()),
            "duplicate_rows": duplicate_rows,
            "issues": issues,
            "missing_by_column": missing_table,
            "source_flags": source_flags,
        }

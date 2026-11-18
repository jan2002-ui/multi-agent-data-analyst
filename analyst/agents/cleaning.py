"""Data Cleaning Agent: conservative, fully logged transformations.

Unlike the original (which filled *every* column - e.g. inventing a ``return_reason`` for
orders that were never returned), this agent only repairs what can be repaired safely and
leaves conditional fields untouched.
"""

from __future__ import annotations

import pandas as pd

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext
from analyst.utils import is_text_series, to_datetime, to_numeric

CANCELLED = {"cancelled", "canceled"}
LEAKAGE_STATUS = {"refunded": "Refunded", "voided": "Voided", "failed": "Failed payment",
                  "partially refunded": "Partially refunded"}


class CleaningAgent(BaseAgent):
    name = "cleaning"
    title = "Data Cleaning Agent"
    description = "Standardises types and text, removes duplicates and imputes core measures safely."

    def run(self, ctx: AnalysisContext) -> dict:
        df, s, cfg = ctx.raw.copy(), ctx.schema, ctx.config
        log: list[dict] = []
        original_rows = len(df)

        def note(action: str, detail: str, count: int = 0) -> None:
            log.append({"action": action, "detail": detail, "count": int(count)})

        # 1. Trim stray whitespace in text columns.
        trimmed = 0
        for col in df.columns:
            series = df[col]
            if not is_text_series(series) or isinstance(series.dtype, pd.CategoricalDtype):
                continue
            if series.dropna().head(500).map(lambda v: not isinstance(v, str)).any():
                continue  # mixed-type column: leave untouched
            stripped = series.str.strip()
            changed = int((stripped.notna() & (stripped != series)).sum())
            if changed:
                df[col] = stripped
                trimmed += changed
        if trimmed:
            note("trim_whitespace", "Removed leading/trailing whitespace in text values.", trimmed)

        # 2. Parse dates.
        date_cols = [s.get(r) for r in ("date", "ship_date", "delivery_date") if s.has(r)]
        unparseable = 0
        for col in date_cols:
            before_null = int(df[col].isna().sum())
            df[col] = to_datetime(df[col])
            unparseable += int(df[col].isna().sum()) - before_null
        if date_cols:
            note("parse_dates", f"Parsed {', '.join(date_cols)} as datetime "
                 f"({unparseable} unparseable values set to missing).", unparseable)

        # 3. Numeric coercion for core measures.
        numeric_cols = [s.get(r) for r in ("revenue", "gross_revenue", "profit", "cost", "quantity",
                                           "unit_price", "discount_amount", "discount_pct", "shipping")
                        if s.has(r)]
        for col in numeric_cols:
            if not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = to_numeric(df[col])
                note("coerce_numeric", f"Converted '{col}' to numeric.")

        # 4. Duplicates.
        duplicates = int(df.duplicated().sum())
        if duplicates:
            df = df.drop_duplicates().reset_index(drop=True)
            note("drop_duplicates", "Removed exact duplicate rows.", duplicates)

        # 5. Impute only sparse core measures; never conditional/optional columns.
        for col in numeric_cols:
            missing = int(df[col].isna().sum())
            if not missing:
                continue
            if missing / len(df) <= cfg.impute_threshold and df[col].notna().any():
                df[col] = df[col].fillna(df[col].median())
                note("impute_median", f"Filled '{col}' with its median.", missing)
            else:
                note("left_missing", f"'{col}' has too many gaps to impute safely; left as-is.", missing)

        # 6. Derived helper columns (prefixed so they never collide with source columns).
        if s.has("date"):
            df["_month"] = df[s.get("date")].dt.to_period("M").astype(str).where(df[s.get("date")].notna())
        df["_leakage"] = None
        if s.has("status"):
            status = df[s.get("status")].astype(str).str.lower()
            df.loc[status.isin(CANCELLED), "_leakage"] = "Cancelled"
        if s.has("payment_status"):
            pay = df[s.get("payment_status")].astype(str).str.lower()
            for key, label in LEAKAGE_STATUS.items():
                df.loc[(pay == key) & df["_leakage"].isna(), "_leakage"] = label
        if s.has("profit"):
            df["_is_loss"] = df[s.get("profit")] < 0

        ctx.clean = df
        remaining = int(df.isna().sum().sum())
        return {
            "original_rows": original_rows, "cleaned_rows": len(df),
            "rows_removed": original_rows - len(df), "duplicates_removed": duplicates,
            "remaining_missing_cells": remaining, "actions": log,
            "note": "Optional/conditional columns (e.g. return_reason) are intentionally not imputed.",
        }

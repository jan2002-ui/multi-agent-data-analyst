"""Semantic schema detection.

The original project hard-coded a column called ``sales``. Real datasets rarely use
exactly that name (the bundled one has ``net_sales`` / ``gross_sales``), so every agent
asks the schema for a *role* ("revenue", "profit", "customer_id" ...) instead of a name.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import pandas as pd

from analyst.utils import to_datetime, to_numeric

# Order matters: earlier roles claim columns first, and a column is used for one role only.
ROLE_CANDIDATES: dict[str, list[str]] = {
    "revenue": ["net_sales", "net_revenue", "sales", "sales_amount", "total_sales", "revenue",
                "line_total", "amount", "gross_sales"],
    "gross_revenue": ["gross_sales", "gross_revenue"],
    "profit": ["profit", "net_profit", "gross_profit"],
    "cost": ["total_cost", "cost", "cogs"],
    "quantity": ["quantity", "qty", "units", "units_sold"],
    "unit_price": ["unit_price", "price"],
    "discount_amount": ["discount_amount"],
    "discount_pct": ["discount_percent", "discount_pct", "discount"],
    "shipping": ["shipping_cost", "freight"],
    "date": ["order_date", "date", "transaction_date", "sales_date", "invoice_date"],
    "ship_date": ["ship_date", "shipped_date"],
    "delivery_date": ["delivery_date", "delivered_date"],
    "order_id": ["order_id", "invoice_id", "transaction_id"],
    "line_id": ["order_line_id", "line_id"],
    "customer_id": ["customer_id", "cust_id", "client_id"],
    "product": ["product_name", "product", "item", "sku"],
    "category": ["category", "product_category", "product_type"],
    "sub_category": ["sub_category", "subcategory"],
    "region": ["region", "territory"],
    "channel": ["sales_channel", "channel"],
    "segment": ["customer_segment", "segment"],
    "status": ["order_status", "status"],
    "payment_status": ["payment_status"],
    "return_flag": ["return_flag", "returned", "is_returned"],
    "return_reason": ["return_reason"],
    "currency": ["currency"],
    "source_quality_flag": ["data_quality_flag"],
    "source_anomaly_flag": ["anomaly_flag"],
    "source_fraud_flag": ["fraud_flag"],
}

NUMERIC_ROLES = {"revenue", "gross_revenue", "profit", "cost", "quantity", "unit_price",
                 "discount_amount", "discount_pct", "shipping", "return_flag"}
DATE_ROLES = {"date", "ship_date", "delivery_date"}

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "CAD": "CA$", "AUD": "A$", "JPY": "¥"}

# Column-name fragments that indicate pre-computed model output; using them as features
# for a new anomaly model would be target leakage.
LEAKAGE_FRAGMENTS = ("anomaly", "fraud", "predicted", "forecast", "score", "flag", "risk")


@dataclass(frozen=True)
class Schema:
    columns: dict[str, str] = field(default_factory=dict)
    currency: str | None = None

    def get(self, role: str) -> str | None:
        return self.columns.get(role)

    def has(self, *roles: str) -> bool:
        return all(role in self.columns for role in roles)

    @property
    def symbol(self) -> str:
        if not self.currency:
            return ""
        return CURRENCY_SYMBOLS.get(self.currency.upper(), f"{self.currency} ")

    @property
    def revenue_label(self) -> str:
        return (self.get("revenue") or "revenue").replace("_", " ")

    def as_dict(self) -> dict:
        return {"roles": dict(self.columns), "currency": self.currency}


def _looks_numeric(series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series):
        return True
    sample = series.dropna().head(200)
    return not sample.empty and to_numeric(sample).notna().mean() >= 0.8


def _looks_date(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().head(200)
    if sample.empty or pd.api.types.is_numeric_dtype(sample):
        return False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return to_datetime(sample).notna().mean() >= 0.8


def detect_schema(df: pd.DataFrame) -> Schema:
    """Map business roles to the best matching columns in ``df``."""
    taken: set[str] = set()
    mapping: dict[str, str] = {}

    for role, candidates in ROLE_CANDIDATES.items():
        for candidate in candidates:
            if candidate not in df.columns or candidate in taken:
                continue
            series = df[candidate]
            if role in NUMERIC_ROLES and not _looks_numeric(series):
                continue
            if role in DATE_ROLES and not _looks_date(series):
                continue
            mapping[role] = candidate
            taken.add(candidate)
            break

    currency = None
    if "currency" in mapping:
        mode = df[mapping["currency"]].dropna().astype(str).mode()
        currency = mode.iloc[0] if not mode.empty else None

    return Schema(columns=mapping, currency=currency)


def feature_columns(df: pd.DataFrame, schema: Schema) -> tuple[list[str], list[str]]:
    """Columns suited to an anomaly model, plus the leakage columns that were excluded."""
    roles = ("revenue", "profit", "quantity", "unit_price", "discount_pct", "shipping", "cost")
    features = [schema.get(r) for r in roles if schema.has(r)]

    leaked = [
        c for c in df.select_dtypes("number").columns
        if any(frag in c for frag in LEAKAGE_FRAGMENTS)
    ]
    if len(features) < 2:  # unknown dataset: fall back to every sensible numeric column
        features = [
            c for c in df.select_dtypes("number").columns
            if c not in leaked and not c.startswith("_") and df[c].nunique() > 2
            and not c.endswith("_id")
        ]
    return features, leaked

"""Small, dependency-free helpers shared across agents."""

from __future__ import annotations

import math
from datetime import date, datetime

import numpy as np
import pandas as pd


def to_native(obj):
    """Recursively convert numpy / pandas objects into JSON-safe Python values."""
    if obj is None or obj is pd.NaT or obj is pd.NA:
        return None
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_native(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return to_native(obj.to_dict("records"))
    if isinstance(obj, pd.Series):
        return to_native(obj.to_dict())
    if isinstance(obj, np.ndarray):
        return to_native(obj.tolist())
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(obj, pd.Period):
        return str(obj)
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()
    return obj


def safe_div(numerator, denominator, default: float = 0.0) -> float:
    """Division that never raises and never returns NaN/inf."""
    try:
        if denominator in (0, None) or pd.isna(denominator) or pd.isna(numerator):
            return default
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def is_text_series(series: pd.Series) -> bool:
    """True for string-like columns under both pandas 2.x (object) and 3.x (str)."""
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return False
    if pd.api.types.is_datetime64_any_dtype(series):
        return False
    return (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
        or isinstance(series.dtype, pd.CategoricalDtype)
    )


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def to_datetime(series: pd.Series) -> pd.Series:
    """Tolerant datetime parsing that works for ISO and mixed formats."""
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except (ValueError, TypeError):
        return pd.to_datetime(series, errors="coerce")


def money(value, symbol: str = "") -> str:
    """Compact currency formatting: 1234567 -> $1.23M."""
    if value is None or pd.isna(value):
        return "n/a"
    v = float(value)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}{symbol}{v / 1_000_000:,.2f}M"
    if v >= 1_000:
        return f"{sign}{symbol}{v / 1_000:,.1f}K"
    return f"{sign}{symbol}{v:,.2f}"


def pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.{digits}f}%"

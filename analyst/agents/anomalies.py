"""Anomaly Agent: transparent IQR screening plus an explainable Isolation Forest.

Improvements over the original:
* only business measures are modelled, so pre-computed ``anomaly_score`` / ``fraud_flag`` /
  ``predicted_*`` columns can no longer leak into the model;
* each flagged row carries the features that made it unusual (robust z-scores);
* results are compared with any flags already supplied by the source system;
* output is capped and excludes personal data such as customer names.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from analyst.agents.base import BaseAgent, SkipAgent
from analyst.context import AnalysisContext
from analyst.schema import feature_columns
from analyst.utils import safe_div

MIN_ROWS = 30


def iqr_bounds(values: pd.Series, k: float = 1.5) -> tuple[float, float, float, float]:
    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    iqr = q3 - q1
    return float(q1), float(q3), float(q1 - k * iqr), float(q3 + k * iqr)


def robust_z(values: pd.Series) -> pd.Series:
    """(x - median) / (1.4826 * MAD); falls back to std when MAD is zero."""
    median = values.median()
    mad = (values - median).abs().median() * 1.4826
    if not mad:
        mad = values.std(ddof=0) or 1.0
    return (values - median) / mad


class AnomalyAgent(BaseAgent):
    name = "anomalies"
    title = "Anomaly Detection Agent"
    description = "IQR outlier screening and an explainable Isolation Forest on business measures."
    requires = ("revenue",)

    def run(self, ctx: AnalysisContext) -> dict:
        df, s, cfg = ctx.df, ctx.schema, ctx.config
        if len(df) < MIN_ROWS:
            raise SkipAgent(f"At least {MIN_ROWS} rows are required for anomaly detection.")

        features, leaked = feature_columns(df, s)
        if len(features) < 2:
            raise SkipAgent("Fewer than two usable numeric measures were found.")

        # ---- Layer 1: univariate IQR screening.
        iqr = []
        for col in features:
            values = df[col].dropna()
            if values.nunique() < 4:
                continue
            q1, q3, low, high = iqr_bounds(values)
            outliers = values[(values < low) | (values > high)]
            iqr.append({"column": col, "q1": round(q1, 2), "q3": round(q3, 2),
                        "lower": round(low, 2), "upper": round(high, 2),
                        "outliers": int(len(outliers)), "outlier_pct": round(100 * len(outliers) / len(values), 2),
                        "max_value": round(float(values.max()), 2), "min_value": round(float(values.min()), 2)})

        # ---- Layer 2: multivariate Isolation Forest.
        x = df[features].replace([np.inf, -np.inf], np.nan)
        x = x.fillna(x.median()).fillna(0)
        model = IsolationForest(n_estimators=200, contamination=cfg.contamination,
                                random_state=cfg.random_state, n_jobs=1)
        flags = model.fit_predict(x) == -1
        scores = -model.score_samples(x)          # higher = more anomalous

        z = x.apply(robust_z)
        ids = [s.get(r) for r in ("order_id", "line_id", "customer_id", "product", "category") if s.has(r)]
        shown = [c for c in ids + features[:5] if c in df.columns]
        shown = list(dict.fromkeys(shown))

        order = np.argsort(-scores)
        order = [i for i in order if flags[i]][:cfg.top_n]
        records = []
        for i in order:
            row = {c: (None if pd.isna(df.iloc[i][c]) else df.iloc[i][c]) for c in shown}
            drivers = z.iloc[i].abs().sort_values(ascending=False).head(2).index
            row["score"] = round(float(scores[i]), 3)
            row["drivers"] = "; ".join(
                f"{d} {'high' if z.iloc[i][d] > 0 else 'low'} ({abs(z.iloc[i][d]):.1f}σ)" for d in drivers)
            records.append(row)

        # ---- Compare with flags already present in the source data.
        validation = {}
        for role, label in (("source_anomaly_flag", "anomaly_flag"), ("source_fraud_flag", "fraud_flag")):
            if s.has(role):
                truth = df[s.get(role)].fillna(0).astype(int).to_numpy() == 1
                if truth.any():
                    caught = int((truth & flags).sum())
                    validation[label] = {
                        "source_flagged": int(truth.sum()), "also_flagged_by_model": caught,
                        "recall_pct": round(100 * safe_div(caught, truth.sum()), 1),
                        "precision_pct": round(100 * safe_div(caught, flags.sum()), 1)}

        ctx.artifacts["anomaly_flags"] = pd.Series(flags, index=df.index)
        ctx.artifacts["anomaly_scores"] = pd.Series(scores, index=df.index)

        return {
            "algorithm": "Isolation Forest (200 trees)",
            "contamination": cfg.contamination,
            "features": features, "excluded_leakage_columns": leaked,
            "total_records": len(df), "flagged": int(flags.sum()),
            "flagged_pct": round(100 * float(flags.mean()), 2),
            "top_records": records, "iqr": iqr, "validation": validation,
            "revenue_in_flagged": round(float(df.loc[flags, s.get("revenue")].sum()), 2),
        }

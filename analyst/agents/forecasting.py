"""Forecasting Agent: backtested monthly revenue forecast with honest uncertainty.

Several simple models compete on a rolling-origin backtest; the winner produces the
forecast and its error defines an 80% prediction band. An incomplete final month is
excluded from training so it cannot drag the trend down.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analyst.agents.base import BaseAgent, SkipAgent
from analyst.context import AnalysisContext
from analyst.utils import safe_div

MIN_MONTHS = 9
Z80 = 1.2816


def _naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-1], h)


def _moving_avg(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-3:].mean(), h)


def _linear(y: np.ndarray, h: int) -> np.ndarray:
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    return intercept + slope * np.arange(len(y), len(y) + h)


def _seasonal_naive(y: np.ndarray, h: int) -> np.ndarray:
    if len(y) < 12:
        return _moving_avg(y, h)
    return np.array([y[len(y) - 12 + (i % 12)] for i in range(h)])


def _blend(y: np.ndarray, h: int) -> np.ndarray:
    """Average of trend and recent level: robust when either alone over-reacts."""
    return 0.5 * _linear(y, h) + 0.5 * _moving_avg(y, h)


MODELS = {"Naive (last month)": _naive, "3-month average": _moving_avg, "Linear trend": _linear,
          "Seasonal naive": _seasonal_naive, "Trend + level blend": _blend}


class ForecastingAgent(BaseAgent):
    name = "forecasting"
    title = "Forecasting Agent"
    description = "Backtests several models and forecasts monthly revenue with an 80% interval."
    requires = ("revenue", "date")

    def run(self, ctx: AnalysisContext) -> dict:
        cfg = ctx.config
        monthly = ctx.data("eda").get("monthly")
        if not monthly:
            raise SkipAgent("Monthly aggregation unavailable.")
        series = pd.DataFrame(monthly)
        excluded_partial = None
        if not series["complete"].iloc[-1]:
            excluded_partial = str(series["_month"].iloc[-1])
            series = series.iloc[:-1]
        if len(series) < MIN_MONTHS:
            raise SkipAgent(f"At least {MIN_MONTHS} complete months are required (found {len(series)}).")

        y = series["revenue"].to_numpy(dtype=float)
        folds = min(4, max(2, len(y) // 5))

        backtest = []
        residuals: dict[str, list[float]] = {}
        for name, fn in MODELS.items():
            errors, actuals = [], []
            for i in range(len(y) - folds, len(y)):
                pred = fn(y[:i], 1)[0]
                errors.append(y[i] - pred)
                actuals.append(y[i])
            residuals[name] = errors
            mae = float(np.mean(np.abs(errors)))
            backtest.append({"model": name, "mae": round(mae, 2),
                             "mape_pct": round(100 * safe_div(mae, np.mean(actuals)), 2)})
        backtest.sort(key=lambda r: r["mae"])
        best = backtest[0]["model"]
        sigma = float(np.std(residuals[best], ddof=1)) if folds > 1 else 0.0

        h = cfg.forecast_horizon
        skip = 1 if excluded_partial else 0       # forecast starts after the last *observed* month
        point = np.clip(MODELS[best](y, h + skip), 0, None)
        last_period = pd.Period(series["_month"].iloc[-1], freq="M")
        horizon = []
        for i in range(skip, h + skip):
            width = Z80 * sigma * np.sqrt(i + 1)
            horizon.append({"month": str(last_period + i + 1), "forecast": round(float(point[i]), 2),
                            "lower": round(float(max(0.0, point[i] - width)), 2),
                            "upper": round(float(point[i] + width), 2)})

        slope = float(np.polyfit(np.arange(len(y)), y, 1)[0])
        return {
            "model": best, "backtest": backtest, "backtest_months": folds,
            "history": series[["_month", "revenue"]].rename(columns={"_month": "month"}).to_dict("records"),
            "forecast": horizon, "excluded_partial_month": excluded_partial,
            "trend_per_month": round(slope, 2),
            "trend_pct_per_month": round(100 * safe_div(slope, y.mean()), 2),
            "forecast_total": round(float(sum(p["forecast"] for p in horizon)), 2),
            "disclaimer": ("Statistical baseline from a short history; it does not model promotions, "
                           "holidays or external events. Treat the band as indicative, not guaranteed."),
        }

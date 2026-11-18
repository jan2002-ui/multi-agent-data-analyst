from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
REAL_DATA = ROOT / "data" / "sample" / "sales_dataset.csv"
TINY_DATA = ROOT / "data" / "sample" / "sales_data.csv"


def make_sales(n_days: int = 450, seed: int = 7) -> pd.DataFrame:
    """Deterministic synthetic order lines with a known total and planted anomalies."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n_days)
    rows = []
    for i, d in enumerate(dates):
        for line in range(2):
            qty = int(rng.integers(1, 4))
            price = float(rng.choice([20.0, 35.0, 50.0]))
            cost = price * 0.6
            rows.append({
                "order_id": f"O{i:04d}", "order_line_id": f"L{i:04d}-{line}", "order_date": d.date().isoformat(),
                "customer_id": f"C{int(rng.integers(1, 60)):03d}", "product_name": f"P{line}",
                "category": "A" if line == 0 else "B", "region": "North" if i % 2 else "South",
                "quantity": qty, "unit_price": price, "gross_sales": qty * price, "discount_amount": 0.0,
                "net_sales": qty * price, "total_cost": qty * cost, "profit": qty * (price - cost),
                "order_status": "Delivered", "payment_status": "Paid", "currency": "USD",
                "return_flag": 0, "return_reason": None,
            })
    df = pd.DataFrame(rows)
    # planted anomaly: absurd quantity
    df.loc[10, ["quantity", "gross_sales", "net_sales", "total_cost", "profit"]] = [500, 25000, 25000, 15000, 10000]
    df.loc[20, ["order_status", "payment_status"]] = ["Cancelled", "Refunded"]
    df.loc[30, "return_flag"], df.loc[30, "return_reason"] = 1, "Damaged"
    return df


@pytest.fixture(scope="session")
def sales_df() -> pd.DataFrame:
    return make_sales()


@pytest.fixture(scope="session")
def analysed(sales_df):
    from analyst import run_analysis
    return run_analysis(sales_df, source_name="synthetic")

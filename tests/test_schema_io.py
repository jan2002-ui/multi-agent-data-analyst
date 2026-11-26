import io

import pandas as pd
import pytest

from analyst.io import DataLoadError, load_dataset, normalize_columns
from analyst.schema import detect_schema, feature_columns


def test_normalize_columns_handles_spaces_case_and_duplicates():
    assert normalize_columns(["Order ID", " Net-Sales ", "order_id", "", "Order ID"]) == [
        "order_id", "net_sales", "order_id_1", "column_3", "order_id_2"]


def test_load_from_bytes_latin1_fallback():
    raw = "name,amount\nCafé,5\n".encode("latin-1")
    df = load_dataset(raw)
    assert df.loc[0, "name"] == "Café"


def test_load_errors_are_explicit(tmp_path):
    with pytest.raises(DataLoadError):
        load_dataset(tmp_path / "missing.csv")
    with pytest.raises(DataLoadError):
        load_dataset(pd.DataFrame())
    with pytest.raises(DataLoadError):
        load_dataset(io.BytesIO(b""))


def test_schema_prefers_net_sales_over_gross_and_never_double_assigns(sales_df):
    schema = detect_schema(sales_df)
    assert schema.get("revenue") == "net_sales"
    assert schema.get("gross_revenue") == "gross_sales"
    assert len(set(schema.columns.values())) == len(schema.columns)
    assert schema.symbol == "$"


def test_schema_works_with_legacy_sales_column():
    df = pd.DataFrame({"order_date": ["2025-01-01"], "sales": [10], "customer_id": ["a"]})
    assert detect_schema(df).get("revenue") == "sales"


def test_feature_columns_exclude_model_output_leakage(sales_df):
    df = sales_df.assign(anomaly_score=0.1, fraud_flag=0, predicted_profit=1.0)
    features, leaked = feature_columns(df, detect_schema(df))
    assert "anomaly_score" in leaked and "fraud_flag" in leaked and "predicted_profit" in leaked
    assert not set(features) & set(leaked)

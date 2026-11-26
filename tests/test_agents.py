import numpy as np
import pandas as pd
import pytest

from analyst import AnalysisConfig, run_analysis
from analyst.agents.base import BaseAgent
from analyst.agents.customers import rfm_segment, score_quintile
from analyst.agents.forecasting import MODELS
from analyst.utils import money, to_native
from tests.conftest import make_sales


def test_all_agents_succeed_on_clean_data(analysed):
    assert all(r.status == "success" for r in analysed.results.values()), {
        k: (v.status, v.message) for k, v in analysed.results.items()}


def test_kpis_match_independent_computation(analysed, sales_df):
    k = analysed.data("eda")["kpis"]
    assert k["revenue"] == pytest.approx(sales_df["net_sales"].sum(), abs=0.01)
    assert k["profit"] == pytest.approx(sales_df["profit"].sum(), abs=0.01)
    assert k["orders"] == sales_df["order_id"].nunique()
    assert k["margin_pct"] == pytest.approx(100 * sales_df["profit"].sum() / sales_df["net_sales"].sum(), abs=0.01)


def test_quality_detects_planted_problems():
    df = make_sales(60)
    df.loc[3, "quantity"] = -1
    df.loc[4, "net_sales"] = -5
    df = pd.concat([df, df.head(2)], ignore_index=True)
    ctx = run_analysis(df)
    dq = ctx.data("data_quality")
    checks = {i["check"] for i in dq["issues"]}
    assert {"quantity", "revenue", "uniqueness"} <= checks
    assert dq["score"] < 100 and dq["duplicate_rows"] == 2


def test_cleaning_never_imputes_conditional_columns(analysed):
    reason = analysed.clean["return_reason"]
    assert reason.notna().sum() == 1            # only the single real return keeps a reason
    assert analysed.data("cleaning")["rows_removed"] == 0


def test_cleaning_removes_duplicates_and_imputes_small_gaps():
    df = make_sales(60)
    df.loc[5, "net_sales"] = np.nan
    ctx = run_analysis(pd.concat([df, df.head(3)], ignore_index=True))
    c = ctx.data("cleaning")
    assert c["duplicates_removed"] == 3
    assert ctx.clean["net_sales"].isna().sum() == 0
    assert any(a["action"] == "impute_median" for a in c["actions"])


def test_leakage_and_returns_are_reported(analysed):
    eda = analysed.data("eda")
    assert {x["type"] for x in eda["leakage"]} == {"Cancelled"}
    assert eda["returns"]["returned_lines"] == 1
    assert eda["returns"]["top_reasons"][0]["reason"] == "Damaged"


def test_isolation_forest_finds_planted_anomaly_and_explains_it(analysed):
    a = analysed.data("anomalies")
    assert "net_sales" in a["features"] and "return_flag" in a["excluded_leakage_columns"]
    top = a["top_records"][0]
    assert top["order_line_id"] == "L0005-0"          # the planted 500-unit line ranks first
    assert "quantity" in top["drivers"] or "net_sales" in top["drivers"]
    assert a["flagged"] >= 1 and analysed.artifacts["anomaly_flags"].sum() == a["flagged"]


def test_anomaly_output_contains_no_customer_names(analysed):
    assert "customer_name" not in analysed.data("anomalies")["top_records"][0]


def test_rfm_helpers():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert score_quintile(s).tolist() == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert score_quintile(s, ascending=False).iloc[0] == 5
    assert rfm_segment(5, 5, 5) == "Champions" and rfm_segment(1, 1, 1) == "Lost"
    assert rfm_segment(1, 5, 5) == "At Risk"


def test_customer_concentration_is_consistent(analysed):
    c = analysed.data("customers")
    conc = c["concentration"]
    assert conc["top_10_share_pct"] >= conc["top_customer_share_pct"]
    assert sum(s["customers"] for s in c["segments"]) == conc["customers"]
    assert c["pareto"][-1]["revenue_pct"] == pytest.approx(100, abs=0.01)


def test_forecast_backtests_and_starts_after_last_month(analysed):
    f = analysed.data("forecasting")
    assert f["backtest"][0]["mae"] <= f["backtest"][-1]["mae"]
    assert len(f["forecast"]) == 3
    for p in f["forecast"]:
        assert p["lower"] <= p["forecast"] <= p["upper"] and p["lower"] >= 0
    last_hist = pd.Period(f["history"][-1]["month"], freq="M")
    first_fc = pd.Period(f["forecast"][0]["month"], freq="M")
    assert first_fc == last_hist + 1 + (1 if f["excluded_partial_month"] else 0)


def test_forecast_models_return_requested_horizon():
    y = np.arange(1, 25, dtype=float)
    for fn in MODELS.values():
        assert len(fn(y, 4)) == 4


def test_forecast_skips_short_history():
    ctx = run_analysis(make_sales(40))
    assert ctx.results["forecasting"].status == "skipped"


def test_insights_cover_key_areas(analysed):
    areas = {i["area"] for i in analysed.data("insights")["insights"]}
    assert {"Overview", "Customers", "Forecast", "Data quality"} <= areas
    assert all(i["severity"] in {"critical", "warning", "opportunity", "positive", "info"}
               for i in analysed.data("insights")["insights"])


def test_summary_rule_based_by_default(analysed):
    s = analysed.data("summary")
    assert s["source"] == "rules" and "orders" in s["text"]


def test_llm_narration_uses_injected_client_and_survives_failure():
    from analyst.llm import narrate

    class Block:
        type, text = "text", " Revenue is healthy. "

    class Client:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                assert "customer" not in str(kw["messages"]).lower()
                return type("R", (), {"content": [Block]})

    assert narrate({"kpis": {"revenue": 1}}, "m", client=Client()) == "Revenue is healthy."

    class Broken:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                raise RuntimeError("boom")

    assert narrate({}, "m", client=Broken()) is None


def test_failing_agent_is_isolated():
    class Boom(BaseAgent):
        name, title = "boom", "Boom"

        def run(self, ctx):
            raise RuntimeError("kaput")

    from analyst.orchestrator import default_pipeline
    ctx = run_analysis(make_sales(40), agents=[Boom(), *default_pipeline()])
    assert ctx.results["boom"].status == "failed" and "kaput" in ctx.results["boom"].message
    assert ctx.results["eda"].status == "success"


def test_progress_callback_and_json_export(sales_df):
    seen = []
    ctx = run_analysis(sales_df, progress=lambda i, n, r: seen.append((i, n, r.agent)))
    assert seen[0][0] == 1 and seen[-1][0] == seen[-1][1] == 10
    import json
    assert json.loads(json.dumps(ctx.to_dict()))["pipeline"][0]["agent"] == "data_quality"


def test_reports_written_to_disk(sales_df, tmp_path):
    ctx = run_analysis(sales_df, AnalysisConfig(output_dir=tmp_path))
    files = ctx.data("report")["files"]
    assert (tmp_path / files["html"].split("/")[-1]).read_text().startswith("<!doctype html>")
    assert "Key findings" in ctx.artifacts["report_html"]


def test_config_validation():
    for bad in ({"contamination": 0}, {"top_n": 0}, {"forecast_horizon": 99}):
        with pytest.raises(ValueError):
            AnalysisConfig(**bad)


def test_utils():
    assert money(1234567, "$") == "$1.23M" and money(None) == "n/a" and money(-2500, "$") == "-$2.5K"
    assert to_native({"a": np.float64("nan"), "b": np.int64(3), "c": pd.Timestamp("2025-01-01")}) == {
        "a": None, "b": 3, "c": "2025-01-01T00:00:00"}

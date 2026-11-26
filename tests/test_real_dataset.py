"""Regression tests on the bundled 3,633-row dataset (values verified independently with pandas)."""

import pytest

from analyst import run_analysis
from tests.conftest import REAL_DATA, TINY_DATA

pytestmark = pytest.mark.skipif(not REAL_DATA.exists(), reason="sample dataset not present")


@pytest.fixture(scope="module")
def ctx():
    return run_analysis(REAL_DATA)


def test_schema_resolves_net_sales(ctx):
    assert ctx.schema.get("revenue") == "net_sales" and ctx.schema.symbol == "$"


def test_headline_numbers(ctx):
    k = ctx.data("eda")["kpis"]
    assert k["revenue"] == pytest.approx(708917.42, abs=0.01)
    assert k["profit"] == pytest.approx(265827.24, abs=0.01)
    assert k["orders"] == 1800 and k["customers"] == 380 and k["loss_making_lines"] == 7


def test_every_agent_runs(ctx):
    assert {r.status for r in ctx.results.values()} == {"success"}


def test_source_flags_not_used_as_features(ctx):
    a = ctx.data("anomalies")
    assert not {"anomaly_score", "fraud_flag", "predicted_profit"} & set(a["features"])
    assert "fraud_flag" in a["validation"]


def test_return_reason_not_fabricated(ctx):
    assert ctx.clean["return_reason"].notna().sum() == 260


def test_legacy_tiny_sample_still_works():
    c = run_analysis(TINY_DATA)
    assert c.results["eda"].status == "success" and c.results["forecasting"].status == "skipped"

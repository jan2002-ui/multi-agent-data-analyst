import pytest

from analyst.dashboard import (
    Filters,
    apply_filters,
    group_revenue,
    matrix,
    month_over_month,
    monthly_frame,
    slicer_options,
    sparkline_values,
    totals,
)


@pytest.fixture(scope="module")
def ctx(analysed):
    return analysed


def test_slicer_options_cover_dimensions(ctx):
    opts = slicer_options(ctx.df, ctx.schema)
    assert opts["category"] == ["A", "B"] and opts["region"] == ["North", "South"]


def test_filters_match_manual_pandas(ctx):
    f = Filters(category=("A",), region=("North",), month_from="2025-03", month_to="2025-08")
    out = apply_filters(ctx.df, ctx.schema, f)
    manual = ctx.df[(ctx.df["category"] == "A") & (ctx.df["region"] == "North")
                    & (ctx.df["_month"] >= "2025-03") & (ctx.df["_month"] <= "2025-08")]
    assert len(out) == len(manual) > 0
    assert totals(out, ctx.schema)["revenue"] == pytest.approx(manual["net_sales"].sum())


def test_empty_filter_returns_everything(ctx):
    assert len(apply_filters(ctx.df, ctx.schema, Filters())) == len(ctx.df)


def test_totals_match_eda_agent(ctx):
    t, k = totals(ctx.df, ctx.schema), ctx.data("eda")["kpis"]
    assert t["revenue"] == pytest.approx(k["revenue"], abs=0.01) and t["orders"] == k["orders"]
    assert t["margin_pct"] == pytest.approx(k["margin_pct"], abs=0.01)


def test_monthly_frame_partial_month_and_mom(ctx):
    last_day = ctx.df["order_date"].max()
    m = monthly_frame(ctx.df, ctx.schema, last_day)
    assert m["revenue"].sum() == pytest.approx(ctx.df["net_sales"].sum())
    assert not m["complete"].iloc[-1]          # data ends 26 Mar -> March is a partial month
    assert m["complete"].iloc[:-1].all()
    values = m.loc[m["complete"], "revenue"]
    expected = 100 * (values.iloc[-1] - values.iloc[-2]) / values.iloc[-2]
    assert month_over_month(m, "revenue") == pytest.approx(expected)
    assert month_over_month(m.head(1), "revenue") is None
    assert len(sparkline_values(m, "revenue", 6)) == 6


def test_matrix_and_group_revenue_add_up(ctx):
    pivot = matrix(ctx.df, ctx.schema)
    assert pivot.to_numpy().sum() == pytest.approx(ctx.df["net_sales"].sum())
    g = group_revenue(ctx.df, ctx.schema, "category")
    assert g["revenue"].sum() == pytest.approx(ctx.df["net_sales"].sum())
    assert group_revenue(ctx.df, ctx.schema, "channel", top=1).empty


def test_rank_bar_encodes_margin_without_colorbar(ctx):
    from analyst import viz
    g = group_revenue(ctx.df, ctx.schema, "category")
    fig = viz.rank_bar(g["name"], g["revenue"], "$", margins=g["margin_pct"])
    assert fig.data[0].marker.showscale is False and "%" in fig.data[0].text[0]

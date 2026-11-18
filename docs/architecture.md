# Architecture

The system follows a **blackboard architecture**: independent agents read a shared
`AnalysisContext`, publish their findings back to it, and never call each other directly.

```
CSV ─► load_dataset ─► detect_schema ─► AnalysisContext ─► [ agents run in order ] ─► reports / dashboard
                                         (raw, clean, schema,
                                          results, artifacts)
```

| # | Agent | Reads | Publishes |
|---|-------|-------|-----------|
| 1 | Data Quality | raw data | 0-100 score (completeness, validity, uniqueness, consistency), issue log |
| 2 | Data Understanding | raw data | column types, cardinality, date range |
| 3 | Data Cleaning | raw data | cleaned frame (`ctx.clean`), action log |
| 4 | EDA | clean | KPIs, breakdowns, monthly trend, discount/return/leakage analysis |
| 5 | Anomaly Detection | clean | IQR screening + explainable Isolation Forest, validation vs source flags |
| 6 | Customer Analytics | clean | RFM segments, concentration (Pareto), top customers |
| 7 | Forecasting | EDA | backtested monthly forecast with 80% interval |
| 8 | Business Insights | all of the above | ranked findings with evidence and next steps |
| 9 | Executive Summary | insights | summary text (rule-based; optional LLM polish) |
| 10 | Report | everything | JSON + standalone HTML report |

## Design decisions

* **Semantic schema, not column names.** `analyst/schema.py` maps *roles* (revenue, profit, customer_id…)
  to columns, so `net_sales`, `sales` or `revenue` all work. The original code hard-coded `sales`, which
  silently produced empty output on the bundled dataset.
* **Failure isolation.** `BaseAgent.execute` times each agent and converts exceptions into a `failed`
  result; missing prerequisites become `skipped`. One agent can never crash the pipeline.
* **No target leakage.** Columns such as `anomaly_score`, `fraud_flag`, `predicted_profit` are excluded
  from the anomaly model (see `schema.feature_columns`).
* **Conservative cleaning.** Only core numeric measures with ≤5% gaps are imputed. Conditional fields
  (e.g. `return_reason`) are never filled.
* **Honest forecasting.** Five models compete on a rolling-origin backtest; an incomplete final month is
  excluded; uncertainty is shown as a band derived from backtest error.
* **Privacy.** Reports contain aggregates and capped top-N rows without customer names. The optional LLM
  step receives only aggregate KPIs and finding headlines.

## Adding an agent

```python
from analyst.agents.base import BaseAgent

class MyAgent(BaseAgent):
    name, title = "my_agent", "My Agent"
    requires = ("revenue",)               # schema roles needed, else the agent is skipped

    def run(self, ctx):
        return {"total": float(ctx.df[ctx.schema.get("revenue")].sum())}

run_analysis("data.csv", agents=[*default_pipeline(), MyAgent()])
```

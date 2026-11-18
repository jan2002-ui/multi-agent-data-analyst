📊 Multi-Agent Data Analyst

A ten-agent analytics pipeline that turns a raw sales CSV into KPIs, explainable anomaly detection, customer segments, a backtested forecast and ranked business recommendations.
Dashboard overview

Why this project

Most "AI data analyst" demos stop at a few charts. This one is built the way a production analytics tool would be: it detects your columns automatically, refuses to fabricate data, explains why a record is anomalous, validates its own forecast with a backtest, and turns numbers into prioritised actions.

Features
Area	What it does
Schema auto-detection	Maps business roles (revenue, profit, customer, date…) to columns, so net_sales, sales or revenue all work with no configuration
Data quality	0–100 score across completeness, validity, uniqueness and consistency, plus business-rule checks (e.g. profit = revenue − cost)
Safe cleaning	Type fixes, de-duplication and median imputation only for sparse core measures; conditional fields such as return_reason are never invented
EDA	KPIs, breakdowns by category, region, channel and segment, monthly trend, discount impact, returns and revenue leakage
Anomaly detection	IQR screening plus Isolation Forest on business measures only (no target leakage); every flagged row shows its top drivers
Customer analytics	RFM segmentation (Champions → Lost), Pareto revenue concentration, at-risk high-value customers
Forecasting	Five models compete on a rolling-origin backtest; incomplete months are excluded; an 80% prediction band is shown
Business insights	Severity-ranked findings, each with evidence and a suggested next step
Reporting	Interactive dashboard, CLI, JSON export and a standalone HTML report
Optional LLM summary	Off by default; sends aggregated figures only, never row-level data

Run on the bundled dataset (3,633 order lines × 72 columns, about 1.5 seconds end to end):

$708.9K revenue at a 37.5% margin across 1,800 orders and 380 customers
Home & Kitchen generates 58% of revenue, a concentration risk
Electronics is 18% of revenue but earns only 25.8% margin against 37.5% overall
10.4% of booked revenue is hit by cancellations, refunds or failed payments
34 high-value customers are drifting away (last purchase about 261 days ago)
The last 3 complete months are 10.7% below the prior 3, while the long-run trend is up 1.0% per month
Architecture

The system follows a blackboard architecture. Independent agents read a shared context, publish their findings back to it, and never call each other. Each agent is timed, and a failure in one is isolated from the rest.

CSV
Loader + schema detection
Shared context
Data Quality
Profiling
Cleaning
EDA
Anomalies
Customers
Forecasting
Insights
Executive Summary
Report
Streamlit dashboard
CLI / HTML / JSON

Full design notes are in docs/architecture.md.

Quick start
bash
git clone https://github.com/jan2002-ui/multi-agent-data-analyst.git
cd multi-agent-data-analyst

python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
streamlit run app.py              # dashboard, auto-loads the sample dataset

Command line:

bash
python main.py data/sample/sales_dataset.csv     # writes JSON + HTML to reports/
python main.py my_data.csv --horizon 6 --contamination 0.03

Docker:

bash
docker build -t multi-agent-data-analyst .
docker run -p 8501:8501 multi-agent-data-analyst
Use it as a library
python
from analyst import run_analysis, AnalysisConfig

ctx = run_analysis("data/sample/sales_dataset.csv", AnalysisConfig(forecast_horizon=6))

ctx.data("eda")["kpis"]               # revenue, profit, margin, AOV ...
ctx.data("insights")["insights"]      # ranked findings with next steps
ctx.results["forecasting"].status     # success | skipped | failed
Add your own agent
python
from analyst.agents.base import BaseAgent
from analyst.orchestrator import default_pipeline, run_analysis

class TotalRevenueAgent(BaseAgent):
    name, title = "total_revenue", "Total Revenue Agent"
    requires = ("revenue",)           # skipped automatically if the column is missing

    def run(self, ctx):
        return {"total": float(ctx.df[ctx.schema.get("revenue")].sum())}

ctx = run_analysis("data.csv", agents=[*default_pipeline(), TotalRevenueAgent()])
Your own data

Upload any CSV in the dashboard sidebar. Columns are matched by name patterns, for example:

Role	Recognised names (examples)
Revenue	net_sales, sales, revenue, amount, gross_sales
Profit	profit, net_profit
Date	order_date, date, transaction_date
Customer	customer_id, client_id

Only revenue is required. Agents whose inputs are missing are skipped with a clear message rather than failing.

Project structure
analyst/              core package: schema, config, context, orchestrator, viz, reporting, CLI
analyst/agents/       quality · profiling · cleaning · eda · anomalies · customers
                      forecasting · insights · summary · report
ui/                   Streamlit styles, components and tabs
tests/                unit, real-data regression and UI smoke tests
data/sample/          sample datasets
docs/                 architecture notes, screenshots, example report
Testing and quality
bash
pip install -r requirements-dev.txt
python -m pytest -q        # 34 tests
ruff check .

The tests cover schema detection, planted data-quality problems, the no-imputation rule, anomaly detection with a planted outlier, customer concentration, forecast correctness, agent failure isolation, and a regression test on the real dataset whose headline numbers were verified independently with pandas. A Streamlit smoke test renders the full app. GitHub Actions runs lint and tests on Python 3.10, 3.11 and 3.12.

Optional LLM summary

Copy .env.example to .env, set ANTHROPIC_API_KEY, install pip install anthropic, and enable the toggle in the sidebar. Only aggregated KPIs and finding headlines are sent, never rows or customer identifiers. If the call fails, the app silently keeps the rule-based summary.

Limitations
Forecasts come from roughly 20 months of history and do not model promotions, holidays or external events.
Insights highlight patterns worth investigating; they do not prove causes.
The agents are deterministic analytical components, not autonomous LLM agents. The optional LLM only rewrites the summary.
Roadmap
[ ] Weekly forecasting granularity and holiday effects
[ ] Cohort retention analysis
[ ] Configurable column mapping in the UI
[ ] Scheduled runs with email delivery of the HTML report
License

MIT. See LICENSE.

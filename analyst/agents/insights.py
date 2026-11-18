"""Business Insights Agent: rule-based, evidence-linked findings ranked by severity.

Every insight cites the numbers it is based on and proposes a next step phrased as
something to *investigate* - the data shows correlation, not causation.
"""

from __future__ import annotations

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext
from analyst.utils import money, pct

SEVERITY_RANK = {"critical": 0, "warning": 1, "opportunity": 2, "positive": 3, "info": 4}


class InsightsAgent(BaseAgent):
    name = "insights"
    title = "Business Insights Agent"
    description = "Turns agent outputs into ranked, actionable findings with supporting numbers."

    def run(self, ctx: AnalysisContext) -> dict:
        sym = ctx.schema.symbol
        eda, cust = ctx.data("eda"), ctx.data("customers")
        fc, anom, dq = ctx.data("forecasting"), ctx.data("anomalies"), ctx.data("data_quality")
        kpis = eda.get("kpis", {})
        out: list[dict] = []

        def add(severity: str, area: str, title: str, detail: str, action: str = "") -> None:
            out.append({"severity": severity, "area": area, "title": title, "detail": detail, "action": action})

        if kpis:
            margin = f" at a {pct(kpis['margin_pct'])} margin" if "margin_pct" in kpis else ""
            add("info", "Overview", f"{money(kpis['revenue'], sym)} revenue{margin}",
                f"{kpis['orders']:,} orders, average order value {money(kpis['aov'], sym)}"
                + (f", {kpis['customers']:,} customers." if "customers" in kpis else "."))

        # ---- Category concentration and margin gaps.
        rows = eda.get("breakdowns", {}).get("category", {}).get("rows", [])
        if rows:
            top = rows[0]
            if top["share_pct"] >= 40:
                add("warning", "Sales", f"{top['name']} generates {pct(top['share_pct'], 0)} of revenue",
                    f"One category carries {money(top['revenue'], sym)}; weakness there would hit the whole business.",
                    "Test growth in the next-largest categories to reduce dependence.")
            avg = kpis.get("margin_pct")
            if avg is not None:
                for r in rows:
                    m = r.get("margin_pct")
                    if m is not None and r["share_pct"] >= 8 and m < avg - 8:
                        add("warning", "Profitability",
                            f"{r['name']}: {pct(r['share_pct'], 0)} of revenue but only {pct(m)} margin",
                            f"Overall margin is {pct(avg)}; this category sits {avg - m:.1f} pts lower.",
                            "Review supplier cost, pricing and discounting for this category.")
                best = max((r for r in rows if r.get("margin_pct") is not None and r["share_pct"] >= 3),
                           key=lambda r: r["margin_pct"], default=None)
                if best and best["margin_pct"] > avg + 5:
                    add("opportunity", "Profitability",
                        f"{best['name']} earns the best margin ({pct(best['margin_pct'])})",
                        f"It is only {pct(best['share_pct'], 0)} of revenue, so growth here is highly accretive.",
                        "Prioritise marketing and inventory depth for this category.")

        # ---- Loss-making lines.
        if kpis.get("loss_making_lines"):
            add("warning", "Profitability", f"{kpis['loss_making_lines']} order lines lose money",
                f"Combined loss {money(abs(kpis['loss_amount']), sym)}.",
                "Check whether deep discounts or shipping costs drive these negative margins.")

        # ---- Discount depth.
        bands = eda.get("discount_bands", [])
        if len(bands) >= 3:
            full, deep = bands[0], bands[-1]
            if deep["margin_pct"] < full["margin_pct"] - 5:
                add("warning", "Pricing",
                    f"Deep discounts ({deep['band']}) cut margin to {pct(deep['margin_pct'])}",
                    f"Full-price lines earn {pct(full['margin_pct'])}; the {deep['band']} band earns "
                    f"{pct(deep['margin_pct'])} across {deep['lines']:,} lines.",
                    "Cap discount depth or require minimum basket size.")

        # ---- Revenue leakage.
        leak = eda.get("leakage", [])
        if leak and kpis.get("revenue"):
            share = 100 * kpis["leakage_revenue"] / kpis["revenue"]
            if share >= 2:
                parts = ", ".join(f"{x['type'].lower()} {money(x['revenue'], sym)}" for x in leak[:3])
                add("critical" if share >= 15 else "warning", "Revenue leakage",
                    f"{pct(share)} of booked revenue is hit by cancellations, refunds or failed payments",
                    f"{money(kpis['leakage_revenue'], sym)} at risk ({parts}).",
                    "Investigate checkout failures and fulfilment causes behind cancellations.")

        # ---- Returns.
        ret = eda.get("returns", {})
        if ret.get("rate_pct") is not None and ret.get("returned_lines"):
            reason = ret.get("top_reasons", [{}])[0].get("reason")
            worst = (ret.get("by_category") or [{}])[0]
            add("warning" if ret["rate_pct"] >= 5 else "info", "Returns",
                f"Return rate is {pct(ret['rate_pct'])}",
                (f"Most common reason: {reason}. " if reason else "")
                + (f"Highest in {worst['name']} ({pct(worst['rate_pct'])})." if worst.get("name") else ""),
                "Target the top return reason with product-page or packaging fixes.")

        # ---- Customers.
        conc = cust.get("concentration", {})
        if conc:
            if conc["top_customer_share_pct"] >= 5:
                add("warning", "Customers",
                    f"{conc['top_customer']} alone is {pct(conc['top_customer_share_pct'])} of revenue",
                    f"The top 10 customers contribute {pct(conc['top_10_share_pct'])}.",
                    "Assign account management and monitor this relationship closely.")
            seg = {x["segment"]: x for x in cust.get("segments", [])}
            if "At Risk" in seg:
                a = seg["At Risk"]
                add("opportunity", "Customers", f"{a['customers']:,} high-value customers are drifting away",
                    f"They represent {pct(a['revenue_share_pct'])} of revenue and last bought "
                    f"{a['avg_recency_days']:.0f} days ago on average.",
                    "Launch a win-back campaign before they lapse completely.")
            add("info", "Customers", f"{pct(conc['repeat_customer_rate_pct'])} of customers ordered more than once",
                f"Average {conc['avg_orders_per_customer']:.1f} orders and "
                f"{money(conc['avg_revenue_per_customer'], sym)} revenue per customer.")

        # ---- Trend & forecast.
        if fc:
            direction = "rising" if fc["trend_pct_per_month"] > 0.5 else "falling" if fc["trend_pct_per_month"] < -0.5 else "flat"
            sev = "warning" if direction == "falling" else "positive" if direction == "rising" else "info"
            nxt = fc["forecast"][0]
            hist = [h["revenue"] for h in fc["history"]]
            if len(hist) >= 6:
                recent, prior = sum(hist[-3:]) / 3, sum(hist[-6:-3]) / 3
                change = 100 * (recent - prior) / prior if prior else 0
                if abs(change) >= 5:
                    add("warning" if change < 0 else "positive", "Momentum",
                        f"Last 3 complete months are {abs(change):.1f}% {'below' if change < 0 else 'above'} the prior 3",
                        f"Average monthly revenue moved from {money(prior, sym)} to {money(recent, sym)}.",
                        "Check whether seasonality, promotions or fewer orders explain the shift.")
            add(sev, "Forecast", f"Long-run revenue trend is {direction} ({fc['trend_pct_per_month']:+.1f}% per month)",
                f"Best backtested model: {fc['model']}. Next month ({nxt['month']}) is projected at "
                f"{money(nxt['forecast'], sym)} (80% range {money(nxt['lower'], sym)}-{money(nxt['upper'], sym)}).",
                "Use as a planning baseline, not a commitment.")

        # ---- Anomalies.
        if anom:
            top = (anom.get("top_records") or [{}])[0]
            add("info", "Anomalies", f"{anom['flagged']} unusual order lines flagged ({pct(anom['flagged_pct'])})",
                f"Together they hold {money(anom['revenue_in_flagged'], sym)} of revenue."
                + (f" Most unusual: {top.get('drivers')}." if top.get("drivers") else ""),
                "Review flagged lines for pricing errors, bulk orders or fraud.")

        # ---- Data quality.
        if dq:
            sev = "critical" if dq["score"] < 70 else "warning" if dq["score"] < 85 else "info"
            top_issue = next((i for i in dq["issues"] if i["severity"] != "info"), None)
            add(sev, "Data quality", f"Data quality score {dq['score']:.0f}/100 ({dq['status']})",
                top_issue["message"] if top_issue else "No blocking issues found.",
                "Fix upstream capture of the flagged fields." if top_issue else "")

        out.sort(key=lambda i: SEVERITY_RANK[i["severity"]])
        counts = {sev: sum(1 for i in out if i["severity"] == sev) for sev in SEVERITY_RANK}
        return {"insights": out, "counts": counts}

"""Executive Summary Agent: a deterministic summary, optionally polished by an LLM."""

from __future__ import annotations

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext
from analyst.llm import narrate
from analyst.utils import money, pct


class SummaryAgent(BaseAgent):
    name = "summary"
    title = "Executive Summary Agent"
    description = "Writes a short executive summary; uses an LLM only if explicitly enabled."

    def run(self, ctx: AnalysisContext) -> dict:
        sym = ctx.schema.symbol
        kpis = ctx.data("eda").get("kpis", {})
        insights = ctx.data("insights").get("insights", [])
        dq = ctx.data("data_quality")

        sentences = []
        if kpis:
            s = f"The dataset covers {kpis['orders']:,} orders worth {money(kpis['revenue'], sym)}"
            if "margin_pct" in kpis:
                s += f" with a {pct(kpis['margin_pct'])} profit margin"
            if "date_start" in kpis:
                s += f" between {kpis['date_start']} and {kpis['date_end']}"
            sentences.append(s + ".")
        flagged = [i for i in insights if i["severity"] in ("critical", "warning")]
        if flagged:
            sentences.append("Key risks: " + "; ".join(i["title"] for i in flagged[:3]) + ".")
        opportunities = [i for i in insights if i["severity"] in ("opportunity", "positive")]
        if opportunities:
            sentences.append("Opportunities: " + "; ".join(i["title"] for i in opportunities[:2]) + ".")
        if dq:
            sentences.append(f"Data quality is rated {dq['status'].lower()} ({dq['score']:.0f}/100).")
        text = " ".join(sentences) or "No summary could be produced from the available data."

        source = "rules"
        if ctx.config.use_llm:
            polished = narrate({"kpis": kpis, "headlines": [i["title"] for i in insights[:8]],
                                "data_quality_score": dq.get("score")}, ctx.config.llm_model)
            if polished:
                text, source = polished, "llm"
        return {"text": text, "source": source}

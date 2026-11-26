"""Report Agent: assembles JSON and a self-contained HTML executive report."""

from __future__ import annotations

import json
from datetime import timezone

from analyst.agents.base import BaseAgent
from analyst.context import AnalysisContext
from analyst.reporting import build_html


class ReportAgent(BaseAgent):
    name = "report"
    title = "Report Generation Agent"
    description = "Builds JSON and HTML reports; writes them to disk when an output directory is set."

    def run(self, ctx: AnalysisContext) -> dict:
        payload = json.dumps(ctx.to_dict(), indent=2)
        html = build_html(ctx)
        ctx.artifacts["report_json"] = payload
        ctx.artifacts["report_html"] = html

        files = {}
        if ctx.config.output_dir:
            out = ctx.config.output_dir
            out.mkdir(parents=True, exist_ok=True)
            stamp = ctx.generated_at.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
            json_path, html_path = out / f"analysis_{stamp}.json", out / f"analysis_{stamp}.html"
            json_path.write_text(payload, encoding="utf-8")
            html_path.write_text(html, encoding="utf-8")
            files = {"json": str(json_path), "html": str(html_path)}
        return {"json_kb": round(len(payload) / 1024, 1), "html_kb": round(len(html) / 1024, 1), "files": files}

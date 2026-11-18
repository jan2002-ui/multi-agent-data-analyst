"""Standalone HTML executive report (light theme, printable, no server needed)."""

from __future__ import annotations

from html import escape

import pandas as pd

from analyst import viz
from analyst.context import AnalysisContext
from analyst.utils import money, pct

CSS = """
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--accent:#6366f1;--bg:#f8fafc}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1080px;margin:0 auto;padding:40px 24px 64px}
header{background:linear-gradient(135deg,#312e81,#6366f1 60%,#22d3ee);color:#fff;border-radius:18px;padding:34px 38px;margin-bottom:28px}
header h1{margin:0 0 6px;font-size:28px}header p{margin:0;opacity:.85}
h2{margin:36px 0 12px;font-size:20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.kpi b{display:block;font-size:24px}.kpi span{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:12px;border-left:5px solid var(--accent)}
.card.critical{border-left-color:#e11d48}.card.warning{border-left-color:#f59e0b}.card.opportunity{border-left-color:#0ea5e9}.card.positive{border-left-color:#10b981}
.card h3{margin:0 0 4px;font-size:16px}.card p{margin:2px 0;color:#334155}.card .act{color:var(--accent);font-weight:600;font-size:13px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13.5px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}th{background:#f1f5f9;font-weight:600}
.summary{font-size:16px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px 22px}
footer{margin-top:44px;color:var(--muted);font-size:12.5px}
@media print{body{background:#fff}.wrap{padding:0}}
"""


def _table(rows, columns: dict[str, str], limit: int = 15) -> str:
    if not rows:
        return "<p>No data available.</p>"
    df = pd.DataFrame(rows).head(limit)
    df = df[[c for c in columns if c in df.columns]].rename(columns=columns)
    return df.to_html(index=False, border=0, na_rep="", float_format=lambda v: f"{v:,.2f}", escape=True)


def build_html(ctx: AnalysisContext) -> str:
    sym = ctx.schema.symbol
    eda, cust, fc = ctx.data("eda"), ctx.data("customers"), ctx.data("forecasting")
    kpis, dq = eda.get("kpis", {}), ctx.data("data_quality")
    insights, summary = ctx.data("insights").get("insights", []), ctx.data("summary")

    tiles = []
    if kpis:
        tiles = [("Revenue", money(kpis["revenue"], sym)), ("Orders", f"{kpis['orders']:,}"),
                 ("Avg order value", money(kpis["aov"], sym))]
        if "profit" in kpis:
            tiles += [("Profit", money(kpis["profit"], sym)), ("Margin", pct(kpis["margin_pct"]))]
        if "customers" in kpis:
            tiles.append(("Customers", f"{kpis['customers']:,}"))
    if dq:
        tiles.append(("Data quality", f"{dq['score']:.0f}/100"))

    first = True

    def embed(fig):
        nonlocal first
        html = fig.to_html(full_html=False, include_plotlyjs="cdn" if first else False,
                           config={"displayModeBar": False})
        first = False
        return html

    body = [f'<div class="summary">{escape(summary.get("text", ""))}</div>'] if summary else []
    body.append("<h2>Key findings</h2>")
    for i in insights:
        act = f'<p class="act">→ {escape(i["action"])}</p>' if i["action"] else ""
        body.append(f'<div class="card {i["severity"]}"><h3>{escape(i["title"])}</h3>'
                    f'<p>{escape(i["detail"])}</p>{act}</div>')

    if eda.get("monthly"):
        body += ["<h2>Revenue trend and forecast</h2>", embed(viz.revenue_trend(eda["monthly"], fc or None, sym, True))]
    for role in ("category", "region", "channel"):
        block = eda.get("breakdowns", {}).get(role)
        if block:
            body += [f"<h2>Performance by {escape(block['label'].lower())}</h2>",
                     embed(viz.breakdown_bar(block["rows"], block["label"], sym, True)),
                     _table(block["rows"], {"name": block["label"], "revenue": "Revenue", "profit": "Profit",
                                            "margin_pct": "Margin %", "share_pct": "Share %"})]
    if cust.get("top_customers"):
        body += ["<h2>Top customers</h2>",
                 _table(cust["top_customers"], {"customer_id": "Customer", "revenue": "Revenue", "profit": "Profit",
                                                "orders": "Orders", "share_pct": "Share %", "segment": "Segment"})]
    if cust.get("segments"):
        body.append(embed(viz.rfm_chart(cust["segments"], True)))
    anomalies = ctx.data("anomalies")
    if anomalies.get("top_records"):
        body += ["<h2>Most unusual order lines</h2>",
                 _table(anomalies["top_records"], {k: k.replace("_", " ").title()
                                                   for k in anomalies["top_records"][0]}, 10)]

    kpi_html = "".join(f'<div class="kpi"><b>{escape(v)}</b><span>{escape(k)}</span></div>' for k, v in tiles)
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>Analysis report</title><style>{CSS}</style></head>"
            f"<body><div class='wrap'><header><h1>Business Analysis Report</h1>"
            f"<p>{escape(ctx.source_name)} · generated {ctx.generated_at:%Y-%m-%d %H:%M} UTC · "
            f"{len(ctx.raw):,} rows × {ctx.raw.shape[1]} columns</p></header>"
            f"<div class='grid'>{kpi_html}</div>{''.join(body)}"
            f"<footer>Generated by Multi-Agent Data Analyst. Findings highlight patterns worth investigating; "
            f"they do not establish causation.</footer></div></body></html>")

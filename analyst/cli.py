"""Command-line interface: ``python -m analyst data.csv --out reports``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from analyst.config import AnalysisConfig
from analyst.io import DataLoadError
from analyst.orchestrator import run_analysis
from analyst.utils import money, pct

ICONS = {"success": "✔", "skipped": "–", "failed": "✘"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="analyst", description="Run the multi-agent sales analysis on a CSV file.")
    p.add_argument("csv", type=Path, help="Path to the input CSV file")
    p.add_argument("--out", type=Path, default=Path("reports"), help="Directory for JSON/HTML reports")
    p.add_argument("--no-report", action="store_true", help="Do not write report files")
    p.add_argument("--contamination", type=float, default=0.02, help="Expected anomaly share (0-0.5]")
    p.add_argument("--horizon", type=int, default=3, help="Forecast horizon in months (1-12)")
    p.add_argument("--llm", action="store_true", help="Polish the summary with an LLM (needs ANTHROPIC_API_KEY)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s")
    try:
        config = AnalysisConfig(contamination=args.contamination, forecast_horizon=args.horizon,
                                output_dir=None if args.no_report else args.out, use_llm=args.llm)
        ctx = run_analysis(args.csv, config)
    except (DataLoadError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"\nMulti-Agent Data Analyst · {ctx.source_name}\n{'─' * 60}")
    for r in ctx.results.values():
        note = f"  ({r.message})" if r.message else ""
        print(f" {ICONS[r.status]} {r.title:<28}{r.duration_ms:>8.0f} ms{note}")
    k = ctx.data("eda").get("kpis", {})
    if k:
        sym = ctx.schema.symbol
        print(f"\n Revenue {money(k['revenue'], sym)} | Orders {k['orders']:,}"
              + (f" | Margin {pct(k['margin_pct'])}" if "margin_pct" in k else ""))
    print(f"\n {ctx.data('summary').get('text', '')}\n")
    files = ctx.data("report").get("files", {})
    for kind, path in files.items():
        print(f" {kind.upper()} report → {path}")
    return 1 if any(r.status == "failed" for r in ctx.results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())

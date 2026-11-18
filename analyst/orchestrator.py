"""Pipeline orchestration over a shared context (blackboard architecture)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from analyst.agents.anomalies import AnomalyAgent
from analyst.agents.base import BaseAgent
from analyst.agents.cleaning import CleaningAgent
from analyst.agents.customers import CustomerAgent
from analyst.agents.eda import EDAAgent
from analyst.agents.forecasting import ForecastingAgent
from analyst.agents.insights import InsightsAgent
from analyst.agents.profiling import ProfilingAgent
from analyst.agents.quality import DataQualityAgent
from analyst.agents.report import ReportAgent
from analyst.agents.summary import SummaryAgent
from analyst.config import AnalysisConfig
from analyst.context import AgentResult, AnalysisContext
from analyst.io import load_dataset
from analyst.schema import detect_schema

logger = logging.getLogger("analyst")

ProgressCallback = Callable[[int, int, AgentResult], None]


def default_pipeline() -> list[BaseAgent]:
    """Execution order matters: later agents read what earlier agents publish."""
    return [DataQualityAgent(), ProfilingAgent(), CleaningAgent(), EDAAgent(), AnomalyAgent(),
            CustomerAgent(), ForecastingAgent(), InsightsAgent(), SummaryAgent(), ReportAgent()]


def run_analysis(source, config: AnalysisConfig | None = None, agents: list[BaseAgent] | None = None,
                 progress: ProgressCallback | None = None, source_name: str | None = None) -> AnalysisContext:
    """Run the full multi-agent analysis.

    Args:
        source: CSV path, bytes, file-like object or DataFrame.
        config: optional :class:`AnalysisConfig`.
        agents: override the default pipeline (useful for tests and extensions).
        progress: callback ``(index, total, result)`` fired after each agent.
        source_name: label shown in reports.
    """
    config = config or AnalysisConfig()
    raw = load_dataset(source)
    name = source_name or (Path(source).name if isinstance(source, (str, Path)) else "uploaded dataset")
    ctx = AnalysisContext(raw=raw, schema=detect_schema(raw), config=config, source_name=name)

    pipeline = agents if agents is not None else default_pipeline()
    for index, agent in enumerate(pipeline, start=1):
        result = agent.execute(ctx)
        ctx.results[agent.name] = result
        logger.info("%-22s %-8s %7.1f ms %s", agent.name, result.status, result.duration_ms, result.message)
        if progress:
            progress(index, len(pipeline), result)

    if ctx.clean is None:  # cleaning failed or was removed: downstream code can still use ctx.df
        ctx.clean = ctx.raw
    return ctx


__all__ = ["run_analysis", "default_pipeline"]

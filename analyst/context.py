"""Shared blackboard passed between agents, and the result envelope each agent returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from analyst.config import AnalysisConfig
from analyst.schema import Schema
from analyst.utils import to_native


@dataclass
class AgentResult:
    agent: str
    title: str
    status: str                      # "success" | "skipped" | "failed"
    duration_ms: float
    data: dict = field(default_factory=dict)
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "success"


@dataclass
class AnalysisContext:
    """Blackboard: agents read the dataset + earlier results and publish their own."""

    raw: pd.DataFrame
    schema: Schema
    config: AnalysisConfig
    source_name: str = "dataset"
    clean: pd.DataFrame | None = None
    results: dict[str, AgentResult] = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)   # non-JSON objects (DataFrames, HTML ...)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def df(self) -> pd.DataFrame:
        """Cleaned data when available, otherwise the raw frame."""
        return self.clean if self.clean is not None else self.raw

    def data(self, agent: str) -> dict:
        result = self.results.get(agent)
        return result.data if result and result.ok else {}

    def ok(self, agent: str) -> bool:
        return bool(self.results.get(agent) and self.results[agent].ok)

    @property
    def total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.results.values())

    def to_dict(self) -> dict:
        """JSON-safe export of all agent outputs (no row-level data)."""
        return to_native({
            "project": "Multi-Agent Data Analyst",
            "generated_at_utc": self.generated_at.isoformat(),
            "source": self.source_name,
            "schema": self.schema.as_dict(),
            "pipeline": [
                {"agent": r.agent, "title": r.title, "status": r.status,
                 "duration_ms": round(r.duration_ms, 1), "message": r.message}
                for r in self.results.values()
            ],
            "results": {name: r.data for name, r in self.results.items() if r.ok},
        })

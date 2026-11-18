"""Central, validated configuration for an analysis run."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AnalysisConfig:
    """Tunable parameters. Defaults are chosen to be safe for unknown datasets."""

    contamination: float = 0.02          # expected share of anomalous rows (Isolation Forest)
    top_n: int = 15                      # rows shown in "top N" tables
    forecast_horizon: int = 3            # months to forecast
    impute_threshold: float = 0.05       # impute core numeric fields only if <= 5% missing
    random_state: int = 42
    output_dir: Path | None = None       # when set, JSON + HTML reports are written here
    use_llm: bool = False                # optional LLM polish for the executive summary
    llm_model: str = field(default_factory=lambda: os.getenv("ANALYST_LLM_MODEL", "claude-sonnet-5-5"))

    def __post_init__(self) -> None:
        if not 0 < self.contamination <= 0.5:
            raise ValueError("contamination must be in (0, 0.5].")
        if self.top_n < 1:
            raise ValueError("top_n must be >= 1.")
        if not 1 <= self.forecast_horizon <= 12:
            raise ValueError("forecast_horizon must be between 1 and 12.")
        if not 0 <= self.impute_threshold <= 1:
            raise ValueError("impute_threshold must be between 0 and 1.")
        if self.output_dir is not None:
            self.output_dir = Path(self.output_dir)

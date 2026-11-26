"""Multi-Agent Data Analyst: a blackboard-style pipeline of specialised analytics agents."""

from analyst.config import AnalysisConfig
from analyst.context import AgentResult, AnalysisContext
from analyst.orchestrator import run_analysis

__version__ = "2.0.0"
__all__ = ["AnalysisConfig", "AgentResult", "AnalysisContext", "run_analysis", "__version__"]

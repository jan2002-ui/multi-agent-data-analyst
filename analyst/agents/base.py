"""Agent contract: declare required roles, implement ``run``; the base class handles the rest."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from time import perf_counter

from analyst.context import AgentResult, AnalysisContext

logger = logging.getLogger("analyst")


class SkipAgent(Exception):
    """Raise inside ``run`` to skip gracefully (e.g. not enough data)."""


class BaseAgent(ABC):
    name: str = "agent"
    title: str = "Agent"
    description: str = ""
    requires: tuple[str, ...] = ()       # schema roles that must be present

    @abstractmethod
    def run(self, ctx: AnalysisContext) -> dict:
        """Return a JSON-friendly dict. Raise SkipAgent to skip."""

    def execute(self, ctx: AnalysisContext) -> AgentResult:
        """Run with timing, role checks and failure isolation."""
        start = perf_counter()

        def result(status: str, data: dict | None = None, message: str = "") -> AgentResult:
            return AgentResult(self.name, self.title, status,
                               (perf_counter() - start) * 1000, data or {}, message)

        missing = [role for role in self.requires if not ctx.schema.has(role)]
        if missing:
            return result("skipped", message=f"Missing required fields: {', '.join(missing)}.")
        try:
            return result("success", self.run(ctx))
        except SkipAgent as exc:
            return result("skipped", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - one agent must never take down the pipeline
            logger.exception("Agent %s failed", self.name)
            return result("failed", message=f"{type(exc).__name__}: {exc}")

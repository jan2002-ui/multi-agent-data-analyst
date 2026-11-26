"""Optional LLM narration.

Only aggregated KPIs and insight headlines are sent - never row-level records or customer
identifiers. The feature is off by default and degrades silently to the deterministic summary.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("analyst")

SYSTEM_PROMPT = (
    "You are a senior business analyst. Write a concise executive summary (max 120 words) from the "
    "JSON provided. Use only the figures given, never invent numbers, and end with the single most "
    "important recommended action."
)


def llm_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def narrate(payload: dict, model: str, client=None) -> str | None:
    """Return an LLM-written summary, or None if unavailable / on any error."""
    try:
        if client is None:
            if not llm_available():
                return None
            import anthropic  # optional dependency
            client = anthropic.Anthropic()
        response = client.messages.create(
            model=model, max_tokens=400, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        return text.strip() or None
    except Exception as exc:  # noqa: BLE001 - narration is a nicety, never a failure point
        logger.warning("LLM narration unavailable: %s", exc)
        return None

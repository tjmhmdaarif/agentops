"""Optional LLM decision backend with hard fallback to deterministic rules.

The LLM can ONLY pick from the tool registry; its output is validated with
Pydantic. Any failure — missing SDK, timeout, invalid JSON, schema mismatch —
returns None and the caller silently falls back to rules.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from app.agent.prompts import SYSTEM_PROMPT, build_user_prompt
from app.core.config import Settings
from app.core.logging import get_logger
from app.tools.registry import ToolRegistry

log = get_logger("agent.llm")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm")


class LLMDecision(BaseModel):
    action: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: str = "medium"
    reason: str = ""
    requires_human: bool = False


class LLMDecider:
    def __init__(self, settings: Settings, registry: ToolRegistry) -> None:
        self.settings = settings
        self.registry = registry

    @property
    def available(self) -> bool:
        if not (self.settings.llm_enabled and self.settings.anthropic_api_key):
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def submit(self, briefing: dict[str, Any]) -> concurrent.futures.Future:
        return _executor.submit(self._call, briefing)

    def _call(self, briefing: dict[str, Any]) -> Optional[LLMDecision]:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
            message = client.messages.create(
                model=self.settings.llm_model,
                max_tokens=400,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": build_user_prompt(briefing, self.registry.describe_all()),
                }],
                timeout=self.settings.llm_timeout_seconds,
            )
            text = "".join(block.text for block in message.content if hasattr(block, "text"))
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                log.warning("llm_no_json")
                return None
            decision = LLMDecision.model_validate(json.loads(match.group(0)))
            if decision.action != "monitor" and decision.action not in self.registry.names():
                log.warning("llm_unknown_tool action=%s", decision.action)
                return None
            return decision
        except (ValidationError, json.JSONDecodeError) as exc:
            log.warning("llm_invalid_output %s", exc)
            return None
        except Exception as exc:  # network, auth, rate limits — all non-fatal
            log.warning("llm_unavailable %s: %s", type(exc).__name__, exc)
            return None

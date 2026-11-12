"""
Interface chung mà mọi provider (Anthropic, Gemini, ...) phải tuân theo.
Nhờ đó llm_caller.py, prompt_constructor.py, output_validator.py không
cần biết đang chạy với provider nào.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMCallResult:
    raw_text: str
    model: str
    stop_reason: Optional[str]
    input_tokens: int
    output_tokens: int
    attempts: list[dict[str, str]] = field(default_factory=list)


class LLMCallError(RuntimeError):
    def __init__(self, message, *, provider=None, model=None, status_code=None,
                 error_kind="unknown", fallback_eligible=False, attempts=None):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.error_kind = error_kind
        self.fallback_eligible = fallback_eligible
        self.attempts = list(attempts or [])


class LLMProvider(ABC):
    """Mọi provider implement một phương thức duy nhất: generate()."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
    ) -> LLMCallResult:
        ...

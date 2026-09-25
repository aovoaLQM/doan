"""
Interface chung mà mọi provider (Anthropic, Gemini, ...) phải tuân theo.
Nhờ đó llm_caller.py, prompt_constructor.py, output_validator.py không
cần biết đang chạy với provider nào.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMCallResult:
    raw_text: str
    model: str
    stop_reason: Optional[str]
    input_tokens: int
    output_tokens: int


class LLMCallError(RuntimeError):
    pass


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
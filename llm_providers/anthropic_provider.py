from __future__ import annotations

import os
from typing import Optional

import anthropic

from .base import LLMProvider, LLMCallResult, LLMCallError


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: Optional[str] = None):
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> LLMCallResult:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as e:  # noqa: BLE001
            raise LLMCallError(f"Lỗi gọi Anthropic API: {e}") from e

        text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        raw_text = "\n".join(text_blocks).strip()
        if not raw_text:
            raise LLMCallError("Anthropic trả về nội dung rỗng")

        return LLMCallResult(
            raw_text=raw_text,
            model=response.model,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
from __future__ import annotations

import os
from typing import Optional

from google import genai
from google.genai import types

from .base import LLMProvider, LLMCallResult, LLMCallError


class GeminiProvider(LLMProvider):
    """
    Dùng SDK mới `google-genai` (thay cho google-generativeai cũ).
    Cài: pip install google-genai --break-system-packages
    API key: đặt biến môi trường GEMINI_API_KEY hoặc truyền trực tiếp.
    """

    def __init__(self, model: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        self.model = model
        self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> LLMCallResult:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    # Ép JSON đầu ra để giảm rủi ro model chèn text ngoài JSON
                    response_mime_type="application/json",
                ),
            )
        except Exception as e:  # noqa: BLE001
            raise LLMCallError(f"Lỗi gọi Gemini API: {e}") from e

        raw_text = (response.text or "").strip()
        if not raw_text:
            raise LLMCallError("Gemini trả về nội dung rỗng")

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        finish_reason = None
        if getattr(response, "candidates", None):
            finish_reason = str(response.candidates[0].finish_reason)

        return LLMCallResult(
            raw_text=raw_text,
            model=self.model,
            stop_reason=finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
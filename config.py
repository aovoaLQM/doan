"""
Đọc cấu hình từ biến môi trường / .env và khởi tạo provider tương ứng.

Biến môi trường cần có:
  LLM_PROVIDER=anthropic | gemini      (mặc định: anthropic)
  ANTHROPIC_API_KEY=...                (nếu dùng anthropic)
  GEMINI_API_KEY=...                   (nếu dùng gemini)
  LLM_MODEL=...                        (tùy chọn, override model mặc định)
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

from llm_providers import LLMProvider, AnthropicProvider, GeminiProvider

load_dotenv()  # nạp file .env nếu có, không lỗi nếu không có file

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
}


def get_provider() -> LLMProvider:
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    model = os.environ.get("LLM_MODEL") or _DEFAULT_MODELS.get(provider_name)

    if provider_name == "anthropic":
        return AnthropicProvider(model=model)
    elif provider_name == "gemini":
        return GeminiProvider(model=model)
    else:
        raise ValueError(f"LLM_PROVIDER='{provider_name}' không được hỗ trợ (chỉ: anthropic, gemini)")
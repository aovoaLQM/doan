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
from pathlib import Path
from dotenv import dotenv_values

from llm_providers import LLMProvider, AnthropicProvider, GeminiProvider
from llm_providers.fallback import FallbackProvider
from llm_providers.errors import normalize_error

_ENV_PATH = Path(__file__).resolve().parent / ".env"

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
}


def get_provider() -> LLMProvider:
    # Read per request: local project settings take priority over stale process values.
    settings = dict(os.environ)
    settings.update({key: value for key, value in dotenv_values(_ENV_PATH).items() if value is not None})
    provider_name = settings.get("LLM_PROVIDER", "anthropic").strip().lower()
    model = settings.get("LLM_MODEL", "").strip() or _DEFAULT_MODELS.get(provider_name)

    if provider_name == "anthropic":
        provider_type = AnthropicProvider
    elif provider_name == "gemini":
        provider_type = GeminiProvider
    else:
        raise ValueError(f"LLM_PROVIDER='{provider_name}' không được hỗ trợ (chỉ: anthropic, gemini)")

    models = list(dict.fromkeys([model] + [
        item.strip() for item in settings.get("LLM_FALLBACK_MODELS", "").split(",") if item.strip()
    ]))

    def create(selected_model):
        try:
            key_name = "GEMINI_API_KEY" if provider_name == "gemini" else "ANTHROPIC_API_KEY"
            return provider_type(model=selected_model, api_key=settings.get(key_name), fallback_mode=len(models) > 1)
        except Exception as error:
            raise normalize_error(error, provider_name, selected_model) from error

    return FallbackProvider(provider_name, models, create) if len(models) > 1 else create(model)

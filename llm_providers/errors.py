"""Classify SDK errors without inspecting response messages."""
import httpx
import anthropic
from google.genai.errors import APIError

from .base import LLMCallError

TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}
FALLBACK_CODES = TRANSIENT_CODES | {400, 401, 403, 404}


def normalize_error(error, provider, model):
    code = None
    if isinstance(error, APIError):
        code = error.code
    elif isinstance(error, anthropic.APIStatusError):
        code = error.status_code
    if isinstance(error, (TimeoutError, httpx.TimeoutException, anthropic.APITimeoutError)):
        kind = "timeout"
    elif isinstance(error, (ConnectionError, httpx.NetworkError, anthropic.APIConnectionError)):
        kind = "connection"
    else:
        kind = {
            408: "timeout", 429: "quota_or_rate_limit", 500: "server_error",
            502: "server_error", 503: "overloaded", 504: "timeout",
            400: "invalid_request", 401: "authentication", 403: "permission",
            404: "model_not_found",
        }.get(code, "api_error" if code is not None else "internal_error")
    eligible = code in FALLBACK_CODES or kind in {"timeout", "connection"}
    detail = "quá tải tạm thời" if code == 503 else kind
    return LLMCallError(
        f"{provider} ({model}): {detail}" + (f" (HTTP {code})" if code else ""),
        provider=provider, model=model, status_code=code, error_kind=kind,
        fallback_eligible=eligible,
    )

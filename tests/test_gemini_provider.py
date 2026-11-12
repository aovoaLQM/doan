from types import SimpleNamespace
from unittest.mock import patch

import pytest
from google.genai.errors import ServerError, ClientError

from llm_providers import GeminiProvider, LLMCallError


def test_gemini_uses_bounded_sdk_retries():
    with patch("llm_providers.gemini_provider.genai.Client") as client:
        GeminiProvider(api_key="test-key")
    retry = client.call_args.kwargs["http_options"].retry_options
    assert client.call_args.kwargs["http_options"].timeout == 60000
    assert retry.attempts == 4
    assert 503 in retry.http_status_codes
    assert 403 not in retry.http_status_codes
    assert retry.initial_delay < retry.max_delay <= 10


@pytest.mark.parametrize("code,error_type", [(503, ServerError), (403, ClientError)])
def test_gemini_api_errors(code, error_type):
    error = error_type(code, {"error": {"code": code, "message": "API error"}})
    with patch("llm_providers.gemini_provider.genai.Client") as client:
        provider = GeminiProvider(api_key="test-key")
        client.return_value.models.generate_content.side_effect = error
        with pytest.raises(LLMCallError) as caught:
            provider.generate("system", "user")
    assert caught.value.__cause__ is error
    assert ("quá tải" in str(caught.value)) == (code == 503)


def test_gemini_success_keeps_json_and_usage():
    with patch("llm_providers.gemini_provider.genai.Client") as client:
        provider = GeminiProvider(api_key="test-key")
        client.return_value.models.generate_content.return_value = SimpleNamespace(
            text=' {"ok": true} ', candidates=[],
            usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=8),
        )
        result = provider.generate("system", "user", max_tokens=4000)
        config = client.return_value.models.generate_content.call_args.kwargs["config"]
    assert result.raw_text == '{"ok": true}'
    assert (result.input_tokens, result.output_tokens) == (12, 8)
    assert config.response_mime_type == "application/json"
    assert config.max_output_tokens == 4000

from unittest.mock import Mock

import httpx
import pytest
import anthropic
from google.genai.errors import ClientError

from llm_providers.base import LLMCallError, LLMCallResult
from llm_providers.errors import normalize_error
from llm_providers.fallback import FallbackProvider


@pytest.mark.parametrize("provider", ["gemini", "anthropic"])
@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_errors_continue_to_next_model(provider, code):
    if provider == "gemini":
        sdk_error = ClientError(code, {"error": {"message": "not available"}})
    else:
        response = httpx.Response(code, request=httpx.Request("POST", "https://test.invalid"))
        sdk_error = anthropic.APIStatusError("not available", response=response, body={})
    error = normalize_error(sdk_error, provider, "main")
    main = Mock()
    main.generate.side_effect = error
    backup = Mock()
    backup.generate.return_value = LLMCallResult("{}", "backup", None, 1, 1)
    factory = Mock(side_effect=[main, backup])
    chain = FallbackProvider(provider, ["main", "backup"], factory)
    result = chain.generate("system", "prompt")
    assert result.model == "backup"
    assert result.attempts[0]["error_kind"] == {
        400: "invalid_request", 401: "authentication",
        403: "permission", 404: "model_not_found",
    }[code]
    assert factory.call_count == 2
    assert main.generate.call_args == backup.generate.call_args


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_all_models_fail_returns_attempt_history(code):
    error = normalize_error(ClientError(code, {}), "gemini", "missing")
    instance = Mock()
    instance.generate.side_effect = error
    chain = FallbackProvider("gemini", ["missing", "also-missing"], Mock(return_value=instance))
    with pytest.raises(LLMCallError) as caught:
        chain.generate("system", "prompt")
    assert [a["model"] for a in caught.value.attempts] == ["missing", "also-missing"]
    assert caught.value.error_kind == error.error_kind

from unittest.mock import patch

import config


def test_project_env_refreshes_key_model_and_fallback(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr(config, "_ENV_PATH", env)
    monkeypatch.setenv("GEMINI_API_KEY", "stale-process-key")
    env.write_text("LLM_PROVIDER=gemini\nGEMINI_API_KEY=first-key\nLLM_MODEL=first\nLLM_FALLBACK_MODELS=\n")
    with patch("config.GeminiProvider") as provider:
        config.get_provider()
        provider.assert_called_once_with(model="first", api_key="first-key", fallback_mode=False)
        env.write_text("LLM_PROVIDER=gemini\nGEMINI_API_KEY=new-key\nLLM_MODEL=new\nLLM_FALLBACK_MODELS=backup\n")
        chain = config.get_provider()
        assert chain.models == ("new", "backup")
        chain.factory("backup")
        assert provider.call_args.kwargs == dict(model="backup", api_key="new-key", fallback_mode=True)


def test_environment_used_when_project_env_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_MODEL", "main")
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "")
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    with patch("config.GeminiProvider") as provider:
        config.get_provider()
        provider.assert_called_once_with(model="main", api_key="env-key", fallback_mode=False)

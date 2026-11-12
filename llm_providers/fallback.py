from .base import LLMProvider, LLMCallError


class FallbackProvider(LLMProvider):
    """A lazy, ordered chain; no retries or state carried between requests."""

    def __init__(self, provider, models, factory):
        self.provider = provider
        self.models = tuple(models)
        self.factory = factory

    def generate(self, system_prompt, user_prompt, max_tokens=2000):
        attempts = []
        last_error = None
        for model in self.models:
            try:
                instance = self.factory(model)
                result = instance.generate(system_prompt, user_prompt, max_tokens=max_tokens)
            except LLMCallError as error:
                attempts.append({"model": model, "status": "error", "error_kind": error.error_kind})
                error.attempts = list(attempts)
                if not error.fallback_eligible:
                    raise
                last_error = error
                continue
            attempts.append({"model": model, "status": "success", "error_kind": ""})
            result.attempts = list(attempts)
            return result
        summary = "; ".join(f"{a['model']}: {a['error_kind']}" for a in attempts)
        raise LLMCallError(
            f"Không model nào hoàn tất yêu cầu: {summary}", provider=self.provider,
            model=last_error.model, status_code=last_error.status_code,
            error_kind=last_error.error_kind, attempts=attempts,
        ) from last_error

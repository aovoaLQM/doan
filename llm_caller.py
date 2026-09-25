"""
[3] LLM call
-------------
Gọi LLM (qua provider đã cấu hình trong config.py) để sinh bản nháp kịch bản.
Không còn phụ thuộc trực tiếp vào SDK của bất kỳ hãng nào — đổi provider
chỉ cần đổi biến môi trường LLM_PROVIDER, không sửa file này.
"""

from __future__ import annotations

import json

from config import get_provider
from llm_providers import LLMCallResult, LLMCallError  # re-export cho tiện import ở nơi khác
from schema_builder import ScenarioParams
from prompt_constructor import SYSTEM_PROMPT, build_user_prompt


def call_llm(params: ScenarioParams, max_tokens: int = 8000) -> LLMCallResult:
    """
    Gọi LLM (provider lấy từ config) để sinh bản nháp kịch bản dựa trên
    ScenarioParams đã validate. Raise LLMCallError nếu gọi API thất bại.
    """
    provider = get_provider()
    user_prompt = build_user_prompt(params)
    return provider.generate(SYSTEM_PROMPT, user_prompt, max_tokens=max_tokens)


def strip_code_fences(text: str) -> str:
    """Phòng trường hợp LLM vẫn bọc kết quả trong ```json ... ``` dù đã dặn không làm vậy."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def parse_llm_json(result: LLMCallResult) -> dict:
    """Parse JSON từ raw_text; raise LLMCallError nếu không phải JSON hợp lệ."""
    cleaned = strip_code_fences(result.raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMCallError(f"LLM không trả về JSON hợp lệ: {e}\nNội dung nhận được:\n{cleaned[:500]}") from e


if __name__ == "__main__":
    from schema_builder import build_scenario_params

    params = build_scenario_params(
        attack_type="bec",
        learner_role="nhan_vien_ke_toan",
        business_context="chuyen_khoan_khan",
        manipulation_mechanism="authority",
        difficulty_level="intermediate",
        red_flags_required=3,
    )
    result = call_llm(params)
    print(f"Model: {result.model}, tokens in/out: {result.input_tokens}/{result.output_tokens}")
    parsed = parse_llm_json(result)
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
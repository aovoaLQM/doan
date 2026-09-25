"""
Pipeline runner [1] -> [4]
---------------------------
Ghép toàn bộ 4 bước đầu. Kết quả trả về là một PipelineOutcome đưa sang
hàng đợi human review ([5]) — module này KHÔNG tự xuất bản (export)
bất kỳ nội dung nào, kể cả khi is_valid=True.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

from schema_builder import build_scenario_params, ScenarioParams, SchemaValidationError
from llm_caller import call_llm, parse_llm_json, LLMCallError, LLMCallResult
from output_validator import validate_output, ValidationResult


@dataclass
class PipelineOutcome:
    status: str  # "ready_for_review" | "input_rejected" | "llm_error" | "validation_failed"
    params: Optional[ScenarioParams] = None
    llm_result: Optional[LLMCallResult] = None
    validation: Optional[ValidationResult] = None
    error_message: Optional[str] = None

    def to_review_payload(self) -> dict[str, Any]:
        """Định dạng gọn để đưa vào hàng đợi human review ở bước [5]."""
        return {
            "status": self.status,
            "scenario_id": self.params.scenario_id if self.params else None,
            "input_params": self.params.to_dict() if self.params else None,
            "llm_output": self.validation.normalized_output if self.validation else None,
            "validation_issues": [
                {"severity": i.severity, "field": i.field, "message": i.message}
                for i in (self.validation.issues if self.validation else [])
            ],
            "error_message": self.error_message,
            "requires_manual_approval": self.status == "ready_for_review",
        }


def run_pipeline(
    attack_type: str,
    learner_role: str,
    business_context: str,
    manipulation_mechanism: str,
    difficulty_level: str,
    red_flags_required: int,
    language: str = "vi",
    output_format: str = "json",
) -> PipelineOutcome:
    # [1] Schema builder
    try:
        params = build_scenario_params(
            attack_type=attack_type,
            learner_role=learner_role,
            business_context=business_context,
            manipulation_mechanism=manipulation_mechanism,
            difficulty_level=difficulty_level,
            red_flags_required=red_flags_required,
            language=language,
            output_format=output_format,
        )
    except SchemaValidationError as e:
        return PipelineOutcome(status="input_rejected", error_message=str(e))

    # [2] Prompt constructor được gọi bên trong [3] call_llm (dùng build_user_prompt)
    # [3] LLM call — provider (Anthropic/Gemini) được chọn qua LLM_PROVIDER trong .env
    try:
        llm_result = call_llm(params)
        parsed = parse_llm_json(llm_result)
    except LLMCallError as e:
        return PipelineOutcome(status="llm_error", params=params, error_message=str(e))

    # [4] Output validator
    validation = validate_output(parsed, params)

    status = "ready_for_review" if validation.is_valid else "validation_failed"
    return PipelineOutcome(
        status=status,
        params=params,
        llm_result=llm_result,
        validation=validation,
    )


if __name__ == "__main__":
    import json

    outcome = run_pipeline(
        attack_type="bec",
        learner_role="nhan_vien_ke_toan",
        business_context="chuyen_khoan_khan",
        manipulation_mechanism="authority",
        difficulty_level="intermediate",
        red_flags_required=3,
    )
    print(json.dumps(outcome.to_review_payload(), ensure_ascii=False, indent=2))
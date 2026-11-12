import pytest

from prompt_constructor import build_user_prompt, _format_library
from schema_builder import (
    AttackType as A, BusinessContext as C, CompetencyGroup,
    ScenarioGroup, SchemaValidationError, allowed_attacks, allowed_contexts,
    build_scenario_params, allowed_groups,
)


CASES = {
    C.COLLEAGUE_SUPPORT: [A.CHAT_IMPERSONATION, A.PHISHING_EMAIL],
    C.EMPLOYEE_BENEFITS: [A.PHISHING_EMAIL, A.CHAT_IMPERSONATION, A.SMISHING],
    C.INTERNAL_RESALE: [A.CHAT_IMPERSONATION, A.PHISHING_EMAIL],
}


@pytest.mark.parametrize("group", list(ScenarioGroup))
def test_part_iv_accepts_all_groups(group):
    context = allowed_contexts(group)[0]
    params = make_params(context, allowed_attacks(context)[0], scenario_group=group.value)
    prompt = build_user_prompt(params)
    assert "Phần IV" in prompt
    assert "không tự đổi nhóm kịch bản" in prompt
    assert "PHẢI khác hẳn 3 nhóm huấn luyện chính" not in prompt
    assert allowed_groups(CompetencyGroup.PRINCIPLE_APPLICATION) == list(ScenarioGroup)
    for competency in CompetencyGroup:
        if competency in (CompetencyGroup.SIGN_RECOGNITION, CompetencyGroup.MANIPULATION_RECOGNITION):
            assert allowed_groups(competency) == [ScenarioGroup.LEADER, ScenarioGroup.IT, ScenarioGroup.BANK]


def make_params(context, attack, level="beginner", count=3, **overrides):
    values = dict(
        attack_type=attack.value, learner_role="nhan_vien_van_phong",
        business_context=context.value, manipulation_mechanism="urgency",
        difficulty_level=level, competency_group="van_dung_nguyen_tac",
        scenario_group="tinh_huong_khac", red_flags_required=count,
    )
    values.update(overrides)
    return build_scenario_params(**values)


@pytest.mark.parametrize("context,attacks", CASES.items())
def test_contexts_are_exclusive_to_other(context, attacks):
    assert allowed_attacks(context) == attacks
    assert len(allowed_contexts(ScenarioGroup.OTHER)) == 11
    for group in ScenarioGroup:
        assert (context in allowed_contexts(group)) == (group == ScenarioGroup.OTHER)
    for competency in CompetencyGroup:
        if competency in (CompetencyGroup.SIGN_RECOGNITION, CompetencyGroup.MANIPULATION_RECOGNITION):
            with pytest.raises(SchemaValidationError):
                make_params(context, attacks[0], competency_group=competency.value)
    for attack in A:
        if attack not in attacks:
            with pytest.raises(SchemaValidationError):
                make_params(context, attack)


@pytest.mark.parametrize("context,attack", [
    (context, attack) for context, attacks in CASES.items() for attack in attacks
])
@pytest.mark.parametrize("level,count", [("beginner", 3), ("intermediate", 2), ("advanced", 1)])
@pytest.mark.parametrize("competency,part", [(CompetencyGroup.PRINCIPLE_APPLICATION, "Phần IV"), (CompetencyGroup.RESPONSE_BEHAVIOR, "Phần III")])
def test_new_context_prompts(context, attack, level, count, competency, part):
    params = make_params(context, attack, level, count, competency_group=competency.value)
    prompt = build_user_prompt(params)
    channel = {A.CHAT_IMPERSONATION: "chat", A.PHISHING_EMAIL: "email", A.SMISHING: "sms"}[attack]
    assert f'Kênh: "{channel}"' in prompt
    assert context.value in prompt
    assert part in prompt
    assert "Mốc tham khảo (chỉ chọn dữ kiện đáp án/lời giải cần)" in prompt
    assert "Hành vi an toàn đầy đủ" in prompt
    library = _format_library(params, "other")
    assert "nang_cao" in library
    if context == C.INTERNAL_RESALE:
        assert "đặt cọc" in prompt

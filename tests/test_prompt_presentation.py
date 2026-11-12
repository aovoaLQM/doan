import pytest

from prompt_constructor import (
    _pick_names, _fictional_names_block, _target_flag_block, build_user_prompt,
)
from schema_builder import (
    CompetencyGroup, DifficultyLevel, LearnerRole, ScenarioGroup,
    allowed_groups, allowed_contexts, allowed_attacks, build_scenario_params,
)


def combinations():
    for competency in CompetencyGroup:
        for group in allowed_groups(competency):
            for context in allowed_contexts(group):
                for attack in allowed_attacks(context):
                    for difficulty in DifficultyLevel:
                        yield competency, group, context, attack, difficulty


def params_for(case, role=LearnerRole.OFFICE_STAFF):
    competency, group, context, attack, difficulty = case
    return build_scenario_params(
        competency_group=competency.value, scenario_group=group.value,
        business_context=context.value, attack_type=attack.value,
        learner_role=role.value, manipulation_mechanism="urgency",
        difficulty_level=difficulty.value,
        red_flags_required=1 if difficulty == DifficultyLevel.ADVANCED else 3,
    )


@pytest.mark.parametrize("case", list(combinations()))
def test_prompts_keep_short_opening_and_required_evidence(case):
    params = params_for(case)
    names = _pick_names(params)
    assert names == _pick_names(params)
    for entity in ("company", "partner", "bank", "courier", "cloud"):
        official = names[entity + "_domain"]
        fake = names["fake_" + entity]
        assert official.endswith((".vn", ".com", ".net"))
        assert fake.endswith((".vn", ".com", ".net"))
        assert official != fake
    prompt = build_user_prompt(params)
    assert "tối đa 50 từ" in prompt
    assert "Chỉ thêm quy trình/mốc đối chiếu nếu đáp án hoặc lời giải cần đến" in prompt
    assert "Mốc đối chiếu narrative PHẢI nêu" not in prompt
    assert "bằng câu dẫn bối cảnh trung tính" not in prompt
    assert names["recipient_email"] in prompt
    assert names["recipient_email"].endswith("@" + names["company_domain"])
    assert "không tô đậm/in nghiêng riêng ký tự khác biệt" in prompt
    assert params.competency_group.value in prompt


@pytest.mark.parametrize("role", [LearnerRole.OFFICE_STAFF, LearnerRole.IT_HELPDESK])
def test_internal_email_has_concrete_role_address(role):
    case = next(c for c in combinations() if c[1] == ScenarioGroup.IT)
    params = params_for(case, role)
    names = _pick_names(params)
    block = _fictional_names_block(params, names)
    local = "nhan.vien" if role == LearnerRole.IT_HELPDESK else "it.helpdesk"
    assert f"Từ: {local}@{names['fake_company']}" in block
    assert f"Đến: {names['recipient_email']}" in block
    assert "dùng tên miền\n  trong dòng Đến" in block


def test_external_sender_uses_own_domain():
    case = next(c for c in combinations() if c[1] == ScenarioGroup.BANK)
    params = params_for(case)
    names = _pick_names(params)
    block = _fictional_names_block(params, names)
    assert f"Từ: cham.soc@{names['fake_bank']}" in block
    assert "tên miền người nhận KHÔNG chứng minh tên miền" in block


def test_target_still_requires_evidence_for_thresholds():
    block = _target_flag_block(("yêu cầu thanh toán vượt ngưỡng phê duyệt", "trung_binh"))
    assert "PHẢI cung cấp đúng mốc" in block
    assert "số tiền phải khớp điều kiện vi phạm" in block


@pytest.mark.parametrize("role", list(LearnerRole))
@pytest.mark.parametrize("competency,group", [
    (competency, group) for competency in CompetencyGroup for group in allowed_groups(competency)
])
def test_selected_role_is_explicit_across_groups(role, competency, group):
    labels = {
        LearnerRole.ACCOUNTANT: "nhân viên kế toán",
        LearnerRole.IT_HELPDESK: "nhân viên IT Helpdesk",
        LearnerRole.MID_MANAGER: "quản lý cấp trung",
        LearnerRole.RECEPTIONIST: "lễ tân",
        LearnerRole.NEW_HIRE: "nhân viên mới",
        LearnerRole.HR_STAFF: "nhân viên HR",
        LearnerRole.OFFICE_STAFF: "nhân viên văn phòng",
    }
    context = allowed_contexts(group)[0]
    case = (competency, group, context, allowed_attacks(context)[0], DifficultyLevel.BEGINNER)
    prompt = build_user_prompt(params_for(case, role))
    assert f"Vai trò đã chọn: {labels[role]} (learner_role={role.value})" in prompt
    assert f'"Bạn là {labels[role]} tại' in prompt
    assert "không tự đổi nghề để khớp bối cảnh" in prompt
    assert "người học — nhân viên có quyền xử lý giao dịch" not in prompt
    assert "Bạn là chuyên viên kế toán" not in prompt

"""[1] Schema builder — tham số hóa kịch bản đào tạo."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class AttackType(str, Enum):
    PHISHING_EMAIL = "phishing_email"
    VISHING = "vishing"
    SMISHING = "smishing"
    BEC = "bec"
    PRETEXTING = "pretexting"
    TAILGATING = "tailgating"
    QUID_PRO_QUO = "quid_pro_quo"


class LearnerRole(str, Enum):
    ACCOUNTANT = "nhan_vien_ke_toan"
    IT_HELPDESK = "it_helpdesk"
    MID_MANAGER = "quan_ly_cap_trung"
    RECEPTIONIST = "le_tan"
    NEW_HIRE = "nhan_vien_moi"
    HR_STAFF = "nhan_vien_hr"
    OFFICE_STAFF = "nhan_vien_van_phong"


class BusinessContext(str, Enum):
    URGENT_TRANSFER = "chuyen_khoan_khan"
    PASSWORD_RESET = "reset_mat_khau"
    CONTRACT_SIGNING = "ky_hop_dong"
    INVOICE_PROCESSING = "xu_ly_hoa_don"
    RECRUITMENT = "tuyen_dung"
    VENDOR_ONBOARDING = "onboard_nha_cung_cap"
    ACCOUNT_SECURITY_ALERT = "canh_bao_bao_mat_tai_khoan"
    REMOTE_IT_SUPPORT = "ho_tro_ky_thuat_tu_xa"
    BANK_TRANSACTION_VERIFICATION = "xac_minh_giao_dich_ngan_hang"


class ManipulationMechanism(str, Enum):
    AUTHORITY = "authority"
    URGENCY = "urgency"
    SCARCITY = "scarcity"
    SOCIAL_PROOF = "social_proof"
    FAMILIARITY = "familiarity_liking"
    FEAR = "fear_intimidation"


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class CompetencyGroup(str, Enum):
    """4 nhóm năng lực theo mục 3.6.2 — người dùng chọn TRƯỚC, LLM phải bám đúng."""
    SIGN_RECOGNITION = "nhan_dien_dau_hieu"                    # Phần I
    MANIPULATION_RECOGNITION = "nhan_biet_co_che_thao_tung"    # Phần II
    RESPONSE_BEHAVIOR = "lua_chon_hanh_vi_ung_pho"             # Phần III
    PRINCIPLE_APPLICATION = "van_dung_nguyen_tac"              # Phần IV


class OutputFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    DOCX = "docx"


class SchemaValidationError(ValueError):
    pass


_RED_FLAG_BOUNDS: dict[DifficultyLevel, tuple[int, int]] = {
    DifficultyLevel.BEGINNER: (3, 6),
    DifficultyLevel.INTERMEDIATE: (2, 4),
    DifficultyLevel.ADVANCED: (1, 2),
}

_SUPPORTED_LANGUAGES = {"vi", "en"}


@dataclass(frozen=True)
class ScenarioParams:
    attack_type: AttackType
    learner_role: LearnerRole
    business_context: BusinessContext
    manipulation_mechanism: ManipulationMechanism
    difficulty_level: DifficultyLevel
    competency_group: CompetencyGroup
    red_flags_required: int
    language: str = "vi"
    output_format: OutputFormat = OutputFormat.JSON
    scenario_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requester_note: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, Enum):
                d[k] = v.value
        return d


def build_scenario_params(
    attack_type: str,
    learner_role: str,
    business_context: str,
    manipulation_mechanism: str,
    difficulty_level: str,
    competency_group: str,
    red_flags_required: int,
    language: str = "vi",
    output_format: str = "json",
    requester_note: Optional[str] = None,
) -> ScenarioParams:
    errors: list[str] = []

    def _coerce_enum(enum_cls, value, field_name):
        try:
            return enum_cls(value)
        except ValueError:
            valid = ", ".join(e.value for e in enum_cls)
            errors.append(f"{field_name}='{value}' không hợp lệ. Giá trị cho phép: {valid}")
            return None

    attack_type_e = _coerce_enum(AttackType, attack_type, "attack_type")
    learner_role_e = _coerce_enum(LearnerRole, learner_role, "learner_role")
    business_context_e = _coerce_enum(BusinessContext, business_context, "business_context")
    manipulation_e = _coerce_enum(ManipulationMechanism, manipulation_mechanism, "manipulation_mechanism")
    difficulty_e = _coerce_enum(DifficultyLevel, difficulty_level, "difficulty_level")
    competency_e = _coerce_enum(CompetencyGroup, competency_group, "competency_group")
    output_format_e = _coerce_enum(OutputFormat, output_format, "output_format")

    if language not in _SUPPORTED_LANGUAGES:
        errors.append(f"language='{language}' không hợp lệ.")

    if not isinstance(red_flags_required, int):
        errors.append("red_flags_required phải là số nguyên")
    elif difficulty_e is not None:
        lo, hi = _RED_FLAG_BOUNDS[difficulty_e]
        if not (lo <= red_flags_required <= hi):
            errors.append(
                f"red_flags_required={red_flags_required} không phù hợp difficulty_level="
                f"{difficulty_e.value} (yêu cầu {lo}-{hi})"
            )

    if requester_note and len(requester_note) > 500:
        errors.append("requester_note quá dài")

    if errors:
        raise SchemaValidationError("; ".join(errors))

    return ScenarioParams(
        attack_type=attack_type_e,
        learner_role=learner_role_e,
        business_context=business_context_e,
        manipulation_mechanism=manipulation_e,
        difficulty_level=difficulty_e,
        competency_group=competency_e,
        red_flags_required=red_flags_required,
        language=language,
        output_format=output_format_e,
        requester_note=requester_note,
    )
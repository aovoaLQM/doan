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
    CHAT_IMPERSONATION = "chat_impersonation"   # giả danh qua ứng dụng chat / mạng xã hội
    QUISHING = "quishing"                       # mã QR giả
    BAITING = "baiting"                         # vật mồi (USB, thiết bị bỏ quên)


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
    # --- Giả danh IT: bổ sung ---
    MAILBOX_QUOTA = "hop_thu_day_hoac_het_han"
    SOFTWARE_UPDATE = "cai_phan_mem_ban_va"
    MFA_CONFIRMATION = "xac_nhan_dang_nhap_mfa"
    # --- Giả danh ngân hàng: bổ sung ---
    BANK_KYC_UPDATE = "cap_nhat_thong_tin_ekyc"
    BANK_CANCEL_OTP = "huy_giao_dich_doc_otp"
    BANK_CARD_LOCKED = "the_tai_khoan_bi_khoa"
    BANK_PROMOTION = "uu_dai_hoan_tien_han_muc"
    BANK_APP_UPDATE = "cap_nhat_ung_dung_smart_otp"
    # --- Nhóm "Khác" (tình huống mới, dùng cho Phần IV) ---
    GIFT_CARD_REQUEST = "nho_mua_the_qua_tang"
    GOV_AGENCY = "gia_danh_co_quan_nha_nuoc"
    DELIVERY_FEE = "giao_hang_phi_theo_doi"
    RECRUITER_PARTNER = "nha_tuyen_dung_doi_tac"
    CLOUD_DOCUMENT = "dich_vu_dam_may_tai_lieu"
    PHYSICAL_ACCESS = "ra_vao_van_phong"
    BAITING_DEVICE = "thiet_bi_ma_qr_la"
    SURVEY_REWARD = "khao_sat_nhan_qua"
    COLLEAGUE_SUPPORT = "dong_nghiep_nho_ho_tro"
    EMPLOYEE_BENEFITS = "dang_ky_cong_doan_phuc_loi"
    INTERNAL_RESALE = "mua_ban_thanh_ly_noi_bo"


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


class ScenarioGroup(str, Enum):
    """Nhóm kịch bản: 3 nhóm huấn luyện chính (mục 3.3-3.5) + nhóm "Khác" (tình huống mới)."""
    LEADER = "gia_danh_lanh_dao"
    IT = "gia_danh_it"
    BANK = "gia_danh_ngan_hang"
    OTHER = "tinh_huong_khac"


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


# ---------------------------------------------------------------------------
# Chuỗi lựa chọn phụ thuộc:  Nhóm năng lực -> Nhóm kịch bản -> Bối cảnh -> Loại tấn công (kênh/kỹ thuật)
# Mục đích: chặn tổ hợp mâu thuẫn ngay từ đầu để LLM không phải đoán ai giả danh ai.
#   - Phần I-II dùng 3 nhóm huấn luyện chính; Phần III-IV cho phép cả 4 nhóm.
#   - "pretexting" là nhãn chung cho giả danh IT/Helpdesk.
# ---------------------------------------------------------------------------
_GROUP_CONTEXTS: dict[ScenarioGroup, list[BusinessContext]] = {
    ScenarioGroup.LEADER: [
        BusinessContext.URGENT_TRANSFER, BusinessContext.INVOICE_PROCESSING,
        BusinessContext.VENDOR_ONBOARDING, BusinessContext.CONTRACT_SIGNING, BusinessContext.RECRUITMENT,
    ],
    ScenarioGroup.IT: [
        BusinessContext.PASSWORD_RESET, BusinessContext.ACCOUNT_SECURITY_ALERT,
        BusinessContext.REMOTE_IT_SUPPORT, BusinessContext.MAILBOX_QUOTA,
        BusinessContext.SOFTWARE_UPDATE, BusinessContext.MFA_CONFIRMATION,
    ],
    ScenarioGroup.BANK: [
        BusinessContext.BANK_TRANSACTION_VERIFICATION, BusinessContext.BANK_KYC_UPDATE,
        BusinessContext.BANK_CANCEL_OTP, BusinessContext.BANK_CARD_LOCKED,
        BusinessContext.BANK_PROMOTION, BusinessContext.BANK_APP_UPDATE,
    ],
    ScenarioGroup.OTHER: [
        BusinessContext.GIFT_CARD_REQUEST, BusinessContext.GOV_AGENCY, BusinessContext.DELIVERY_FEE,
        BusinessContext.RECRUITER_PARTNER, BusinessContext.CLOUD_DOCUMENT, BusinessContext.PHYSICAL_ACCESS,
        BusinessContext.BAITING_DEVICE, BusinessContext.SURVEY_REWARD,
        BusinessContext.COLLEAGUE_SUPPORT, BusinessContext.EMPLOYEE_BENEFITS,
        BusinessContext.INTERNAL_RESALE,
    ],
}

_A, _C = AttackType, BusinessContext
_CONTEXT_ATTACKS: dict[BusinessContext, list[AttackType]] = {
    # Giả danh lãnh đạo
    _C.URGENT_TRANSFER: [_A.BEC], _C.INVOICE_PROCESSING: [_A.BEC], _C.VENDOR_ONBOARDING: [_A.BEC],
    _C.CONTRACT_SIGNING: [_A.BEC], _C.RECRUITMENT: [_A.BEC],
    # Giả danh IT/Helpdesk
    _C.PASSWORD_RESET: [_A.PRETEXTING, _A.PHISHING_EMAIL, _A.VISHING, _A.SMISHING],
    _C.ACCOUNT_SECURITY_ALERT: [_A.PRETEXTING, _A.PHISHING_EMAIL, _A.VISHING, _A.SMISHING],
    _C.REMOTE_IT_SUPPORT: [_A.PRETEXTING, _A.VISHING, _A.PHISHING_EMAIL],
    _C.MAILBOX_QUOTA: [_A.PRETEXTING, _A.PHISHING_EMAIL, _A.SMISHING],
    _C.SOFTWARE_UPDATE: [_A.PRETEXTING, _A.PHISHING_EMAIL, _A.VISHING],
    _C.MFA_CONFIRMATION: [_A.PRETEXTING, _A.VISHING, _A.SMISHING],
    # Giả danh ngân hàng
    _C.BANK_TRANSACTION_VERIFICATION: [_A.PHISHING_EMAIL, _A.VISHING, _A.SMISHING],
    _C.BANK_KYC_UPDATE: [_A.PHISHING_EMAIL, _A.VISHING, _A.SMISHING],
    _C.BANK_CANCEL_OTP: [_A.VISHING, _A.SMISHING],
    _C.BANK_CARD_LOCKED: [_A.PHISHING_EMAIL, _A.VISHING, _A.SMISHING],
    _C.BANK_PROMOTION: [_A.PHISHING_EMAIL, _A.SMISHING, _A.VISHING],
    _C.BANK_APP_UPDATE: [_A.PHISHING_EMAIL, _A.SMISHING],
    # Nhóm "Khác"
    _C.GIFT_CARD_REQUEST: [_A.CHAT_IMPERSONATION],
    _C.GOV_AGENCY: [_A.VISHING, _A.PHISHING_EMAIL, _A.SMISHING],
    _C.DELIVERY_FEE: [_A.SMISHING, _A.PHISHING_EMAIL],
    _C.RECRUITER_PARTNER: [_A.CHAT_IMPERSONATION, _A.PHISHING_EMAIL],
    _C.CLOUD_DOCUMENT: [_A.PHISHING_EMAIL, _A.CHAT_IMPERSONATION],
    _C.PHYSICAL_ACCESS: [_A.TAILGATING, _A.QUID_PRO_QUO],
    _C.BAITING_DEVICE: [_A.BAITING, _A.QUISHING],
    _C.SURVEY_REWARD: [_A.QUID_PRO_QUO, _A.PHISHING_EMAIL, _A.SMISHING],
    _C.COLLEAGUE_SUPPORT: [_A.CHAT_IMPERSONATION, _A.PHISHING_EMAIL],
    _C.EMPLOYEE_BENEFITS: [_A.PHISHING_EMAIL, _A.CHAT_IMPERSONATION, _A.SMISHING],
    _C.INTERNAL_RESALE: [_A.CHAT_IMPERSONATION, _A.PHISHING_EMAIL],
}

_MAIN_GROUPS = [ScenarioGroup.LEADER, ScenarioGroup.IT, ScenarioGroup.BANK]
_COMPETENCY_GROUPS: dict[CompetencyGroup, list[ScenarioGroup]] = {
    CompetencyGroup.SIGN_RECOGNITION: _MAIN_GROUPS,
    CompetencyGroup.MANIPULATION_RECOGNITION: _MAIN_GROUPS,
    CompetencyGroup.RESPONSE_BEHAVIOR: [*_MAIN_GROUPS, ScenarioGroup.OTHER],
    CompetencyGroup.PRINCIPLE_APPLICATION: [*_MAIN_GROUPS, ScenarioGroup.OTHER],
}


def allowed_groups(competency: CompetencyGroup) -> list[ScenarioGroup]:
    """Nhóm kịch bản hợp lệ cho một nhóm năng lực."""
    return list(_COMPETENCY_GROUPS[competency])


def allowed_contexts(group: ScenarioGroup) -> list[BusinessContext]:
    """Bối cảnh hợp lệ cho một nhóm kịch bản (đúng thứ tự khai báo ở trên)."""
    return list(_GROUP_CONTEXTS[group])


def allowed_attacks(context: BusinessContext) -> list[AttackType]:
    """Loại tấn công (kênh/kỹ thuật) hợp lệ cho một bối cảnh."""
    return list(_CONTEXT_ATTACKS[context])


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
    scenario_group: ScenarioGroup
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
    scenario_group: str,
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
    group_e = _coerce_enum(ScenarioGroup, scenario_group, "scenario_group")
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

    # Chuỗi phụ thuộc — chỉ báo lỗi ở mắt xích đầu tiên bị sai để tránh lỗi dây chuyền gây nhiễu.
    if competency_e is not None and group_e is not None and group_e not in allowed_groups(competency_e):
        ok = ", ".join(g.value for g in allowed_groups(competency_e))
        errors.append(f"scenario_group='{group_e.value}' không phù hợp với competency_group="
                      f"'{competency_e.value}'. Nhóm kịch bản hợp lệ: {ok}")
    elif group_e is not None and business_context_e is not None and business_context_e not in allowed_contexts(group_e):
        ok = ", ".join(c.value for c in allowed_contexts(group_e))
        errors.append(f"business_context='{business_context_e.value}' không thuộc scenario_group="
                      f"'{group_e.value}'. Bối cảnh hợp lệ: {ok}")
    elif business_context_e is not None and attack_type_e is not None and attack_type_e not in allowed_attacks(business_context_e):
        ok = ", ".join(a.value for a in allowed_attacks(business_context_e))
        errors.append(f"attack_type='{attack_type_e.value}' không phù hợp với business_context="
                      f"'{business_context_e.value}'. Loại tấn công hợp lệ: {ok}")

    if errors:
        raise SchemaValidationError("; ".join(errors))

    return ScenarioParams(
        attack_type=attack_type_e,
        learner_role=learner_role_e,
        business_context=business_context_e,
        manipulation_mechanism=manipulation_e,
        difficulty_level=difficulty_e,
        competency_group=competency_e,
        scenario_group=group_e,
        red_flags_required=red_flags_required,
        language=language,
        output_format=output_format_e,
        requester_note=requester_note,
    )

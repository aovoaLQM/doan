"""
run_cli.py
-----------
Chạy pipeline [1]->[4] với tham số CHỌN QUA MENU thay vì hardcode trong code.

Cách dùng:
    python run_cli.py
Sau đó làm theo hướng dẫn trên màn hình để chọn attack_type, learner_role, v.v.
"""

from __future__ import annotations

import json
from enum import Enum

from schema_builder import (
    AttackType,
    LearnerRole,
    BusinessContext,
    ManipulationMechanism,
    DifficultyLevel,
    _RED_FLAG_BOUNDS,
)
from pipeline import run_pipeline


# Nhãn tiếng Việt dễ đọc cho từng giá trị enum, hiển thị trên menu
_LABELS: dict[type[Enum], dict[str, str]] = {
    AttackType: {
        "phishing_email": "Phishing qua email",
        "vishing": "Vishing (lừa đảo qua điện thoại)",
        "smishing": "Smishing (lừa đảo qua SMS)",
        "bec": "BEC (Business Email Compromise - giả mạo email lãnh đạo)",
        "pretexting": "Pretexting (giả danh/dựng kịch bản)",
        "tailgating": "Tailgating (bám đuôi ra vào trụ sở)",
        "quid_pro_quo": "Quid pro quo (đổi chác lợi ích)",
    },
    LearnerRole: {
        "nhan_vien_ke_toan": "Nhân viên kế toán",
        "it_helpdesk": "IT Helpdesk",
        "quan_ly_cap_trung": "Quản lý cấp trung",
        "le_tan": "Lễ tân",
        "nhan_vien_moi": "Nhân viên mới",
        "nhan_vien_hr": "Nhân viên HR",
    },
    BusinessContext: {
        "chuyen_khoan_khan": "Chuyển khoản khẩn",
        "reset_mat_khau": "Reset mật khẩu",
        "ky_hop_dong": "Ký hợp đồng",
        "xu_ly_hoa_don": "Xử lý hóa đơn",
        "tuyen_dung": "Tuyển dụng",
        "onboard_nha_cung_cap": "Onboard nhà cung cấp",
    },
    ManipulationMechanism: {
        "authority": "Authority (quyền lực/chức vụ)",
        "urgency": "Urgency (khẩn cấp)",
        "scarcity": "Scarcity (khan hiếm)",
        "social_proof": "Social proof (số đông/uy tín xã hội)",
        "familiarity_liking": "Familiarity/Liking (quen thuộc/thiện cảm)",
        "fear_intimidation": "Fear/Intimidation (sợ hãi/đe dọa)",
    },
    DifficultyLevel: {
        "beginner": "Beginner (cơ bản)",
        "intermediate": "Intermediate (trung bình)",
        "advanced": "Advanced (nâng cao)",
    },
}


def choose_enum(enum_cls: type[Enum], prompt: str) -> str:
    """Hiển thị menu số cho một enum, trả về .value của lựa chọn."""
    options = list(enum_cls)
    labels = _LABELS.get(enum_cls, {})

    print(f"\n{prompt}")
    for idx, opt in enumerate(options, start=1):
        label = labels.get(opt.value, opt.value)
        print(f"  {idx}. {label}")

    while True:
        raw = input(f"Chọn số (1-{len(options)}): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1].value
        print("Lựa chọn không hợp lệ, thử lại.")


def choose_red_flags(difficulty: str) -> int:
    lo, hi = _RED_FLAG_BOUNDS[DifficultyLevel(difficulty)]
    while True:
        raw = input(f"\nSố lượng red flags ({lo}-{hi} cho độ khó '{difficulty}'): ").strip()
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"Giá trị phải là số nguyên trong khoảng {lo}-{hi}.")


def main() -> None:
    print("=== Tạo kịch bản đào tạo nhận diện Social Engineering ===")

    attack_type = choose_enum(AttackType, "Chọn loại tấn công (attack_type):")
    learner_role = choose_enum(LearnerRole, "Chọn vai trò người học (learner_role):")
    business_context = choose_enum(BusinessContext, "Chọn bối cảnh nghiệp vụ (business_context):")
    manipulation_mechanism = choose_enum(ManipulationMechanism, "Chọn cơ chế thao túng tâm lý (manipulation_mechanism):")
    difficulty_level = choose_enum(DifficultyLevel, "Chọn cấp độ khó (difficulty_level):")
    red_flags_required = choose_red_flags(difficulty_level)

    print("\nĐang gọi LLM để sinh kịch bản, vui lòng đợi...\n")

    outcome = run_pipeline(
        attack_type=attack_type,
        learner_role=learner_role,
        business_context=business_context,
        manipulation_mechanism=manipulation_mechanism,
        difficulty_level=difficulty_level,
        red_flags_required=red_flags_required,
    )

    print(json.dumps(outcome.to_review_payload(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
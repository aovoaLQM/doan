"""
[4] Output validator
---------------------
Kiểm tra schema (bao gồm trường "tier" mới của red_flags) + content safety
filter (quét đệ quy toàn bộ chuỗi text trong JSON lồng nhau).
Thiết kế fail-closed: bất kỳ lỗi nào => is_valid=False.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from schema_builder import ScenarioParams

ALLOWED_CHANNELS = {"email", "phone_call", "sms", "in_person", "chat"}
MIN_OPTIONS = 3
MAX_OPTIONS = 4
ALLOWED_RED_FLAG_TIERS = {"co_ban", "trung_binh", "nang_cao"}

_REAL_BRAND_DOMAIN_PATTERNS = [
    r"\bgoogle\.com\b", r"\bmicrosoft\.com\b", r"\bpaypal\.com\b",
    r"\bfacebook\.com\b", r"\bvietcombank\.com\.vn\b", r"\btechcombank\.com\.vn\b",
    r"\bmbbank\.com\.vn\b", r"\bvnpay\.vn\b", r"\bmomo\.vn\b",
    r"\bgmail\.com\b", r"\boutlook\.com\b", r"\banydesk\.com\b", r"\bteamviewer\.com\b",
]

_PII_LOOKALIKE_PATTERNS = [
    r"\b0\d{9}\b",
    r"\b\d{12}\b",
    r"\b(?:\d{4}[ -]?){4}\b",
    r"\b\d{13,16}\b",
]

_ALLOWED_FAKE_DOMAIN_HINT = re.compile(r"gia-?lap|gia-?dinh|example\.(com|vn)|fake|demo", re.IGNORECASE)

_REAL_ATTACK_INSTRUCTION_MARKERS = [
    r"chạy lệnh sau để chiếm quyền",
    r"tải (?:file|payload) sau về máy nạn nhân",
    r"đây là (?:mã|code) (?:khai thác|exploit)",
    r"bypass (?:2fa|mfa|xác thực hai lớp) bằng cách",
    r"keylogger",
    r"reverse shell",
    r"tải (?:anydesk|teamviewer|ultraviewer) tại (?:http|www)",  # link tải thật cho remote-access tool
]


@dataclass
class ValidationIssue:
    severity: str
    field: str
    message: str


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    normalized_output: dict[str, Any] | None = None

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def _err(issues, path, msg):
    issues.append(ValidationIssue("error", path, msg))


def _warn(issues, path, msg):
    issues.append(ValidationIssue("warning", path, msg))


def _validate_schema(data: dict, params: ScenarioParams) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if data.get("refusal") is True:
        _err(issues, "refusal", f"LLM đã từ chối sinh nội dung: {data.get('reason', '(không có lý do)')}")
        return issues

    top_required = {
        "scenario_id": str, "title": str, "channel": str, "difficulty_level": str,
        "layer1_challenge": dict, "layer2_explanation": dict,
        "layer3_transferable_knowledge": dict, "learning_objective": str,
    }
    for f, t in top_required.items():
        if f not in data:
            _err(issues, f, "Thiếu trường bắt buộc")
        elif not isinstance(data[f], t):
            _err(issues, f, f"Kiểu dữ liệu sai: cần {t.__name__}, nhận {type(data[f]).__name__}")

    if data.get("channel") not in ALLOWED_CHANNELS:
        _warn(issues, "channel", f"channel='{data.get('channel')}' không nằm trong {ALLOWED_CHANNELS}")

    # --- Layer 1 ---
    l1 = data.get("layer1_challenge")
    option_ids: list[str] = []
    if isinstance(l1, dict):
        for f in ("narrative", "decision_prompt"):
            if not isinstance(l1.get(f), str) or not l1.get(f, "").strip():
                _err(issues, f"layer1_challenge.{f}", "Thiếu hoặc rỗng")

        options = l1.get("options")
        if not isinstance(options, list):
            _err(issues, "layer1_challenge.options", "Thiếu hoặc không phải danh sách")
        else:
            if not (MIN_OPTIONS <= len(options) <= MAX_OPTIONS):
                _err(issues, "layer1_challenge.options",
                     f"Số lượng options={len(options)}, yêu cầu {MIN_OPTIONS}-{MAX_OPTIONS}")
            safe_count = 0
            for idx, opt in enumerate(options):
                path = f"layer1_challenge.options[{idx}]"
                if not isinstance(opt, dict):
                    _err(issues, path, "Mỗi option phải là object")
                    continue
                for f, t in (("option_id", str), ("text", str), ("is_safe_choice", bool), ("score", (int, float))):
                    if f not in opt:
                        _err(issues, f"{path}.{f}", "Thiếu trường")
                    elif not isinstance(opt[f], t):
                        _err(issues, f"{path}.{f}", f"Kiểu dữ liệu sai, nhận {type(opt.get(f)).__name__}")
                if isinstance(opt.get("option_id"), str):
                    option_ids.append(opt["option_id"])
                if opt.get("is_safe_choice") is True:
                    safe_count += 1
                    if opt.get("score") != 100:
                        _warn(issues, f"{path}.score", "Lựa chọn an toàn nhất nên có score=100")
                score = opt.get("score")
                if isinstance(score, (int, float)) and not (0 <= score <= 100):
                    _err(issues, f"{path}.score", f"score={score} phải trong khoảng 0-100")

            if safe_count != 1:
                _err(issues, "layer1_challenge.options",
                     f"Phải có ĐÚNG 1 lựa chọn is_safe_choice=true, hiện có {safe_count}")
            if len(set(option_ids)) != len(option_ids):
                _err(issues, "layer1_challenge.options", "option_id bị trùng lặp")

    # --- Layer 2 ---
    l2 = data.get("layer2_explanation")
    if isinstance(l2, dict):
        feedback = l2.get("option_feedback")
        if not isinstance(feedback, list):
            _err(issues, "layer2_explanation.option_feedback", "Thiếu hoặc không phải danh sách")
        else:
            feedback_ids = set()
            for idx, fb in enumerate(feedback):
                path = f"layer2_explanation.option_feedback[{idx}]"
                if not isinstance(fb, dict) or "option_id" not in fb or "explanation" not in fb:
                    _err(issues, path, "Cần có 'option_id' và 'explanation'")
                else:
                    feedback_ids.add(fb["option_id"])
            if option_ids and feedback_ids != set(option_ids):
                _err(issues, "layer2_explanation.option_feedback",
                     f"option_id không khớp Layer 1: thiếu {set(option_ids) - feedback_ids}, "
                     f"thừa {feedback_ids - set(option_ids)}")

        red_flags = l2.get("red_flags")
        if not isinstance(red_flags, list):
            _err(issues, "layer2_explanation.red_flags", "Thiếu hoặc không phải danh sách")
        else:
            if len(red_flags) != params.red_flags_required:
                _err(issues, "layer2_explanation.red_flags",
                     f"Số lượng={len(red_flags)}, yêu cầu đúng {params.red_flags_required}")
            has_advanced_tier = False
            for idx, rf in enumerate(red_flags):
                path = f"layer2_explanation.red_flags[{idx}]"
                if not isinstance(rf, dict) or "flag" not in rf or "explanation" not in rf:
                    _err(issues, path, "Cần có 'flag' và 'explanation'")
                    continue
                tier = rf.get("tier")
                if tier is None:
                    _err(issues, f"{path}.tier", "Thiếu trường 'tier'")
                elif tier not in ALLOWED_RED_FLAG_TIERS:
                    _err(issues, f"{path}.tier",
                         f"tier='{tier}' không hợp lệ. Cho phép: {ALLOWED_RED_FLAG_TIERS}")
                elif tier == "nang_cao":
                    has_advanced_tier = True

            if params.difficulty_level.value == "advanced" and not has_advanced_tier:
                _warn(issues, "layer2_explanation.red_flags",
                      "difficulty_level=advanced nhưng không có red flag nào tier='nang_cao'")

    # --- Layer 3 ---
    l3 = data.get("layer3_transferable_knowledge")
    if isinstance(l3, dict):
        for f in ("principle", "general_advice"):
            if not isinstance(l3.get(f), str) or not l3.get(f, "").strip():
                _err(issues, f"layer3_transferable_knowledge.{f}", "Thiếu hoặc rỗng")
        situations = l3.get("applicable_situations")
        if not isinstance(situations, list) or not (1 <= len(situations) <= 5):
            _err(issues, "layer3_transferable_knowledge.applicable_situations",
                 "Cần là danh sách 1-5 phần tử")

    return issues


def _collect_text_leaves(obj: Any, path: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((path or "root", obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_collect_text_leaves(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            out.extend(_collect_text_leaves(v, f"{path}[{idx}]"))
    return out


def _scan_content_safety(data: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for field_path, text in _collect_text_leaves(data):
        for pattern in _REAL_BRAND_DOMAIN_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                _err(issues, field_path,
                     f"Phát hiện domain/thương hiệu thật khớp mẫu '{pattern}'")

        for pattern in _PII_LOOKALIKE_PATTERNS:
            for match in re.finditer(pattern, text):
                snippet = text[max(0, match.start() - 15):match.end() + 15]
                if _ALLOWED_FAKE_DOMAIN_HINT.search(snippet):
                    continue
                _err(issues, field_path,
                     f"Phát hiện chuỗi trông giống PII/số tài khoản thật ('{match.group()}')")

        for marker in _REAL_ATTACK_INSTRUCTION_MARKERS:
            if re.search(marker, text, re.IGNORECASE):
                _err(issues, field_path, f"Phát hiện cụm từ mang tính hướng dẫn tấn công thật: '{marker}'")

    return issues


def validate_output(data: dict, params: ScenarioParams) -> ValidationResult:
    issues = _validate_schema(data, params)

    if not any(i.field == "refusal" for i in issues):
        issues += _scan_content_safety(data)

    has_error = any(i.severity == "error" for i in issues)

    return ValidationResult(
        is_valid=not has_error,
        issues=issues,
        normalized_output=data if not has_error else None,
    )


if __name__ == "__main__":
    from schema_builder import build_scenario_params

    params = build_scenario_params(
        attack_type="pretexting",
        learner_role="nhan_vien_van_phong",
        business_context="ho_tro_ky_thuat_tu_xa",
        manipulation_mechanism="fear_intimidation",
        difficulty_level="advanced",
        red_flags_required=2,
    )

    good_output = {
        "scenario_id": params.scenario_id,
        "title": "Cuộc gọi giả danh kỹ thuật viên IT",
        "channel": "phone_call",
        "difficulty_level": "advanced",
        "layer1_challenge": {
            "narrative": "Người gọi tự xưng kỹ thuật viên IT, yêu cầu cài phần mềm điều khiển từ xa...",
            "decision_prompt": "Bạn sẽ làm gì?",
            "options": [
                {"option_id": "A", "text": "Cài phần mềm theo hướng dẫn ngay", "is_safe_choice": False, "score": 0},
                {"option_id": "B", "text": "Cúp máy, gọi lại số Helpdesk chính thống để xác minh", "is_safe_choice": True, "score": 100},
                {"option_id": "C", "text": "Hỏi thêm thông tin qua điện thoại rồi mới quyết định", "is_safe_choice": False, "score": 40},
            ],
        },
        "layer2_explanation": {
            "option_feedback": [
                {"option_id": "A", "explanation": "Rủi ro cao nhất, mất quyền kiểm soát máy."},
                {"option_id": "B", "explanation": "Đúng quy trình xác minh qua kênh độc lập."},
                {"option_id": "C", "explanation": "Vẫn rủi ro vì tiếp tục trao đổi với người gọi khả nghi."},
            ],
            "red_flags": [
                {"flag": "Yêu cầu cài phần mềm điều khiển từ xa", "explanation": "Không theo quy trình ticket chính thức", "tier": "trung_binh"},
                {"flag": "Người gọi biết tên phòng ban nội bộ", "explanation": "Thông tin có thể bị rò rỉ, tạo lòng tin giả", "tier": "nang_cao"},
            ],
        },
        "layer3_transferable_knowledge": {
            "principle": "Không bao giờ cấp quyền điều khiển từ xa khi chưa xác minh qua kênh độc lập.",
            "applicable_situations": ["Yêu cầu qua email", "Yêu cầu qua tin nhắn nội bộ"],
            "general_advice": "Luôn gọi lại qua số đã biết trước khi hành động.",
        },
        "learning_objective": "Nhận diện pretexting giả danh IT và quy trình xác minh đúng",
        "refusal": False,
    }
    r1 = validate_output(good_output, params)
    print("Case 1 (clean, có tier nang_cao):", r1.is_valid, [(i.severity, i.field, i.message) for i in r1.issues])

    bad_output = dict(good_output)
    bad_output["layer2_explanation"] = {
        **good_output["layer2_explanation"],
        "red_flags": [
            {"flag": "A", "explanation": "B", "tier": "trung_binh"},
            {"flag": "C", "explanation": "D", "tier": "trung_binh"},
        ],
    }
    r2 = validate_output(bad_output, params)
    print("Case 2 (advanced nhưng thiếu tier nang_cao -> warning):",
          r2.is_valid, [(i.severity, i.field, i.message) for i in r2.issues])

    bad_output2 = dict(good_output)
    bad_output2["layer2_explanation"] = {
        **good_output["layer2_explanation"],
        "red_flags": [
            {"flag": "A", "explanation": "B", "tier": "khong_hop_le"},
            {"flag": "C", "explanation": "D", "tier": "nang_cao"},
        ],
    }
    r3 = validate_output(bad_output2, params)
    print("Case 3 (tier sai giá trị -> error):", r3.is_valid, [(i.severity, i.field, i.message) for i in r3.issues])
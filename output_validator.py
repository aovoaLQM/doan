"""[4] Output validator — schema check + content safety, quét đệ quy toàn JSON."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from schema_builder import ScenarioParams

ALLOWED_CHANNELS = {"email", "phone_call", "sms", "in_person", "chat"}
MIN_OPTIONS = 3
MAX_OPTIONS = 4
ALLOWED_RED_FLAG_TIERS = {"co_ban", "trung_binh", "nang_cao"}
ALLOWED_COMPETENCIES = {
    "nhan_dien_dau_hieu",
    "nhan_biet_co_che_thao_tung",
    "lua_chon_hanh_vi_ung_pho",
    "van_dung_nguyen_tac",
}
ALLOWED_DISTRACTOR_TYPES = {"phan_ung_theo_ap_luc", "xac_minh_sai_kenh", "xu_ly_thu_dong", "khong_ap_dung"}

_REAL_BRAND_DOMAIN_PATTERNS = [
    r"\bgoogle\.com\b", r"\bmicrosoft\.com\b", r"\bpaypal\.com\b",
    r"\bfacebook\.com\b", r"\bvietcombank\.com\.vn\b", r"\btechcombank\.com\.vn\b",
    r"\bmbbank\.com\.vn\b", r"\bvnpay\.vn\b", r"\bmomo\.vn\b",
    r"\bgmail\.com\b", r"\boutlook\.com\b", r"\banydesk\.com\b", r"\bteamviewer\.com\b",
]
_PII_LOOKALIKE_PATTERNS = [
    r"\b0\d{9}\b", r"\b\d{12}\b", r"\b(?:\d{4}[ -]?){4}\b", r"\b\d{13,16}\b",
]
_ALLOWED_FAKE_DOMAIN_HINT = re.compile(r"gia-?lap|gia-?dinh|example\.(com|vn)|fake|demo", re.IGNORECASE)


def _is_obviously_placeholder_number(digits: str) -> bool:
    """True nếu là dãy số tăng dần/giảm dần liên tục hoặc lặp lại 1 chữ số duy nhất
    (vd 0123456789, 9876543210, 0000000000) — các mẫu placeholder điển hình mà LLM
    hay dùng để sinh số tài khoản/điện thoại giả, không bao giờ là số thật ngoài đời
    nên loại trừ an toàn khỏi bộ lọc PII mà không làm giảm khả năng bắt PII thật khác."""
    if len(digits) < 4:
        return False
    if len(set(digits)) == 1:
        return True
    ascending = all(int(digits[i + 1]) == (int(digits[i]) + 1) % 10 for i in range(len(digits) - 1))
    descending = all(int(digits[i + 1]) == (int(digits[i]) - 1) % 10 for i in range(len(digits) - 1))
    return ascending or descending
_REAL_ATTACK_INSTRUCTION_MARKERS = [
    r"chạy lệnh sau để chiếm quyền",
    r"tải (?:file|payload) sau về máy nạn nhân",
    r"đây là (?:mã|code) (?:khai thác|exploit)",
    r"bypass (?:2fa|mfa|xác thực hai lớp) bằng cách",
    r"keylogger",
    r"reverse shell",
    r"tải (?:anydesk|teamviewer|ultraviewer) tại (?:http|www)",
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
        "primary_competency": str,
        "layer1_challenge": dict, "layer2_explanation": dict,
        "layer3_transferable_knowledge": dict, "learning_objective": str,
    }
    for f, t in top_required.items():
        if f not in data:
            _err(issues, f, "Thiếu trường bắt buộc")
        elif not isinstance(data[f], t):
            _err(issues, f, f"Kiểu dữ liệu sai: cần {t.__name__}")

    if isinstance(data.get("channel"), str):
        data["channel"] = data["channel"].strip().lower()
    if data.get("channel") not in ALLOWED_CHANNELS:
        _warn(issues, "channel", f"channel không nằm trong {ALLOWED_CHANNELS}")

    if data.get("primary_competency") != params.competency_group.value:
        _err(issues, "primary_competency",
             f"Phải khớp đúng competency_group đã yêu cầu ('{params.competency_group.value}'), "
             f"nhận '{data.get('primary_competency')}'")

    l1 = data.get("layer1_challenge")
    option_ids: list[str] = []
    if isinstance(l1, dict):
        for f in ("narrative", "decision_prompt"):
            if not isinstance(l1.get(f), str) or not l1.get(f, "").strip():
                _err(issues, f"layer1_challenge.{f}", "Thiếu hoặc rỗng")

        # Kiểm tra heuristic: decision_prompt có đúng "chất giọng" của nhóm năng lực không.
        # Đây chỉ là cảnh báo (không chặn cứng) vì có thể có cách diễn đạt hợp lệ khác.
        dp = l1.get("decision_prompt", "") if isinstance(l1.get("decision_prompt"), str) else ""
        dp_lower = dp.lower()
        _EXPECTED_KEYWORDS = {
            "nhan_dien_dau_hieu": ["dấu hiệu"],
            "nhan_biet_co_che_thao_tung": ["cơ chế"],
            "van_dung_nguyen_tac": ["nguyên tắc"],
        }
        expected = _EXPECTED_KEYWORDS.get(params.competency_group.value)
        if expected and dp and not any(kw in dp_lower for kw in expected):
            _warn(issues, "layer1_challenge.decision_prompt",
                  f"Nhóm '{params.competency_group.value}' nên hỏi về {expected[0]}, nhưng "
                  f"decision_prompt không chứa từ khóa này — có thể LLM đã lệch sang dạng câu hỏi hành vi")
        if params.competency_group.value != "lua_chon_hanh_vi_ung_pho" and "làm gì" in dp_lower:
            _warn(issues, "layer1_challenge.decision_prompt",
                  "decision_prompt có vẻ đang hỏi HÀNH ĐỘNG ('làm gì') dù nhóm năng lực này không "
                  "phải Phần III — kiểm tra lại xem LLM có lệch format không")

        options = l1.get("options")
        if not isinstance(options, list):
            _err(issues, "layer1_challenge.options", "Thiếu hoặc không phải danh sách")
        else:
            if not (MIN_OPTIONS <= len(options) <= MAX_OPTIONS):
                _err(issues, "layer1_challenge.options",
                     f"Số lượng options={len(options)}, yêu cầu {MIN_OPTIONS}-{MAX_OPTIONS}")
            safe_count = 0
            distractor_types_seen = set()
            for idx, opt in enumerate(options):
                path = f"layer1_challenge.options[{idx}]"
                if not isinstance(opt, dict):
                    _err(issues, path, "Mỗi option phải là object")
                    continue
                for f, t in (("option_id", str), ("text", str), ("is_safe_choice", bool), ("score", (int, float))):
                    if f not in opt:
                        _err(issues, f"{path}.{f}", "Thiếu trường")
                    elif not isinstance(opt[f], t):
                        _err(issues, f"{path}.{f}", "Kiểu dữ liệu sai")
                if isinstance(opt.get("option_id"), str):
                    option_ids.append(opt["option_id"])
                if opt.get("is_safe_choice") is True:
                    safe_count += 1
                    if opt.get("score") != 100:
                        _warn(issues, f"{path}.score", "Lựa chọn an toàn nhất nên có score=100")
                score = opt.get("score")
                if isinstance(score, (int, float)) and not (0 <= score <= 100):
                    _err(issues, f"{path}.score", f"score={score} phải trong 0-100")

                dtype = opt.get("distractor_type")
                # distractor_type (3 loại nhiễu hành vi) chỉ có nghĩa ở Phần III. Ở các nhóm còn lại
                # giá trị này vô nghĩa nên tự chuẩn hóa về "khong_ap_dung" (kèm cảnh báo mềm),
                # thay vì chặn cứng cả bài vì một trường không ảnh hưởng nội dung/an toàn.
                if params.competency_group.value != "lua_chon_hanh_vi_ung_pho":
                    if dtype not in (None, "khong_ap_dung"):
                        _warn(issues, f"{path}.distractor_type",
                              f"Đã tự chuẩn hóa '{dtype}' -> 'khong_ap_dung' (nhóm năng lực này không dùng loại nhiễu hành vi)")
                    opt["distractor_type"] = "khong_ap_dung"
                    continue
                if dtype is None:
                    _warn(issues, f"{path}.distractor_type", "Thiếu trường distractor_type")
                elif dtype not in ALLOWED_DISTRACTOR_TYPES:
                    _err(issues, f"{path}.distractor_type",
                         f"Giá trị '{dtype}' không hợp lệ. Cho phép: {ALLOWED_DISTRACTOR_TYPES}")
                elif dtype != "khong_ap_dung":
                    distractor_types_seen.add(dtype)

            if safe_count != 1:
                _err(issues, "layer1_challenge.options",
                     f"Phải có ĐÚNG 1 lựa chọn is_safe_choice=true, hiện có {safe_count}")
            if len(set(option_ids)) != len(option_ids):
                _err(issues, "layer1_challenge.options", "option_id bị trùng lặp")
            # Ràng buộc 3-loại-nhiễu-hành-vi CHỈ áp dụng cho Phần III/IV (câu hỏi hành vi ứng phó).
            # Phần I/II là câu hỏi nhận diện/kiến thức nên distractor_type="khong_ap_dung" là ĐÚNG,
            # không phải thiếu đa dạng.
            # Chỉ Phần III dùng 3 loại nhiễu hành vi; Phần IV giờ dùng format phát biểu nguyên
            # tắc riêng (xem prompt_constructor.py), không còn áp dụng ràng buộc này.
            behavior_groups = {"lua_chon_hanh_vi_ung_pho"}
            if params.competency_group.value in behavior_groups and len(options) >= 3 and len(distractor_types_seen) < 2:
                _warn(issues, "layer1_challenge.options",
                      "Nên dùng ít nhất 2 loại distractor khác nhau trong 3 loại chuẩn "
                      "(phan_ung_theo_ap_luc / xac_minh_sai_kenh / xu_ly_thu_dong)")

    l2 = data.get("layer2_explanation")
    if isinstance(l2, dict):
        feedback = l2.get("option_feedback")
        if not isinstance(feedback, list):
            _err(issues, "layer2_explanation.option_feedback", "Thiếu hoặc không phải danh sách")
        else:
            feedback_ids = {fb.get("option_id") for fb in feedback if isinstance(fb, dict)}
            for idx, fb in enumerate(feedback):
                if not isinstance(fb, dict) or "option_id" not in fb or "explanation" not in fb:
                    _err(issues, f"layer2_explanation.option_feedback[{idx}]",
                         "Cần có 'option_id' và 'explanation'")
            if option_ids and feedback_ids != set(option_ids):
                _err(issues, "layer2_explanation.option_feedback",
                     f"option_id không khớp Layer 1: thiếu {set(option_ids) - feedback_ids}")

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
                    _err(issues, f"{path}.tier", f"tier='{tier}' không hợp lệ")
                elif tier == "nang_cao":
                    has_advanced_tier = True
            if params.difficulty_level.value == "advanced" and not has_advanced_tier:
                _warn(issues, "layer2_explanation.red_flags",
                      "difficulty_level=advanced nhưng không có red flag tier='nang_cao'")

    l3 = data.get("layer3_transferable_knowledge")
    if isinstance(l3, dict):
        for f in ("principle", "general_advice"):
            if not isinstance(l3.get(f), str) or not l3.get(f, "").strip():
                _err(issues, f"layer3_transferable_knowledge.{f}", "Thiếu hoặc rỗng")
        situations = l3.get("applicable_situations")
        if not isinstance(situations, list) or not (1 <= len(situations) <= 5):
            _err(issues, "layer3_transferable_knowledge.applicable_situations", "Cần là danh sách 1-5 phần tử")

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
                _err(issues, field_path, f"Phát hiện domain/thương hiệu thật khớp mẫu '{pattern}'")
        for pattern in _PII_LOOKALIKE_PATTERNS:
            for match in re.finditer(pattern, text):
                digits_only = re.sub(r"\D", "", match.group())
                if _is_obviously_placeholder_number(digits_only):
                    continue
                snippet = text[max(0, match.start() - 15):match.end() + 15]
                if _ALLOWED_FAKE_DOMAIN_HINT.search(snippet):
                    continue
                _err(issues, field_path, f"Phát hiện chuỗi trông giống PII/số tài khoản thật ('{match.group()}')")
        for marker in _REAL_ATTACK_INSTRUCTION_MARKERS:
            if re.search(marker, text, re.IGNORECASE):
                _err(issues, field_path, f"Phát hiện cụm từ hướng dẫn tấn công thật: '{marker}'")
    return issues


def validate_output(data: dict, params: ScenarioParams) -> ValidationResult:
    issues = _validate_schema(data, params)
    if not any(i.field == "refusal" for i in issues):
        issues += _scan_content_safety(data)
    has_error = any(i.severity == "error" for i in issues)
    return ValidationResult(is_valid=not has_error, issues=issues, normalized_output=data if not has_error else None)
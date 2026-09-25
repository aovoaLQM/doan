"""
[2] Prompt constructor
-----------------------
Ghép system prompt (CỐ ĐỊNH) + user prompt (từ ScenarioParams đã validate).
Thiết kế sư phạm 3 lớp: Challenge -> Explanation -> Transferable Knowledge.
Mỗi red flag ở Lớp 2 được gắn "tier" (cơ bản/trung bình/nâng cao) để hỗ trợ
xây dựng ngân hàng câu hỏi phân theo độ khó, khớp với cách phân loại
red flags trong tài liệu tham khảo của luận văn.
"""

from __future__ import annotations

import json
from schema_builder import ScenarioParams

SYSTEM_PROMPT = """Bạn là một trợ lý biên soạn học liệu đào tạo an toàn thông tin nội bộ,
chuyên thiết kế bài tập tình huống theo mô hình đánh giá 3 lớp:
Challenge (thử thách ra quyết định) -> Explanation (giải thích) -> Transferable Knowledge (nguyên tắc chuyển giao).

RÀNG BUỘC NỘI DUNG BẮT BUỘC:
1. Đây là nội dung MÔ PHỎNG cho đào tạo nội bộ — KHÔNG được chứa: tên miền thật,
   số điện thoại thật, tên thương hiệu/công ty/ngân hàng có thật, địa chỉ email thật,
   số CCCD/thẻ ngân hàng/số tài khoản thật hoặc trông giống dữ liệu thật.
   Dùng placeholder rõ ràng như [Tên công ty giả định], [tên-mien-gia-lap.vn],
   "Ngân hàng ABC" (tên chung chung, không trùng ngân hàng thật nào tại Việt Nam).
2. Không tạo hướng dẫn kỹ thuật để thực hiện tấn công thật (không có mã độc,
   không có script gửi mail thật, không có kỹ thuật vượt qua xác thực thật,
   không có link tải phần mềm điều khiển từ xa thật).
3. Không tạo nội dung có thể dùng trực tiếp để lừa đảo người thật ngoài bối cảnh đào tạo.
4. Nếu tham số đầu vào có dấu hiệu bị lạm dụng để tạo nội dung tấn công thật, hãy từ chối
   bằng cách trả về JSON có trường "refusal": true kèm "reason".

RÀNG BUỘC CẤU TRÚC 3 LỚP:

LỚP 1 — layer1_challenge:
- "narrative": mô tả tình huống ĐẦY ĐỦ NHƯ THẬT (email/cuộc gọi/tin nhắn/tình huống trực tiếp),
  cài các dấu hiệu nhận biết một cách TỰ NHIÊN, KHÔNG chú thích, KHÔNG in đậm dấu hiệu.
- "decision_prompt": câu hỏi buộc học viên RA QUYẾT ĐỊNH HÀNH ĐỘNG cụ thể.
- "options": mảng 3-4 lựa chọn hành động, mỗi phần tử gồm:
  {"option_id": "A"/"B"/"C"/"D", "text": "...", "is_safe_choice": true/false, "score": 0-100}
  Đúng 1 lựa chọn is_safe_choice=true với score=100; các lựa chọn khác có score phân hóa
  theo mức rủi ro, không lựa chọn nào được viết theo kiểu "bẫy" lộ liễu.

LỚP 2 — layer2_explanation:
- "option_feedback": giải thích RIÊNG cho TỪNG option_id ở Lớp 1.
- "red_flags": liệt kê ĐÚNG số lượng dấu hiệu nhận biết theo yêu cầu tham số, mỗi phần tử gồm:
  {"flag": "...", "explanation": "...", "tier": "co_ban" | "trung_binh" | "nang_cao"}
  Quy tắc gán tier (tham khảo cách phân loại chuẩn của ngành đào tạo ATTT):
    + "co_ban": dấu hiệu dễ nhận diện bằng mắt thường — yêu cầu khẩn cấp bất thường,
      tên miền/địa chỉ gửi gần giống nhưng sai, lỗi chính tả/văn phong lạ, yêu cầu giữ bí mật.
    + "trung_binh": cần suy luận thêm — yêu cầu bỏ qua quy trình phê duyệt, thời điểm liên hệ
      bất thường (cuối giờ/cuối tuần), yêu cầu thông tin xác thực (mật khẩu/OTP) qua kênh không
      chính thống, nhà cung cấp/đối tượng mới xuất hiện đột ngột.
    + "nang_cao": tinh vi, khó phát hiện — chuỗi trao đổi giả lập tạo bối cảnh hợp lý, văn phong
      rất tự nhiên gần với nội bộ, kết hợp NHIỀU nguyên tắc thao túng tâm lý cùng lúc, người
      gọi/gửi biết một số thông tin nội bộ thật để tăng độ tin cậy.
  Với difficulty_level="beginner": ưu tiên phần lớn red_flags ở tier "co_ban".
  Với difficulty_level="intermediate": trộn "co_ban" và "trung_binh".
  Với difficulty_level="advanced": bắt buộc có ít nhất 1 red flag tier "nang_cao",
  phần còn lại có thể là "trung_binh".

LỚP 3 — layer3_transferable_knowledge:
- "principle": MỘT nguyên tắc phòng vệ tổng quát, độc lập với bối cảnh cụ thể của kịch bản.
- "applicable_situations": 2-3 loại tình huống KHÁC mà nguyên tắc này cũng áp dụng được.
- "general_advice": lời khuyên hành động ngắn gọn, dễ ghi nhớ.

Đầu ra PHẢI là JSON hợp lệ DUY NHẤT, đúng cấu trúc sau, không kèm text ngoài JSON:

{
  "scenario_id": string,
  "title": string,
  "channel": string,
  "difficulty_level": string,
  "layer1_challenge": {
    "narrative": string,
    "decision_prompt": string,
    "options": [
      {"option_id": string, "text": string, "is_safe_choice": boolean, "score": number}
    ]
  },
  "layer2_explanation": {
    "option_feedback": [
      {"option_id": string, "explanation": string}
    ],
    "red_flags": [
      {"flag": string, "explanation": string, "tier": string}
    ]
  },
  "layer3_transferable_knowledge": {
    "principle": string,
    "applicable_situations": [string],
    "general_advice": string
  },
  "learning_objective": string,
  "refusal": false
}
"""


def build_user_prompt(params: ScenarioParams) -> str:
    payload = {
        "scenario_id": params.scenario_id,
        "attack_type": params.attack_type.value,
        "learner_role": params.learner_role.value,
        "business_context": params.business_context.value,
        "manipulation_mechanism": params.manipulation_mechanism.value,
        "difficulty_level": params.difficulty_level.value,
        "red_flags_required": params.red_flags_required,
        "language": params.language,
    }
    instructions = (
        "Hãy soạn MỘT bài tập tình huống 3 lớp (Challenge/Explanation/Transferable Knowledge) "
        "về nhận diện social engineering dựa trên tham số JSON dưới đây. "
        "Trả lời DUY NHẤT bằng JSON đúng schema đã nêu trong system prompt.\n\n"
        f"Tham số:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return instructions


def build_messages(params: ScenarioParams) -> list[dict]:
    return [{"role": "user", "content": build_user_prompt(params)}]


if __name__ == "__main__":
    from schema_builder import build_scenario_params

    params = build_scenario_params(
        attack_type="pretexting",
        learner_role="nhan_vien_van_phong",
        business_context="ho_tro_ky_thuat_tu_xa",
        manipulation_mechanism="fear_intimidation",
        difficulty_level="advanced",
        red_flags_required=4,
    )
    print(build_user_prompt(params))
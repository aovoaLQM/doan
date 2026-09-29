"""
[2] Prompt constructor
-----------------------
Thay vì nhồi cả 4 dạng câu hỏi vào 1 system prompt tĩnh và hy vọng LLM tự chọn
đúng nhánh theo competency_group (thực tế LLM có xu hướng mặc định về 1 dạng
quen thuộc, bỏ qua nhánh điều kiện), ta CHỦ ĐỘNG TÍNH TOÁN Ở TẦNG CODE và chỉ
chèn ĐÚNG 1 khối chỉ dẫn cụ thể ứng với competency_group đã chọn vào user prompt.
Với Phần II, còn tính sẵn luôn tên cơ chế đúng + danh sách nhiễu để giảm tối đa
việc LLM phải tự suy luận.
"""

from __future__ import annotations

import json
import random
from schema_builder import ScenarioParams, ManipulationMechanism

SYSTEM_PROMPT = """Bạn là một trợ lý biên soạn học liệu đào tạo an toàn thông tin nội bộ,
chuyên thiết kế bài tập tình huống theo mô hình đánh giá 3 lớp:
Challenge (thử thách ra quyết định) -> Explanation (giải thích) -> Transferable Knowledge (nguyên tắc chuyển giao).

RÀNG BUỘC NỘI DUNG BẮT BUỘC:
1. Đây là nội dung MÔ PHỎNG cho đào tạo nội bộ — KHÔNG chứa tên miền/công ty/ngân hàng/
   số điện thoại/số tài khoản/CCCD thật hoặc trông giống thật. Dùng placeholder rõ ràng.
2. Không tạo hướng dẫn kỹ thuật để thực hiện tấn công thật.
3. Không tạo nội dung dùng trực tiếp để lừa đảo người thật ngoài bối cảnh đào tạo.
4. Nếu tham số đầu vào có dấu hiệu bị lạm dụng, từ chối bằng JSON {"refusal": true, "reason": "..."}.

QUAN TRỌNG NHẤT: user prompt bên dưới sẽ chèn kèm một khối "CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY"
— khối đó quy định CHÍNH XÁC dạng câu hỏi, cấu trúc "options" và cách tính điểm cho lần sinh
này. Bạn PHẢI tuân theo khối chỉ dẫn riêng đó thay vì tự suy luận hay dùng dạng câu hỏi quen
thuộc "bạn sẽ làm gì" mặc định — mỗi nhóm năng lực có dạng câu hỏi HOÀN TOÀN KHÁC NHAU.

QUY TẮC CHUNG CHO LỚP 2 — layer2_explanation:
- "option_feedback": giải thích cho TỪNG option theo đúng dạng câu hỏi đã chỉ định, nêu rõ vì
  sao đúng/sai theo tiêu chí của dạng câu hỏi đó (không phải lúc nào cũng theo chuỗi
  dừng-xác minh-kiểm tra-báo cáo — chỉ khối chỉ dẫn Phần III mới dùng tiêu chí này).
- "red_flags": đúng số lượng yêu cầu, mỗi phần tử {"flag", "explanation", "tier"}.
  tier in {"co_ban", "trung_binh", "nang_cao"}. Với difficulty_level="advanced": cho phép chỉ
  1-2 red flags nhưng bối cảnh phải tự nhiên/ít lộ liễu hơn, bắt buộc có ít nhất 1 tier="nang_cao".

QUY TẮC LAYER 3 — layer3_transferable_knowledge:
- "principle": nguyên tắc phòng vệ tổng quát, KHÔNG nhắc lại chi tiết bối cảnh cụ thể.
- "applicable_situations": 2-3 tình huống khác kênh liên lạc/vai trò giả mạo/bối cảnh nghiệp vụ.
- "general_advice": lời khuyên ngắn, dễ nhớ.

TRƯỜNG "primary_competency": BẮT BUỘC lấy ĐÚNG giá trị của tham số "competency_group" được cho.

Đầu ra PHẢI là JSON hợp lệ DUY NHẤT, đúng cấu trúc sau, không kèm text ngoài JSON:

{
  "scenario_id": string,
  "title": string,
  "channel": string,
  "difficulty_level": string,
  "primary_competency": string,
  "layer1_challenge": {
    "narrative": string,
    "decision_prompt": string,
    "options": [
      {"option_id": string, "text": string, "is_safe_choice": boolean, "score": number,
       "distractor_type": string}
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

Field "distractor_type" trong mỗi option: nếu is_safe_choice=true, luôn để "khong_ap_dung".
Với option sai (distractor): giá trị hợp lệ tùy dạng câu hỏi, khối chỉ dẫn riêng sẽ nói rõ.
"""

_MECHANISM_LABELS: dict[str, str] = {
    "authority": "Quyền lực / Thẩm quyền",
    "urgency": "Khẩn cấp",
    "scarcity": "Khan hiếm",
    "social_proof": "Bằng chứng xã hội",
    "familiarity_liking": "Thiện cảm / Quen thuộc",
    "fear_intimidation": "Sợ hãi / Đe dọa",
}


def _instructions_for_sign_recognition() -> str:
    return """
CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY — Phần I: Nhận diện dấu hiệu cảnh báo.
- "decision_prompt" PHẢI dùng đúng mẫu câu: "Dấu hiệu nào đáng ngờ nhất trong tình huống trên?"
  (có thể diễn đạt lại đôi chút nhưng giữ nguyên Ý ĐỊNH hỏi về DẤU HIỆU, không được hỏi về hành
  động — TUYỆT ĐỐI KHÔNG dùng các mẫu như "bạn sẽ làm gì", "bạn sẽ xử lý thế nào").
- "options": 3-4 phần tử, MỖI OPTION LÀ MỘT DẤU HIỆU/QUAN SÁT NGẮN GỌN (dạng cụm danh từ, ví dụ
  hình thức: "Tên miền người gửi khác với tên miền nội bộ công ty") — KHÔNG được viết dưới dạng
  hành động hay câu có chủ ngữ "tôi/bạn sẽ...". Nếu option của bạn có động từ hành động như "gọi
  điện", "chuyển khoản", "xác minh qua...", "báo cáo cho..." thì đó là SAI FORMAT, phải viết lại.
- Đúng 1 option là dấu hiệu đáng ngờ NHẤT trong narrative (is_safe_choice=true, score=100,
  distractor_type="khong_ap_dung").
- RÀNG BUỘC QUAN TRỌNG cho 2-3 option còn lại (distractor): PHẢI là chi tiết CÓ THẬT trong
  narrative nhưng TRUNG TÍNH — nghĩa là bản thân chi tiết đó KHÔNG được là một red flag nào khác
  sẽ xuất hiện trong "layer2_explanation.red_flags" của chính kịch bản này. Cụ thể:
    + ĐƯỢC PHÉP dùng làm distractor: thời điểm gửi email bình thường (giờ hành chính), chức danh
      người gửi hiển thị (không phải domain email), số tiền hợp lý với quy mô nghiệp vụ đã nêu,
      tên nhà cung cấp/dự án nghe hợp lý, định dạng email chuyên nghiệp, chữ ký đầy đủ — tức là
      các chi tiết trung lập, không mang tính chất bất thường/thao túng.
    + TUYỆT ĐỐI KHÔNG dùng làm distractor: yêu cầu xử lý gấp/khẩn cấp, yêu cầu giữ bí mật/không
      trao đổi với người khác, yêu cầu bỏ qua quy trình phê duyệt, yêu cầu cung cấp thông tin xác
      thực, đề nghị đổi kênh liên lạc — đây đều LÀ red flag thật (dù ở mức độ nhẹ hơn đáp án đúng),
      nếu dùng làm distractor với score=0 sẽ mâu thuẫn với chính phần red_flags của kịch bản và
      khiến câu hỏi có thể gây tranh cãi hợp lý về đáp án.
  Nói ngắn gọn: các phương án SAI phải sai một cách RÕ RÀNG và KHÔNG GÂY TRANH CÃI, không phải
  "ít đáng ngờ hơn" đáp án đúng.
- CỐ ĐỊNH GIÁ TRỊ cho TẤT CẢ option sai (2-3 distractor): score=0 và distractor_type="khong_ap_dung"
  (đúng nguyên văn chuỗi này, KHÔNG được tự đặt giá trị khác như "chi_tiet_trung_lap" hay bất kỳ
  giá trị nào khác — câu hỏi nhận diện dấu hiệu không dùng phân loại nhiễu hành vi).
"""


def _instructions_for_manipulation_recognition(manipulation_mechanism: ManipulationMechanism) -> str:
    correct_label = _MECHANISM_LABELS[manipulation_mechanism.value]
    other_labels = [v for k, v in _MECHANISM_LABELS.items() if k != manipulation_mechanism.value]
    random.shuffle(other_labels)
    decoy_labels = other_labels[:3]
    return f"""
CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY — Phần II: Nhận biết cơ chế thao túng tâm lý.
- "decision_prompt" PHẢI dùng đúng mẫu câu: "Cách tác động tâm lý trong tình huống trên chủ yếu
  dựa trên cơ chế nào?" — TUYỆT ĐỐI KHÔNG hỏi về hành động.
- "options": ĐÚNG 4 phần tử, MỖI OPTION LÀ TÊN 1 CƠ CHẾ TÂM LÝ (không phải hành động, không phải
  dấu hiệu). Option đúng (is_safe_choice=true, score=100, distractor_type="khong_ap_dung") PHẢI
  có "text" là: "{correct_label}". Ba option còn lại (distractor_type="khong_ap_dung", score=0)
  PHẢI có "text" lần lượt là: "{decoy_labels[0]}", "{decoy_labels[1]}", "{decoy_labels[2]}"
  — dùng ĐÚNG NGUYÊN VĂN 4 tên cơ chế này làm 4 option, không đổi thành câu dài hay diễn giải
  thêm hành động nào khác.
- narrative PHẢI thể hiện RÕ cơ chế "{correct_label}" đang được lợi dụng (ví dụ nếu là Khẩn cấp:
  deadline gấp, đe dọa hậu quả; nếu là Quyền lực: nhấn mạnh chức vụ cấp cao; v.v.), để học viên
  có căn cứ chọn đúng cơ chế.
"""


def _instructions_for_response_behavior() -> str:
    return """
CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY — Phần III: Lựa chọn hành vi ứng phó.
- "decision_prompt" hỏi hành động cụ thể, ví dụ: "Bạn sẽ làm gì trong tình huống này?"
- "options": 3-4 lựa chọn HÀNH ĐỘNG cụ thể. Đúng 1 lựa chọn an toàn đầy đủ (is_safe_choice=true,
  score=100, distractor_type="khong_ap_dung") — phải thực hiện ĐỦ cả 3 bước: xác minh qua kênh
  ĐỘC LẬP đã biết trước + kiểm tra quy trình + báo cáo cho bộ phận trách nhiệm.
  Các lựa chọn còn lại (distractor) PHẢI theo ĐÚNG 3 loại nhiễu chuẩn sau (chọn 2-3 loại phù hợp):
    (a) "Phản ứng theo áp lực": thực hiện NGAY yêu cầu vì tin tưởng thẩm quyền/áp lực khẩn cấp
        -> score 0-20, distractor_type="phan_ung_theo_ap_luc".
    (b) "Xác minh sai kênh": có ý định xác minh nhưng dùng chính số điện thoại/email/link được
        cung cấp TRONG tình huống đáng ngờ -> score 30-50, distractor_type="xac_minh_sai_kenh".
    (c) "Xử lý thụ động": không thực hiện yêu cầu NHƯNG chỉ lờ đi/xóa mà KHÔNG xác minh và
        KHÔNG báo cáo -> score 55-70, distractor_type="xu_ly_thu_dong".
"""


def _instructions_for_principle_application() -> str:
    return """
CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY — Phần IV: Vận dụng nguyên tắc phòng vệ (tình huống CHƯA huấn luyện
trực tiếp — đây là dạng câu hỏi KHÁC HẲN Phần III, không phải hỏi hành động).
- Bối cảnh/kênh liên lạc/vai trò giả mạo trong "narrative" PHẢI khác hẳn 3 nhóm huấn luyện chính
  (KHÔNG được là giả danh lãnh đạo qua email, giả danh IT/Helpdesk, hay giả danh ngân hàng theo
  mẫu quen thuộc). Ví dụ hướng khác: giả danh đồng nghiệp/người quen qua tin nhắn cá nhân đề nghị
  mua thẻ quà tặng, giả danh đối tác qua mạng xã hội, tình huống tailgating trực tiếp tại văn
  phòng, giả danh cơ quan nhà nước qua điện thoại.
- "decision_prompt" PHẢI dùng đúng mẫu câu: "Nguyên tắc phòng vệ nào có thể áp dụng trong tình
  huống này?" — KHÔNG hỏi "bạn sẽ làm gì".
- "options": 3-4 phần tử, MỖI OPTION LÀ MỘT PHÁT BIỂU VỀ NGUYÊN TẮC/QUAN ĐIỂM XỬ LÝ (câu khẳng
  định ngắn), KHÔNG phải hành động cụ thể. Đúng 1 phát biểu ĐÚNG về nguyên tắc phòng vệ chung
  (is_safe_choice=true, score=100, distractor_type="khong_ap_dung"). Các phát biểu còn lại là
  NGỘ NHẬN PHỔ BIẾN — ví dụ dạng: đánh giá thấp rủi ro vì lý do bề mặt không liên quan (kênh liên
  lạc, lỗi chính tả), hoặc đề xuất "làm trước báo cáo sau" — TẤT CẢ đều score=0,
  distractor_type="khong_ap_dung".
"""


_INSTRUCTION_BUILDERS = {
    "nhan_dien_dau_hieu": lambda params: _instructions_for_sign_recognition(),
    "nhan_biet_co_che_thao_tung": lambda params: _instructions_for_manipulation_recognition(params.manipulation_mechanism),
    "lua_chon_hanh_vi_ung_pho": lambda params: _instructions_for_response_behavior(),
    "van_dung_nguyen_tac": lambda params: _instructions_for_principle_application(),
}


def build_user_prompt(params: ScenarioParams) -> str:
    payload = {
        "scenario_id": params.scenario_id,
        "attack_type": params.attack_type.value,
        "learner_role": params.learner_role.value,
        "business_context": params.business_context.value,
        "manipulation_mechanism": params.manipulation_mechanism.value,
        "difficulty_level": params.difficulty_level.value,
        "competency_group": params.competency_group.value,
        "red_flags_required": params.red_flags_required,
        "language": params.language,
    }

    specific_instructions = _INSTRUCTION_BUILDERS[params.competency_group.value](params)

    instructions = (
        "Hãy soạn MỘT bài tập tình huống 3 lớp (Challenge/Explanation/Transferable Knowledge) "
        "về nhận diện social engineering dựa trên tham số JSON dưới đây.\n"
        f"{specific_instructions}\n"
        "Trường 'primary_competency' trong output PHẢI đúng bằng giá trị 'competency_group' cho "
        "dưới đây. Trả lời DUY NHẤT bằng JSON đúng schema đã nêu trong system prompt.\n\n"
        f"Tham số:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return instructions


def build_messages(params: ScenarioParams) -> list[dict]:
    return [{"role": "user", "content": build_user_prompt(params)}]
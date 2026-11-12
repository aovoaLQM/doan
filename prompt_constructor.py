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
from schema_builder import ScenarioParams, ManipulationMechanism, LearnerRole


_LEARNER_ROLES = {
    LearnerRole.ACCOUNTANT: ("nhân viên kế toán", "xử lý chứng từ và thanh toán trong phạm vi được phân quyền"),
    LearnerRole.IT_HELPDESK: ("nhân viên IT Helpdesk", "tiếp nhận hỗ trợ kỹ thuật và xử lý quyền truy cập theo quy trình xác minh"),
    LearnerRole.MID_MANAGER: ("quản lý cấp trung", "điều phối công việc và phê duyệt trong phạm vi được ủy quyền"),
    LearnerRole.RECEPTIONIST: ("lễ tân", "tiếp nhận khách, cuộc gọi, thư từ và chuyển yêu cầu tới bộ phận phụ trách; không tự thực hiện thanh toán hay cấp quyền hệ thống"),
    LearnerRole.NEW_HIRE: ("nhân viên mới", "đang làm quen công việc và quy trình; không mặc định thuộc kế toán, văn thư hoặc có quyền thanh toán/phê duyệt"),
    LearnerRole.HR_STAFF: ("nhân viên HR", "xử lý tuyển dụng, hồ sơ nhân sự và phúc lợi trong phạm vi được phân quyền"),
    LearnerRole.OFFICE_STAFF: ("nhân viên văn phòng", "thực hiện công việc hành chính thông thường trong phạm vi được phân công; không mặc định là kế toán hay người phê duyệt"),
}


def _learner_role_block(params: ScenarioParams) -> str:
    label, duties = _LEARNER_ROLES[params.learner_role]
    return f"""
VAI TRÒ NGƯỜI HỌC BẮT BUỘC:
- Vai trò đã chọn: {label} (learner_role={params.learner_role.value}).
- Mở đầu phải xác định đúng: "Bạn là {label} tại <tên công ty đã cấp>"; không đặt họ tên người học.
- Phạm vi công việc: {duties}.
- Giữ đúng vai trò này trong narrative, options và feedback; không tự đổi nghề để khớp bối cảnh.
- Nếu bối cảnh liên quan nghiệp vụ ngoài quyền hạn, người học chỉ là người tiếp nhận/chuyển yêu cầu
  hoặc bị dụ làm ngoài thẩm quyền; không tự gán quyền chuyển tiền, phê duyệt hay quản trị hệ thống.
  Ví dụ lễ tân nhận yêu cầu chuyển thông tin thanh toán tới bộ phận phụ trách, nhân viên mới bị
  thúc ép bỏ qua việc hỏi người hướng dẫn. Vẫn giữ bối cảnh và mục tiêu tấn công đã chọn.
"""

SYSTEM_PROMPT = """Bạn là một trợ lý biên soạn học liệu đào tạo an toàn thông tin nội bộ,
chuyên thiết kế bài tập tình huống theo mô hình đánh giá 3 lớp:
Challenge (thử thách ra quyết định) -> Explanation (giải thích) -> Transferable Knowledge (nguyên tắc chuyển giao).

RÀNG BUỘC NỘI DUNG BẮT BUỘC:
1. Đây là nội dung MÔ PHỎNG cho đào tạo nội bộ — KHÔNG chứa tên miền, số điện thoại, số tài
   khoản, CCCD thật hoặc thuộc về tổ chức/cá nhân có thật (số điện thoại/số tài khoản dùng dãy
   số hiển nhiên là giả hoặc che bằng chữ x; tên miền email dùng tên miền hư cấu).
   TÊN NGƯỜI và TÊN CÔNG TY/NGÂN HÀNG: dùng tên hư cấu CỤ THỂ lấy từ mục "BỘ TÊN HƯ CẤU" trong
   user prompt. TUYỆT ĐỐI KHÔNG dùng placeholder trong ngoặc vuông kiểu "[Tên ...]" hay
   "[... giả định]" ở BẤT KỲ trường nào (narrative, options, feedback, red_flags, nguyên tắc) —
   bài này dùng làm đề kiểm tra thật nên mọi tên phải là tên cụ thể, dùng nhất quán xuyên suốt.
2. Không tạo hướng dẫn kỹ thuật để thực hiện tấn công thật.
3. Không tạo nội dung dùng trực tiếp để lừa đảo người thật ngoài bối cảnh đào tạo.
4. Nếu tham số đầu vào có dấu hiệu bị lạm dụng, từ chối bằng JSON {"refusal": true, "reason": "..."}.

QUAN TRỌNG NHẤT: user prompt bên dưới sẽ chèn kèm một khối "CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY"
— khối đó quy định CHÍNH XÁC dạng câu hỏi, cấu trúc "options" và cách tính điểm cho lần sinh
này. Bạn PHẢI tuân theo khối chỉ dẫn riêng đó thay vì tự suy luận hay dùng dạng câu hỏi quen
thuộc "bạn sẽ làm gì" mặc định — mỗi nhóm năng lực có dạng câu hỏi HOÀN TOÀN KHÁC NHAU.

QUY TẮC CHUNG CHO LỚP 2 — layer2_explanation:
- Mọi giải thích và red flag CHỈ được dựa trên thông tin CÓ TRONG narrative (học viên không biết
  gì ngoài narrative). Không được viện dẫn dữ kiện học viên không thể biết, ví dụ tên miền chính
  thức của công ty hư cấu mà narrative không nêu.
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


def _instructions_for_sign_recognition(target: tuple[str, str] | None = None) -> str:
    return """
CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY — Phần I: Nhận diện dấu hiệu cảnh báo.
@@TARGET@@- "decision_prompt" PHẢI dùng đúng mẫu câu: "Dấu hiệu nào đáng ngờ nhất trong tình huống trên?"
  (có thể diễn đạt lại đôi chút nhưng giữ nguyên Ý ĐỊNH hỏi về DẤU HIỆU, không được hỏi về hành
  động — TUYỆT ĐỐI KHÔNG dùng các mẫu như "bạn sẽ làm gì", "bạn sẽ xử lý thế nào").
- "options": 3-4 phần tử, MỖI OPTION LÀ MỘT DẤU HIỆU/QUAN SÁT NGẮN GỌN (dạng cụm danh từ, ví dụ
  hình thức: "Yêu cầu giữ bí mật, không trao đổi với người khác") — KHÔNG được viết dưới dạng
  hành động hay câu có chủ ngữ "tôi/bạn sẽ...". Nếu option của bạn có động từ hành động như "gọi
  điện", "chuyển khoản", "xác minh qua...", "báo cáo cho..." thì đó là SAI FORMAT, phải viết lại.
- Đúng 1 option là dấu hiệu đáng ngờ NHẤT trong narrative (is_safe_choice=true, score=100,
  distractor_type="khong_ap_dung"). Đáp án đúng PHẢI suy ra được TRỰC TIẾP từ thông tin có trong
  narrative. Nếu đáp án đúng cần một MỐC ĐỐI CHIẾU (tên miền chính thức, văn phong thường ngày, giờ làm việc,
  ngưỡng phê duyệt, quy trình...), narrative BẮT BUỘC cung cấp đúng mốc cần thiết ở vị trí liên quan
  (tên miền nội bộ đối chiếu ngay qua Từ/Đến, tổ chức bên ngoài cần mốc riêng khi liên quan) — xem quy tắc
  "TỰ ĐỦ DỮ KIỆN" trong khối tên hư cấu.
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
""".replace("@@TARGET@@", _target_flag_block(target))


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


_PART4_CONTEXT_FROM_BRIEF = (
    "- Bối cảnh, kênh liên lạc và vai trò giả mạo ĐÃ ĐƯỢC QUY ĐỊNH trong BRIEF TÌNH HUỐNG phía trên (nhóm\n"
    "  đã chọn) — giữ đúng nhóm và bối cảnh đó, không tự đổi nhóm kịch bản.\n"
)
_PART4_CONTEXT_FREE = (
    "- Bối cảnh/kênh liên lạc/vai trò giả mạo trong \"narrative\" PHẢI khác hẳn 3 nhóm huấn luyện chính\n"
    "  (giả danh lãnh đạo qua email, giả danh IT/Helpdesk, giả danh ngân hàng theo mẫu quen thuộc).\n"
)


def _instructions_for_principle_application(from_brief: bool = False) -> str:
    return """
CHỈ DẪN RIÊNG CHO CÂU HỎI NÀY — Phần IV: Vận dụng nguyên tắc phòng vệ (tình huống CHƯA huấn luyện
trực tiếp — đây là dạng câu hỏi KHÁC HẲN Phần III, không phải hỏi hành động).
@@CONTEXT@@- "decision_prompt" PHẢI dùng đúng mẫu câu: "Nguyên tắc phòng vệ nào có thể áp dụng trong tình
  huống này?" — KHÔNG hỏi "bạn sẽ làm gì".
- "options": 3-4 phần tử, MỖI OPTION LÀ MỘT PHÁT BIỂU VỀ NGUYÊN TẮC/QUAN ĐIỂM XỬ LÝ (câu khẳng
  định ngắn), KHÔNG phải hành động cụ thể. Đúng 1 phát biểu ĐÚNG về nguyên tắc phòng vệ chung
  (is_safe_choice=true, score=100, distractor_type="khong_ap_dung"). Các phát biểu còn lại là
  NGỘ NHẬN PHỔ BIẾN — ví dụ dạng: đánh giá thấp rủi ro vì lý do bề mặt không liên quan (kênh liên
  lạc, lỗi chính tả), hoặc đề xuất "làm trước báo cáo sau" — TẤT CẢ đều score=0,
  distractor_type="khong_ap_dung".
""".replace("@@CONTEXT@@", _PART4_CONTEXT_FROM_BRIEF if from_brief else _PART4_CONTEXT_FREE)


_INSTRUCTION_BUILDERS = {
    "nhan_dien_dau_hieu": lambda params: _instructions_for_sign_recognition(_pick_target_flag(params)),
    "nhan_biet_co_che_thao_tung": lambda params: _instructions_for_manipulation_recognition(params.manipulation_mechanism),
    "lua_chon_hanh_vi_ung_pho": lambda params: _instructions_for_response_behavior(),
    "van_dung_nguyen_tac": lambda params: _instructions_for_principle_application(_active_group(params) is not None),
}


# ---------------------------------------------------------------------------
# Bộ tên hư cấu — CODE chọn sẵn cho mỗi lần sinh (thay vì để LLM tự đặt hoặc để placeholder):
#  - đảm bảo luôn có tên cụ thể, dùng được ngay cho đề kiểm tra thật;
#  - tên thay đổi giữa các bài (đề pre-test/post-test song song cần đổi bối cảnh cụ thể);
#  - chọn xác định theo scenario_id nên cùng một bài luôn cùng bộ tên.
# Lưu ý: tên công ty/ngân hàng là hư cấu nhưng không thể loại trừ hoàn toàn việc trùng tên thật
# ngoài đời — người duyệt (Tab 2) nên liếc qua điểm này.
# ---------------------------------------------------------------------------
_MALE_NAMES = [
    "Trần Quốc Bảo", "Lê Minh Khôi", "Phạm Đức Thịnh", "Nguyễn Hữu Phước",
    "Hoàng Gia Huy", "Vũ Anh Tuấn", "Đặng Văn Long", "Bùi Thế Vinh",
    "Đỗ Trọng Nghĩa", "Ngô Thanh Sơn",
]
_FEMALE_NAMES = [
    "Nguyễn Thu Hà", "Lê Mai Anh", "Phạm Ngọc Lan", "Trần Bích Thảo",
    "Hoàng Diệu Linh", "Vũ Thúy Quỳnh", "Đặng Hồng Nhung", "Bùi Khánh Vy",
    "Đỗ Phương Thảo", "Ngô Minh Châu",
]
# (tên tổ chức, tên miền email chính thức) — đều là hư cấu. Mỗi tổ chức có tên miền chính thức
# để narrative nêu ra làm mốc so sánh cho học viên (xem quy tắc "tự đủ dữ kiện" bên dưới).
_COMPANIES = [
    ("Công ty Cổ phần Công nghệ Zentra", "zentra.vn"),
    ("Công ty TNHH Thương mại Lumina Việt", "luminaviet.vn"),
    ("Công ty Cổ phần Xây dựng Orvia", "orvia.vn"),
    ("Công ty TNHH Logistics Kavian", "kavian.vn"),
    ("Công ty Cổ phần Thực phẩm Naviro", "naviro.vn"),
    ("Công ty TNHH Giải pháp Số Veltra", "veltra.vn"),
    ("Công ty Cổ phần Vật liệu Marlen", "marlen.vn"),
    ("Công ty TNHH Dịch vụ Tài chính Corvan", "corvan.vn"),
    ("Công ty Cổ phần Công nghệ Sao Mộc", "saomoc.vn"),
    ("Công ty TNHH Thương mại Mây Trắng", "maytrang.vn"),
    ("Công ty Cổ phần Cơ khí Bắc Sơn", "cokhibacson.vn"),
    ("Công ty TNHH Nông sản Đồng Xanh", "nongsandongxanh.vn"),
    ("Công ty Cổ phần May mặc Hải Âu", "mayhaiau.vn"),
    ("Công ty TNHH Thiết kế Cánh Diều", "thietkecanhdieu.vn"),
    ("Công ty Cổ phần Vận tải Ánh Dương", "vantaianhduong.vn"),
    ("Công ty TNHH Sản xuất Gốm Bình Minh", "gombinhminh.vn"),
    ("Công ty Cổ phần Năng lượng Gió Nam", "gionam.vn"),
    ("Công ty TNHH Giáo dục Hạt Mầm", "giaoduchatmam.vn"),
    ("Công ty Cổ phần Bao bì Tre Việt", "baobitreviet.vn"),
    ("Công ty TNHH Phần mềm Cầu Vồng", "phanmemcauvong.vn"),
    ("Công ty Cổ phần Thực phẩm Vườn Nhà", "thucphamvuonnha.vn"),
    ("Công ty TNHH Nội thất Gỗ Sồi", "noithatgosoi.vn"),
    ("Công ty Cổ phần Dệt sợi Sông Lam", "detsoisonglam.vn"),
    ("Công ty TNHH Du lịch Biển Ngọc", "dulichbienngoc.vn"),
]
_PARTNERS = [
    ("Công ty TNHH Cung ứng Solvex", "solvex.vn"),
    ("Công ty Cổ phần Thiết bị Brandor", "brandor.vn"),
    ("Công ty TNHH Vận tải Quillon", "quillon.vn"),
    ("Công ty Cổ phần Bao bì Dalmar", "dalmar.vn"),
    ("Công ty TNHH Tư vấn Nexaro", "nexaro.vn"),
    ("Công ty Cổ phần Nội thất Pelvin", "pelvin.vn"),
    ("Công ty TNHH Điện lạnh Torvex", "torvex.vn"),
    ("Công ty Cổ phần In ấn Mirage Việt", "mirageviet.vn"),
    ("Công ty TNHH Văn phòng phẩm Bút Xanh", "butxanh.vn"),
    ("Công ty Cổ phần Thiết bị Đỉnh Núi", "thietbidinhnui.vn"),
    ("Công ty TNHH Kho vận Bến Thành Đông", "benthanhdong.vn"),
    ("Công ty Cổ phần In ấn Sắc Màu", "inansacmau.vn"),
    ("Công ty TNHH Vật tư Hướng Dương", "vattuhuongduong.vn"),
    ("Công ty Cổ phần Cung ứng Đại Ngàn", "cungungdaingan.vn"),
    ("Công ty TNHH Điện máy Trúc Lâm", "dienmaytruclam.vn"),
    ("Công ty Cổ phần Bao bì Lá Non", "baobilanon.vn"),
    ("Công ty TNHH Tư vấn Đường Mới", "tuvanduongmoi.vn"),
    ("Công ty Cổ phần Nội thất Nếp Nhà", "noithatnepnha.vn"),
    ("Công ty TNHH Dịch vụ Cánh Én", "dichvucanhen.vn"),
    ("Công ty Cổ phần Vận chuyển Hải Đăng", "vanchuyenhaidang.vn"),
    ("Công ty TNHH Sản xuất Suối Nguồn", "sanxuatsuoinguon.vn"),
    ("Công ty Cổ phần Giải pháp Cầu Nối", "giaiphapcaunoi.vn"),
    ("Công ty TNHH Phân phối An Hòa", "phanphoianhoa.vn"),
    ("Công ty Cổ phần Dịch vụ Thanh Trúc", "dichvuthanhtruc.vn"),
]
_BANKS = [
    ("Ngân hàng ABC", "nganhangabc.vn"),
    ("Ngân hàng XYZ", "nganhangxyz.vn"),
    ("Ngân hàng Alpha Việt", "alphavietbank.vn"),
    ("Ngân hàng Delta Pacific", "deltapacific.vn"),
]


_COURIERS = [
    ("Giao hàng Tốc Hành Vela", "velaexpress.vn"),
    ("Vận chuyển Nhanh Korin", "korinship.vn"),
    ("Bưu chuyển Dalton Việt", "daltonviet.vn"),
    ("Giao nhận Rapido Lume", "rapidolume.vn"),
]
_CLOUD_SERVICES = [
    ("dịch vụ lưu trữ và ký tài liệu Docuvia", "docuvia.com"),
    ("nền tảng chia sẻ tài liệu Filerra", "filerra.com"),
    ("dịch vụ ký số Signara", "signara.com"),
]


def _make_lookalike_domain(domain: str, rng: random.Random) -> str:
    """Sinh tên miền giả mạo gần giống tên miền chính thức (khác tinh tế, dễ bị bỏ sót)."""
    base, tld = domain.rsplit(".", 1)
    candidates = [
        f"{base}-corp.{tld}",
        f"{base}-vn.{tld}",
        f"{base}-mail.{tld}",
        f"{base}{base[-1]}.{tld}",                            # lặp chữ cái cuối
    ]
    swappable = [i for i in range(1, len(base) - 2)
                 if base[i].isalpha() and base[i + 1].isalpha() and base[i] != base[i + 1]]
    if swappable:                                             # hoán đổi 2 chữ cái liền kề
        i = rng.choice(swappable)
        candidates.append(f"{base[:i]}{base[i + 1]}{base[i]}{base[i + 2:]}.{tld}")
    result = rng.choice(candidates)
    return result if result != domain else f"{base}-corp.{tld}"


_RECIPIENT_USERNAMES = (
    "jack123", "thuyabc", "nganyz", "tom33", "duc123",
    "linh88", "minh27", "hanhng", "nam456", "trang92",
    "khoa21", "maiabc", "phuong09", "bao77", "vytran",
    "huy123", "anhtuan", "ngoc35", "quynh68", "tuan99",
    "lan24", "sonabc", "haing", "yen56", "long33",
    "thao91", "phuc22", "kimanh", "hoang18", "dung66",
)


def _pick_names(params: ScenarioParams) -> dict:
    rng = random.Random(params.scenario_id)
    person_main, person_aux = rng.sample(_MALE_NAMES + _FEMALE_NAMES, 2)
    company, company_domain = rng.choice(_COMPANIES)
    partner, partner_domain = rng.choice(_PARTNERS)
    bank, bank_domain = rng.choice(_BANKS)
    courier, courier_domain = rng.choice(_COURIERS)
    cloud, cloud_domain = rng.choice(_CLOUD_SERVICES)
    company_domain, partner_domain, bank_domain, courier_domain, cloud_domain = (
        domain.rsplit(".", 1)[0] + rng.choice((".vn", ".com", ".net"))
        for domain in (company_domain, partner_domain, bank_domain, courier_domain, cloud_domain)
    )
    return {
        "person_main": person_main, "person_aux": person_aux,
        "company": company, "company_domain": company_domain,
        "partner": partner, "partner_domain": partner_domain,
        "bank": bank, "bank_domain": bank_domain,
        "fake_company": _make_lookalike_domain(company_domain, rng),
        "fake_partner": _make_lookalike_domain(partner_domain, rng),
        "fake_bank": _make_lookalike_domain(bank_domain, rng),
        "courier": courier, "courier_domain": courier_domain,
        "fake_courier": _make_lookalike_domain(courier_domain, rng),
        "cloud": cloud, "cloud_domain": cloud_domain,
        "fake_cloud": _make_lookalike_domain(cloud_domain, rng),
        "recipient_email": f"{rng.choice(_RECIPIENT_USERNAMES)}@{company_domain}",
    }


def _fictional_names_block(params: ScenarioParams, names: dict) -> str:
    person_main, person_aux = names["person_main"], names["person_aux"]
    company, company_domain, fake_company = names["company"], names["company_domain"], names["fake_company"]
    partner, partner_domain, fake_partner = names["partner"], names["partner_domain"], names["fake_partner"]
    bank, bank_domain, fake_bank = names["bank"], names["bank_domain"], names["fake_bank"]
    courier, courier_domain, fake_courier = names["courier"], names["courier_domain"], names["fake_courier"]
    cloud, cloud_domain, fake_cloud = names["cloud"], names["cloud_domain"], names["fake_cloud"]
    group = params.scenario_group.value
    ctx = params.business_context.value
    if group == "gia_danh_lanh_dao":
        sender_email = f"giam.doc@{fake_company}"
    elif group == "gia_danh_it":
        local = "nhan.vien" if params.learner_role.value == "it_helpdesk" else "it.helpdesk"
        sender_email = f"{local}@{fake_company}"
    elif group == "gia_danh_ngan_hang":
        sender_email = f"cham.soc@{fake_bank}"
    else:
        sender_email = {
            "dong_nghiep_nho_ho_tro": f"dong.nghiep@{fake_company}",
            "dang_ky_cong_doan_phuc_loi": f"cong.doan@{fake_company}",
            "mua_ban_thanh_ly_noi_bo": f"nhan.vien@{fake_company}",
            "giao_hang_phi_theo_doi": f"giao.hang@{fake_courier}",
            "dich_vu_dam_may_tai_lieu": f"tai.lieu@{fake_cloud}",
            "nha_tuyen_dung_doi_tac": f"tuyen.dung@{fake_partner}",
        }.get(ctx, f"thong.bao@{fake_partner}")
    return f"""
BỘ TÊN HƯ CẤU DÙNG CHO BÀI NÀY (bắt buộc dùng nguyên văn, nhất quán xuyên suốt narrative,
options, feedback và red_flags; không cần dùng hết nếu tình huống không cần nhân vật/tổ chức đó):
- Nhân vật chính (người bị giả mạo / người gửi / người gọi): {person_main}
- Nhân vật phụ (đồng nghiệp, cấp trên, thư ký hoặc đầu mối đối tác — nếu cần): {person_aux}
- Công ty của người học: {company} — email nội bộ chính thức: @{company_domain}
  | tên miền GIẢ MẠO gần giống (cho email đáng ngờ): @{fake_company}
- Đối tác / nhà cung cấp (nếu cần): {partner} — email chính thức: @{partner_domain}
  | tên miền GIẢ MẠO gần giống: @{fake_partner}
- Ngân hàng (nếu cần): {bank} — email chính thức: @{bank_domain}
  | tên miền GIẢ MẠO gần giống: @{fake_bank}
- Đơn vị giao hàng (nếu cần): {courier} — tên miền liên kết chính thức: {courier_domain}
  | tên miền GIẢ MẠO gần giống: {fake_courier}
- Dịch vụ lưu trữ/ký tài liệu (nếu cần): {cloud} — địa chỉ đăng nhập chính thức: {cloud_domain}
  | tên miền GIẢ MẠO gần giống: {fake_cloud}
Quy tắc dùng tên:
- Chỉ với kênh email: dùng địa chỉ Từ: {sender_email}; Đến: {names['recipient_email']}.
  Dòng người nhận chỉ viết Đến: <{names['recipient_email']}>; không thêm tên hiển thị hay họ tên người học.
  Không suy ra tên người học từ tên tài khoản email.
  Tên hiển thị và chữ ký vẫn dùng nhân vật cụ thể đúng vai trò; không dùng tên người để tự đặt lại địa chỉ.
  Địa chỉ viết nguyên vẹn, không tô đậm/in nghiêng riêng ký tự khác biệt, không dùng placeholder người nhận.
  Mọi email và tên miền mô phỏng dùng đúng tên miền đã cấp, với đuôi .vn, .com hoặc .net.
- Chọn chức danh/quan hệ phù hợp với loại tấn công cho nhân vật (ví dụ Tổng Giám đốc, Trưởng phòng,
  kỹ thuật viên IT, chuyên viên ngân hàng); xưng hô (anh/chị/ông/bà) phải khớp giới tính của tên.
- Tên hiển thị của người gửi trong email PHẢI là tên cụ thể kèm chức danh (ví dụ "<chức danh đúng vai của kẻ tấn công
  trong bài này> {person_main}"), KHÔNG phải "[Tên ...]". Lời chào email dùng "Chào bạn", "Kính gửi Anh/Chị" hoặc
  tên cụ thể, KHÔNG dùng "[Tên của bạn]".
- Khi một option hoặc lời giải thích nhắc tới người gửi/tổ chức, viết tên cụ thể ở trên (hoặc chức
  danh), không dùng placeholder.
- Ngoặc vuông CHỈ dùng cho nhãn nút/liên kết giả trong email, ví dụ "[Xác minh tài khoản ngay]".
- Khi tình huống giả danh một tổ chức/nhân vật, email đáng ngờ PHẢI gửi từ tên miền GIẢ MẠO tương
  ứng ở trên; còn tên miền CHÍNH THỨC chỉ dùng làm mốc đối chiếu (xem quy tắc kế tiếp).

QUY TẮC "TỰ ĐỦ DỮ KIỆN" (rất quan trọng — học viên CHỈ biết những gì narrative nói):
- Nếu một dấu hiệu/đáp án dựa trên việc đối chiếu với thông tin CHÍNH THỨC (tên miền email nội bộ,
  tên miền của ngân hàng/đối tác, số tổng đài, địa chỉ website...), narrative PHẢI nêu thông tin
  chính thức đó ở vị trí liên quan, ngắn gọn và trung tính. Với giả danh nội bộ, dùng tên miền
  trong dòng Đến: {names['recipient_email']} làm mốc so sánh với dòng Từ; không lặp câu mô tả
  email nội bộ chính thức. Với tổ chức bên ngoài, tên miền người nhận KHÔNG chứng minh tên miền
  người gửi; nếu đáp án/lời giải cần so sánh, thêm một mốc ngắn như địa chỉ gửi của thông báo trước.
- Mở đầu chỉ 1–2 câu, tối đa 50 từ: vai trò, tổ chức và hoàn cảnh cần thiết. Đi ngay vào thông điệp.
  Xưng hô người học là "bạn", không đặt hoặc nhắc họ tên người học. Mở đầu: "Bạn là {_LEARNER_ROLES[params.learner_role][0]}
  tại {company}."; không suy ra nghề nghiệp từ bối cảnh hoặc địa chỉ email.
  Chỉ thêm quy trình/mốc đối chiếu nếu đáp án hoặc lời giải cần đến; không chép toàn bộ danh sách
  tham khảo vào narrative và không dồn quy trình lên mở đầu. Không tự thêm ngưỡng tiền hay giờ làm
  việc không liên quan. Nếu dùng ngưỡng/thời điểm để suy luận, dữ kiện và yêu cầu phải nhất quán.
- Không được để học viên phải "tự biết" tên miền chính thức của một tổ chức hư cấu.
- Phần giải thích (Lớp 2) chỉ được viện dẫn thông tin CÓ TRONG narrative. Cấm dùng cách nói như
  "thường là ...", "ví dụ ..." để suy đoán tên miền/thông tin chính thức mà narrative không nêu.
"""


# ---------------------------------------------------------------------------
# BRIEF TÌNH HUỐNG theo bối cảnh: code QUYẾT ĐỊNH ai giả danh ai (thay vì để LLM tự đoán).
# Hiện có brief cho nhóm giả danh IT/Helpdesk (các bối cảnh IT bên dưới). Các bối cảnh khác
# không có brief -> giữ nguyên hành vi cũ.
# ---------------------------------------------------------------------------
_IT_CONTEXTS = {"reset_mat_khau", "canh_bao_bao_mat_tai_khoan", "ho_tro_ky_thuat_tu_xa",
                "hop_thu_day_hoac_het_han", "cai_phan_mem_ban_va", "xac_nhan_dang_nhap_mfa"}

_IT_PRETEXT = {
    "reset_mat_khau": "yêu cầu người học đặt lại/đổi mật khẩu (bấm liên kết đặt lại mật khẩu, hoặc đọc mật khẩu/mã tạm thời cho 'kỹ thuật viên')",
    "canh_bao_bao_mat_tai_khoan": "cảnh báo 'hoạt động đăng nhập bất thường' hoặc 'nâng cấp bảo mật bắt buộc', yêu cầu xác minh tài khoản (bấm liên kết, hoặc điền tên đăng nhập + mật khẩu vào biểu mẫu) kèm hạn chót và đe dọa khóa tài khoản",
    "ho_tro_ky_thuat_tu_xa": "báo 'máy tính nhiễm mã độc / đang rò rỉ dữ liệu' và yêu cầu cài phần mềm điều khiển từ xa rồi đọc mã kết nối để 'kiểm tra và làm sạch'",
}

_IT_SOPHISTICATION = {
    "beginner": "dấu hiệu lộ rõ ngay lần đọc đầu (tên miền gửi lệch, giọng đe dọa 'trong 24 giờ sẽ bị khóa', liên kết không thuộc cổng nội bộ).",
    "intermediate": "văn phong chuyên nghiệp, ít lỗi, giống thông báo IT thật; dấu hiệu cần suy luận thêm (đòi mật khẩu/OTP, đòi cài phần mềm ngoài quy trình ticket, liên hệ ngoài giờ hoặc khi không có yêu cầu hỗ trợ trước đó).",
    "advanced": "rất tự nhiên: người gửi/người gọi biết tên phòng ban và phần mềm đang dùng, dùng email/số máy giống nội bộ, kết hợp nhiều cơ chế tâm lý (quyền lực + khẩn cấp + sợ mất dữ liệu).",
}

_IT_REVERSE_PRETEXT = {
    "reset_mat_khau": "reset mật khẩu và gửi mật khẩu mới qua email/tin nhắn vì 'không tự đăng nhập được, đang rất gấp'",
    "canh_bao_bao_mat_tai_khoan": "tắt hoặc đặt lại xác thực đa yếu tố (MFA), hoặc mở khóa tài khoản, vì 'bị khóa, đang gấp'",
    "ho_tro_ky_thuat_tu_xa": "cấp quyền truy cập/điều khiển từ xa vào máy hoặc hệ thống của họ ngay lập tức",
}


_IT_PRETEXT.update({
    "hop_thu_day_hoac_het_han": "thông báo hộp thư sắp đầy hoặc mật khẩu sắp hết hạn, yêu cầu bấm liên kết 'gia hạn' và đăng nhập trước hạn chót",
    "cai_phan_mem_ban_va": "thông báo 'bản vá bảo mật bắt buộc' hoặc phần mềm mới, yêu cầu tải và cài đặt ngay (KHÔNG kèm đường dẫn tải thật)",
    "xac_nhan_dang_nhap_mfa": "báo 'phát hiện đăng nhập lạ', yêu cầu xác nhận thông báo MFA hoặc đọc mã xác thực để 'chặn truy cập trái phép'",
})
_IT_REVERSE_PRETEXT.update({
    "hop_thu_day_hoac_het_han": "tăng dung lượng hoặc gia hạn mật khẩu hộp thư và gửi thông tin đăng nhập mới qua chat vì 'đang rất gấp'",
    "cai_phan_mem_ban_va": "cài ngay một phần mềm 'do khách hàng yêu cầu' hoặc tắt chặn phần mềm ngoài danh mục cho máy của họ",
    "xac_nhan_dang_nhap_mfa": "gửi mã MFA hoặc chấp nhận yêu cầu xác thực hộ vì 'đổi điện thoại, không nhận được mã'",
})


def _it_channel(params: ScenarioParams) -> str:
    atk = params.attack_type.value
    if atk == "vishing":
        return "phone_call"
    if atk == "smishing":
        return "sms"
    if atk == "pretexting" and params.difficulty_level.value == "advanced":
        return "phone_call"
    return "email"


_CHANNEL_FORMAT_HINT = {
    "email": "narrative là một EMAIL: luôn có Từ (tên hiển thị cụ thể và địa chỉ giả mạo), Đến (chỉ địa chỉ email trong dấu <>, không có họ tên người nhận), Tiêu đề và nội dung; dùng địa chỉ được cấp trong BỘ TÊN HƯ CẤU, không tô nổi chỗ khác biệt tên miền.",
    "phone_call": "narrative là một CUỘC GỌI: nêu số hiển thị trên máy, người gọi tự xưng ai, và lời thoại chính của người gọi (KHÔNG viết thành email).",
    "sms": "narrative là một TIN NHẮN SMS ngắn kèm liên kết giả (KHÔNG viết thành email dài).",
    "chat": "narrative là một CUỘC TRÒ CHUYỆN qua ứng dụng nhắn tin (như Zalo/Messenger): nêu tên hiển thị và ảnh đại diện của tài khoản, rồi các tin nhắn chính theo thứ tự (KHÔNG viết thành email).",
    "in_person": "narrative mô tả một TÌNH HUỐNG TRỰC TIẾP tại nơi làm việc: ai xuất hiện, nói và làm gì, bối cảnh xung quanh (KHÔNG viết thành email).",
}


def _brief_it(params: ScenarioParams, names: dict) -> str:
    it_library = _format_library(params, "it")
    rev_library = _format_library(params, "it_reverse")
    ctx = params.business_context.value
    company, company_domain = names["company"], names["company_domain"]
    fake_company, person_main = names["fake_company"], names["person_main"]
    level = params.difficulty_level.value

    if params.learner_role.value == "it_helpdesk":
        return f"""
BRIEF TÌNH HUỐNG (bắt buộc): NGƯỜI HỌC LÀ NHÂN VIÊN IT HELPDESK của {company}. Kẻ tấn công ({person_main})
giả danh một NHÂN VIÊN hoặc LÃNH ĐẠO của công ty để nhờ Helpdesk làm việc nhạy cảm: {_IT_REVERSE_PRETEXT[ctx]}.
- KHÔNG đảo vai: kẻ tấn công KHÔNG giả danh IT, vì người học chính là IT.
- Mốc tham khảo chỉ dùng khi đáp án/lời giải cần: quy trình xác minh danh tính của Helpdesk hoặc cổng ticket
  nội bộ; với email, đối chiếu tên miền qua dòng Từ/Đến, không lặp mô tả tên miền ở mở đầu.
- THƯ VIỆN DẤU HIỆU của nhóm này (red_flags chỉ chọn trong thư viện này, diễn đạt lại theo narrative, chỉ
  chọn dấu hiệu THỰC SỰ được cài trong narrative, và gán tier đúng như dưới đây):
{rev_library}
- Hành vi an toàn đầy đủ: xác minh danh tính người yêu cầu qua kênh độc lập đã biết (gọi số trong danh bạ
  nội bộ, quy trình xác minh của Helpdesk), yêu cầu tạo ticket, KHÔNG gửi mật khẩu/mã qua email-tin nhắn,
  báo cáo bộ phận ATTT.
"""

    channel = _it_channel(params)
    if channel == "phone_call":
        reference_line = (
            "cách công ty vẫn hỗ trợ IT — số máy lẻ Helpdesk chính thức là một số ngắn 4 chữ số "
            "(ví dụ 1000) đã được niêm yết, và mọi yêu cầu hỗ trợ đều tạo qua cổng ticket nội bộ; "
            "cuộc gọi đáng ngờ hiển thị số khác hoặc giả dạng số nội bộ"
        )
    else:
        reference_line = (
            f"email nội bộ chính thức của công ty là @{company_domain} (email/liên kết đáng ngờ dùng "
            f"@{fake_company}), và cách công ty vẫn hỗ trợ IT (ví dụ mọi yêu cầu hỗ trợ đều tạo qua "
            "cổng ticket nội bộ / số máy lẻ Helpdesk đã niêm yết)"
        )
    return f"""
BRIEF TÌNH HUỐNG (bắt buộc — đây là nhóm "Giả danh IT / Helpdesk", KHÔNG phải giả danh lãnh đạo):
- Kẻ tấn công ({person_main}) GIẢ DANH bộ phận IT / Helpdesk / quản trị viên hệ thống của {company}, nhắm
  vào người học (một nhân viên bình thường, KHÔNG phải nhân viên IT). TUYỆT ĐỐI KHÔNG đảo vai: kẻ tấn công
  không phải CEO/giám đốc/ngân hàng, và người học không phải nhân viên IT.
- Kênh: "{channel}" — {_CHANNEL_FORMAT_HINT[channel]} Trường "channel" trong output PHẢI là "{channel}".
- Cớ tiếp cận (theo bối cảnh): {_IT_PRETEXT[ctx]}.
- Độ tinh vi theo độ khó "{level}": {_IT_SOPHISTICATION[level]}
- Nếu có phần mềm điều khiển từ xa: gọi chung là "phần mềm điều khiển từ xa" (hoặc tên phổ biến), KHÔNG kèm
  đường dẫn tải thật.
- Mốc tham khảo (chỉ chọn dữ kiện đáp án/lời giải cần): {reference_line}.
  Không chép toàn bộ; với email nội bộ đối chiếu ngay qua Từ/Đến, bỏ câu mô tả tên miền ở mở đầu.
- THƯ VIỆN DẤU HIỆU của nhóm này (red_flags chỉ chọn trong thư viện này, diễn đạt lại theo narrative, chỉ
  chọn dấu hiệu THỰC SỰ được cài trong narrative, và gán tier đúng như dưới đây):
{it_library}
- Hành vi an toàn đầy đủ (dùng cho đáp án an toàn Phần III và nguyên tắc Lớp 3): KHÔNG bấm liên kết / nhập
  mật khẩu / cài phần mềm / đọc mã OTP; tự mở cổng nội bộ bằng địa chỉ đã biết hoặc gọi lại Helpdesk qua
  số đã lưu/niêm yết chính thức (không dùng số trong email hoặc cuộc gọi); đối chiếu quy trình hỗ trợ (có
  ticket không); báo cáo bộ phận ATTT.
"""


_LEADER_PRETEXT = {
    "chuyen_khoan_khan": "yêu cầu chuyển khoản GẤP cho một đối tác/nhà cung cấp mới (lý do: đang họp kín, không nghe điện được)",
    "xu_ly_hoa_don": "yêu cầu thanh toán hóa đơn cuối tháng và cập nhật tài khoản thụ hưởng mới của một nhà cung cấp quen thuộc",
    "onboard_nha_cung_cap": "yêu cầu thêm ngay một nhà cung cấp mới vào hệ thống và thanh toán đợt đầu, bỏ qua bước thẩm định",
    "ky_hop_dong": "yêu cầu thanh toán đợt 1 của một hợp đồng 'đang ở giai đoạn quyết định' và xử lý ngoài luồng phê duyệt thông thường",
    "tuyen_dung": "yêu cầu gửi gấp dữ liệu nội bộ (hồ sơ nhân sự, danh sách ứng viên, thông tin lương) qua email và giữ kín",
}

_LEADER_SOPHISTICATION = {
    "beginner": "dấu hiệu lộ rõ (địa chỉ gửi gần giống nhưng sai tên miền nội bộ, giọng khẩn cấp, yêu cầu giữ kín, văn phong hơi lạ).",
    "intermediate": "văn phong chuyên nghiệp, ít lỗi chính tả; dấu hiệu cần suy luận (yêu cầu bỏ qua xác minh/phê duyệt thông thường, nhà cung cấp mới hoặc đổi tài khoản phút chót, gửi cuối giờ/cuối tuần).",
    "advanced": "rất tự nhiên: có chuỗi email giả lập 'Re:' với đồng nghiệp tạo bối cảnh hợp lý, văn phong và tên dự án sát nội bộ, số tiền sát ngưỡng phê duyệt, kết hợp quyền lực + khẩn cấp + bí mật.",
}

_BANK_SOPHISTICATION = {
    "beginner": "thông báo 'phát hiện giao dịch đáng ngờ', yêu cầu bấm liên kết xác minh trong 24 giờ, đe dọa khóa tài khoản; dấu hiệu lộ rõ (tên miền gửi gần giống, liên kết không phải website chính thức).",
    "intermediate": "văn phong chuyên nghiệp, thông báo 'nâng cấp bảo mật / cập nhật thông tin khách hàng', yêu cầu điền số CMND/CCCD, số điện thoại, email vào biểu mẫu trước một hạn chót; dấu hiệu cần suy luận thêm.",
    "advanced": "rất thuyết phục: người gửi/người gọi biết thông tin cơ bản (tên ngân hàng, 4 số cuối tài khoản viết dạng xxxx), kênh giả mạo giống chính thức, đòi mã OTP/MFA để 'hủy giao dịch', ép trong vài phút.",
}


_BANK_PRETEXT = {
    "xac_minh_giao_dich_ngan_hang": "phát hiện giao dịch bất thường trên tài khoản của người học, yêu cầu xác minh (bấm liên kết hoặc cung cấp thông tin)",
    "cap_nhat_thong_tin_ekyc": "yêu cầu cập nhật thông tin khách hàng / xác thực sinh trắc học (eKYC) theo 'quy định mới' trước một hạn chót, nhằm thu thập CCCD và ảnh chân dung",
    "huy_giao_dich_doc_otp": "thông báo có giao dịch chuyển tiền lớn bất thường và yêu cầu đọc mã OTP để 'hủy giao dịch', ép trong vài phút",
    "the_tai_khoan_bi_khoa": "thông báo thẻ hoặc tài khoản bị khóa do nghi ngờ gian lận, yêu cầu 'mở khóa' bằng cách nhập thông tin thẻ hoặc đăng nhập",
    "uu_dai_hoan_tien_han_muc": "thông báo ưu đãi, hoàn tiền hoặc nâng hạn mức thẻ đặc biệt, cần xác nhận thông tin hoặc đóng một khoản phí nhỏ",
    "cap_nhat_ung_dung_smart_otp": "yêu cầu cập nhật hoặc kích hoạt lại ứng dụng ngân hàng / Smart OTP vì 'nâng cấp bảo mật', kèm liên kết cài đặt",
}
_BANK_EXTRA_SAFE = {
    "huy_giao_dich_doc_otp": "Ngân hàng không bao giờ yêu cầu đọc OTP để hủy giao dịch; nếu lo ngại, tự khóa thẻ ngay trong ứng dụng.",
    "the_tai_khoan_bi_khoa": "Kiểm tra trạng thái thẻ ngay trong ứng dụng ngân hàng hoặc gọi số in trên thẻ.",
    "cap_nhat_thong_tin_ekyc": "Chỉ cập nhật thông tin/eKYC trong ứng dụng chính thức hoặc tại quầy giao dịch.",
    "uu_dai_hoan_tien_han_muc": "Kiểm tra chương trình ưu đãi trên kênh chính thức; ngân hàng không thu phí nhận ưu đãi qua liên kết.",
    "cap_nhat_ung_dung_smart_otp": "Chỉ tải/cập nhật ứng dụng ngân hàng từ kho ứng dụng chính thức, không cài từ liên kết; không đọc mã kích hoạt cho bất kỳ ai.",
}


def _bank_channel(params: ScenarioParams) -> str:
    return {"vishing": "phone_call", "smishing": "sms"}.get(params.attack_type.value, "email")


def _brief_leader(params: ScenarioParams, names: dict) -> str:
    leader_library = _format_library(params, "leader")
    ctx = params.business_context.value
    company, company_domain = names["company"], names["company_domain"]
    fake_company, person_main = names["fake_company"], names["person_main"]
    partner = names["partner"]
    level = params.difficulty_level.value
    return f"""
BRIEF TÌNH HUỐNG (bắt buộc — đây là nhóm "Giả danh lãnh đạo (CEO Fraud / BEC)", KHÔNG phải giả danh IT hay ngân hàng):
- Kẻ tấn công ({person_main}) GIẢ DANH một lãnh đạo cấp cao (Tổng Giám đốc / Giám đốc điều hành / Giám đốc tài
  chính) của {company}, nhắm vào người học theo đúng VAI TRÒ NGƯỜI HỌC BẮT BUỘC; không mặc định người học
  có quyền xử lý giao dịch hoặc dữ liệu. TUYỆT ĐỐI KHÔNG
  đảo vai: kẻ tấn công không phải IT/Helpdesk hay ngân hàng, và người học không phải lãnh đạo.
- Kênh: "email" — {_CHANNEL_FORMAT_HINT["email"]} Trường "channel" trong output PHẢI là "email".
- Cớ tiếp cận (theo bối cảnh): {_LEADER_PRETEXT[ctx]}. Nếu cần đối tác/nhà cung cấp, dùng {partner}.
- Độ tinh vi theo độ khó "{level}": {_LEADER_SOPHISTICATION[level]}
- Mốc đối chiếu chỉ bổ sung khi đáp án/lời giải cần: so sánh tên miền Từ với Đến cho giả danh nội bộ;
  chỉ nêu quy trình thanh toán hoặc xác minh thay đổi tài khoản nếu liên quan trực tiếp. Không mặc định
  thêm ngưỡng tiền, phê duyệt hai cấp hoặc quy trình nhà cung cấp; dữ kiện phải khớp giao dịch trong bài.
- THƯ VIỆN DẤU HIỆU của nhóm này (red_flags chỉ chọn trong thư viện này, diễn đạt lại theo narrative, chỉ
  chọn dấu hiệu THỰC SỰ được cài trong narrative, và gán tier đúng như dưới đây):
{leader_library}
- Hành vi an toàn đầy đủ (dùng cho đáp án an toàn Phần III và nguyên tắc Lớp 3): DỪNG xử lý yêu cầu nhạy cảm
  (không chuyển tiền, không đổi tài khoản, không gửi dữ liệu); xác minh qua kênh độc lập đã biết (gọi số trong
  danh bạ nội bộ, KHÔNG dùng số/email trong thư nghi ngờ); đối chiếu quy chế thanh toán, ngưỡng phê duyệt và
  quy định đổi tài khoản; báo cáo bộ phận ATTT/quản lý rủi ro.
"""


def _brief_bank(params: ScenarioParams, names: dict) -> str:
    bank_library = _format_library(params, "bank")
    ctx = params.business_context.value
    bank_pretext = _BANK_PRETEXT[ctx]
    bank_extra_safe = _BANK_EXTRA_SAFE.get(ctx, "")
    company, bank = names["company"], names["bank"]
    bank_domain, fake_bank = names["bank_domain"], names["fake_bank"]
    person_main = names["person_main"]
    level = params.difficulty_level.value
    channel = _bank_channel(params)
    if channel == "phone_call":
        reference_line = (
            f"tổng đài chăm sóc khách hàng chính thức của {bank} là một số ngắn đã niêm yết trên thẻ/ứng dụng "
            f"(viết dạng 1900 xxxx), và {bank} không bao giờ yêu cầu khách đọc mã OTP qua điện thoại; cuộc gọi đáng "
            "ngờ hiển thị số khác hoặc giả dạng số tổng đài"
        )
    else:
        reference_line = (
            f"email chính thức của {bank} gửi đến khách hàng có đuôi @{bank_domain} (email/liên kết đáng ngờ dùng "
            f"@{fake_bank}), và khách hàng vẫn kiểm tra thông báo qua ứng dụng/website chính thức của ngân hàng"
        )
    return f"""
BRIEF TÌNH HUỐNG (bắt buộc — đây là nhóm "Giả danh ngân hàng (Phishing/Vishing)", KHÔNG phải giả danh lãnh đạo hay IT):
- Kẻ tấn công ({person_main}) GIẢ DANH nhân viên bộ phận chống gian lận / chăm sóc khách hàng của {bank}, nhắm
  vào người học (một nhân viên của {company}, đồng thời là khách hàng cá nhân của {bank}). TUYỆT ĐỐI KHÔNG đảo
  vai: kẻ tấn công không phải lãnh đạo công ty hay IT nội bộ.
- Kênh: "{channel}" — {_CHANNEL_FORMAT_HINT[channel]} Trường "channel" trong output PHẢI là "{channel}".
- Cớ tiếp cận (theo bối cảnh): {bank_pretext}.
- Độ tinh vi theo độ khó "{level}": {_BANK_SOPHISTICATION[level]}
- Mốc tham khảo (chỉ chọn dữ kiện đáp án/lời giải cần): {reference_line}.
  Nếu cần so sánh tên miền ngân hàng, thêm một mốc chính thức ngắn; tên miền người nhận không phải mốc
  của ngân hàng. Không dùng số tài khoản/số điện thoại thật; số 4 cuối tài khoản viết dạng xxxx.
- THƯ VIỆN DẤU HIỆU của nhóm này (red_flags chỉ chọn trong thư viện này, diễn đạt lại theo narrative, chỉ
  chọn dấu hiệu THỰC SỰ được cài trong narrative, và gán tier đúng như dưới đây):
{bank_library}
- Hành vi an toàn đầy đủ (dùng cho đáp án an toàn Phần III và nguyên tắc Lớp 3): KHÔNG bấm liên kết / nhập thông
  tin cá nhân / đọc mã OTP; tự mở ứng dụng hoặc website chính thức của ngân hàng bằng địa chỉ đã biết, hoặc gọi lại
  tổng đài qua số đã lưu/niêm yết (không dùng số trong thư hoặc cuộc gọi); kiểm tra lịch sử giao dịch và thông báo
  chính thức; báo cáo bộ phận ATTT. {bank_extra_safe}
"""


_OTHER_PRETEXT = {
    "dong_nghiep_nho_ho_tro": "giả danh đồng nghiệp ngang cấp (KHÔNG phải lãnh đạo hoặc IT), viện cớ không truy cập được tài khoản công ty để nhờ gửi tài liệu nội bộ hoặc cấp quyền vào tài khoản cá nhân; không biến thành lời mời xem tài liệu đám mây hay nhờ mua quà",
    "dang_ky_cong_doan_phuc_loi": "giả danh đại diện công đoàn thông báo đăng ký phúc lợi nội bộ, dẫn đến biểu mẫu đòi dữ liệu nhạy cảm hoặc khoản phí bất thường; không phải khảo sát nhận quà",
    "mua_ban_thanh_ly_noi_bo": "giả danh nhân viên đăng bán thanh lý thiết bị trong nhóm công ty hoặc danh sách email nội bộ, lợi dụng niềm tin đồng nghiệp và thúc ép đặt cọc trước khi xác minh người bán, quyền sở hữu và hàng hóa; không phải thiết bị bỏ quên, quà tặng hay bán hàng do lãnh đạo chỉ đạo",
    "nho_mua_the_qua_tang": "một đồng nghiệp ngang cấp hoặc người quen (KHÔNG phải lãnh đạo cấp cao) nhắn từ tài khoản chat mới, nhờ mua hộ thẻ quà tặng hoặc chuyển tiền gấp và hứa hoàn lại sau",
    "gia_danh_co_quan_nha_nuoc": "người tự xưng cán bộ công an / thuế / bảo hiểm xã hội thông báo hồ sơ của người học có vấn đề pháp lý, yêu cầu cung cấp thông tin hoặc chuyển tiền để 'xác minh, giải quyết'",
    "giao_hang_phi_theo_doi": "thông báo bưu kiện/đơn hàng đang chờ giao, yêu cầu trả một khoản phí giao hàng hoặc hải quan nhỏ qua liên kết theo dõi",
    "nha_tuyen_dung_doi_tac": "nhà tuyển dụng hoặc đối tác chủ động mời hợp tác, gửi file 'mô tả công việc / bài test' hoặc đòi thông tin cá nhân",
    "dich_vu_dam_may_tai_lieu": "thông báo có tài liệu được chia sẻ hoặc cần ký tài liệu, yêu cầu bấm vào và đăng nhập để xem",
    "ra_vao_van_phong": "người lạ xưng là giao hàng / kỹ thuật viên / khách xin đi theo qua cửa có kiểm soát ra vào, hoặc nhờ giữ cửa",
    "thiet_bi_ma_qr_la": "một thiết bị lưu trữ hoặc mã QR 'bị bỏ quên' ở nơi làm việc với nhãn hấp dẫn, khuyến khích người nhặt được cắm vào máy hoặc quét mã",
    "khao_sat_nhan_qua": "chương trình khảo sát / tri ân hứa quà tặng để đổi lấy thông tin hoặc mã xác thực",
}

_OTHER_SOPHISTICATION = {
    "beginner": "dấu hiệu lộ rõ ngay lần đọc đầu (nguồn lạ, đòi hỏi bất thường, liên kết hoặc yêu cầu đáng ngờ).",
    "intermediate": "trông thuyết phục và chuyên nghiệp; dấu hiệu cần suy luận thêm (đề nghị làm ngoài quy trình, đòi thông tin quá sớm, viện cớ không thể xác nhận).",
    "advanced": "rất tự nhiên: kẻ tấn công biết thông tin thật về người học hoặc công ty, bắt chước đúng bối cảnh công việc, kết hợp nhiều cơ chế tâm lý.",
}

# Mốc đối chiếu cho từng bối cảnh (format string: dùng khóa trong dict names)
_OTHER_REFERENCE = {
    "dong_nghiep_nho_ho_tro": "người học có kênh liên hệ nội bộ đã lưu của đồng nghiệp; công ty chỉ cho chia sẻ tài liệu công việc với tài khoản công ty đã được phê duyệt, không cấp quyền cho tài khoản cá nhân",
    "dang_ky_cong_doan_phuc_loi": "chương trình phúc lợi được công bố trên cổng nội bộ đã biết; thông báo chính thức nêu rõ không thu phí đăng ký và không yêu cầu mật khẩu hoặc OTP; có đầu mối công đoàn trong danh bạ để xác minh độc lập",
    "mua_ban_thanh_ly_noi_bo": "nhóm mua bán nội bộ không xác thực danh tính hay bảo chứng giao dịch; người học có thể tra danh bạ để liên hệ nhân viên bằng kênh đã biết và kiểm tra trực tiếp hàng hóa trước khi thanh toán",
    "nho_mua_the_qua_tang": "người học đã lưu số/tài khoản chat thật của người đó từ trước, và công ty quy định nhân viên không nhờ nhau mua thẻ quà tặng hay chuyển tiền cá nhân qua chat",
    "gia_danh_co_quan_nha_nuoc": "cơ quan nhà nước chỉ làm việc bằng giấy mời/văn bản chính thức gửi đến cơ quan hoặc nơi cư trú, không giải quyết hồ sơ hay thu tiền qua điện thoại/tin nhắn, và người học không biết mình có vụ việc nào đang được xử lý",
    "giao_hang_phi_theo_doi": "{courier} chỉ gửi liên kết theo dõi từ tên miền {courier_domain} (liên kết đáng ngờ dùng {fake_courier}), phí vận chuyển đã trả lúc đặt hàng, và người học biết mình có đang chờ đơn hàng hay không",
    "nha_tuyen_dung_doi_tac": "người học không nộp hồ sơ cho vị trí này; email tuyển dụng chính thức của {partner} có đuôi @{partner_domain} (email đáng ngờ dùng @{fake_partner}); nhà tuyển dụng thật không đòi CCCD trước buổi phỏng vấn",
    "dich_vu_dam_may_tai_lieu": "công ty dùng {cloud}, địa chỉ đăng nhập chính thức là {cloud_domain} (liên kết đáng ngờ dùng {fake_cloud}); tài liệu công việc thường được chia sẻ qua kênh nội bộ quen thuộc",
    "ra_vao_van_phong": "quy định công ty: mọi khách và kỹ thuật viên phải đăng ký tại lễ tân và đeo thẻ khách; nhân viên không giữ cửa cho người không quẹt thẻ",
    "thiet_bi_ma_qr_la": "quy định công ty cấm cắm thiết bị lạ vào máy tính và cấm quét mã QR không rõ nguồn gốc; thiết bị nhặt được phải giao bộ phận ATTT",
    "khao_sat_nhan_qua": "công ty và đối tác không bao giờ yêu cầu mật khẩu hoặc mã OTP để nhận quà; mọi chương trình khảo sát chính thức đều được thông báo qua email nội bộ",
}

_OTHER_SAFE = {
    "dong_nghiep_nho_ho_tro": "không gửi tài liệu hoặc cấp quyền cho tài khoản cá nhân; xác minh với đồng nghiệp qua kênh nội bộ đã lưu, kiểm tra quyền truy cập theo quy định và báo cáo ATTT nếu có dấu hiệu giả danh.",
    "dang_ky_cong_doan_phuc_loi": "không nhập thông tin nhạy cảm, mật khẩu, OTP hay đóng phí qua thông báo; tự mở cổng nội bộ đã biết, liên hệ đầu mối công đoàn từ danh bạ và báo cáo ATTT.",
    "mua_ban_thanh_ly_noi_bo": "không chuyển tiền đặt cọc khi chưa xác minh; liên hệ người bán qua danh bạ nội bộ độc lập với bài đăng, kiểm tra hàng hóa và quyền sở hữu trước khi thanh toán; báo quản trị nhóm và ATTT về tài khoản giả mạo.",
    "nho_mua_the_qua_tang": "KHÔNG mua thẻ hay chuyển tiền; xác minh bằng cách gọi/nhắn qua số hoặc kênh đã lưu từ trước của người đó (không dùng tài khoản đang nhắn); đối chiếu quy định công ty; báo cáo ATTT và báo cho người bị giả mạo.",
    "gia_danh_co_quan_nha_nuoc": "ngắt cuộc gọi, không cung cấp thông tin hay chuyển tiền; xác minh trực tiếp tại cơ quan hoặc qua số tổng đài niêm yết chính thức; báo cáo ATTT và người thân/đồng nghiệp.",
    "giao_hang_phi_theo_doi": "không bấm liên kết, không nhập thông tin thẻ; kiểm tra đơn hàng trong ứng dụng/trang chính thức của đơn vị vận chuyển (mở bằng địa chỉ đã biết); báo cáo ATTT.",
    "nha_tuyen_dung_doi_tac": "không mở file, không bấm liên kết, không gửi giấy tờ cá nhân; xác minh nhà tuyển dụng qua kênh chính thức của công ty đó; báo cáo ATTT.",
    "dich_vu_dam_may_tai_lieu": "không đăng nhập qua liên kết; mở dịch vụ bằng địa chỉ đã biết để kiểm tra tài liệu; xác nhận với người gửi qua kênh khác; báo cáo ATTT.",
    "ra_vao_van_phong": "không giữ cửa; mời người đó đăng ký tại lễ tân hoặc gọi bảo vệ/người phụ trách để xác nhận lịch hẹn; báo cáo bảo vệ/ATTT.",
    "thiet_bi_ma_qr_la": "không cắm thiết bị, không quét mã; giao thiết bị cho bộ phận ATTT/quản trị và báo vị trí nhặt được.",
    "khao_sat_nhan_qua": "không cung cấp thông tin hay mã xác thực; xác minh chương trình qua kênh nội bộ chính thức; báo cáo ATTT.",
}


def _other_channel(params: ScenarioParams) -> str:
    atk, ctx = params.attack_type.value, params.business_context.value
    if atk == "vishing":
        return "phone_call"
    if atk == "smishing":
        return "sms"
    if atk == "chat_impersonation":
        return "chat"
    if atk in ("tailgating", "baiting", "quishing"):
        return "in_person"
    if atk == "quid_pro_quo":
        return "in_person" if ctx == "ra_vao_van_phong" else "email"
    return "email"


def _brief_other(params: ScenarioParams, names: dict) -> str:
    ctx = params.business_context.value
    other_library = _format_library(params, "other")
    channel = _other_channel(params)
    level = params.difficulty_level.value
    company, person_main = names["company"], names["person_main"]
    reference_line = _OTHER_REFERENCE[ctx].format(**names)
    return f"""
BRIEF TÌNH HUỐNG (bắt buộc — đây là nhóm "Khác: tình huống mới", KHÁC HẲN ba nhóm huấn luyện chính):
- Người học là một nhân viên của {company}. Kẻ tấn công ({person_main}) hành động theo bối cảnh dưới đây.
  TUYỆT ĐỐI KHÔNG viết thành giả danh lãnh đạo qua email, giả danh IT/Helpdesk hay giả danh ngân hàng theo
  mẫu quen thuộc.
- Kênh: "{channel}" — {_CHANNEL_FORMAT_HINT[channel]} Trường "channel" trong output PHẢI là "{channel}".
- Cớ tiếp cận (theo bối cảnh): {_OTHER_PRETEXT[ctx]}.
- Độ tinh vi theo độ khó "{level}": {_OTHER_SOPHISTICATION[level]}
- Mốc tham khảo (chỉ chọn dữ kiện đáp án/lời giải cần): {reference_line}.
  Chỉ nêu dữ kiện liên quan ở vị trí cần thiết, không chép toàn bộ vào mở đầu.
- THƯ VIỆN DẤU HIỆU của nhóm này (red_flags chỉ chọn trong thư viện này, diễn đạt lại theo narrative, chỉ
  chọn dấu hiệu THỰC SỰ được cài trong narrative, và gán tier đúng như dưới đây):
{other_library}
- Hành vi an toàn đầy đủ (dùng cho nguyên tắc Lớp 3 và Lớp 2): {_OTHER_SAFE[ctx]}
"""


# ---------------------------------------------------------------------------
# THƯ VIỆN DẤU HIỆU (red flags) theo nhóm kịch bản — MỘT NGUỒN DUY NHẤT, lấy từ tài liệu luận văn
# (mục 3.3.2 / 3.4.2 / 3.5.2). Dùng cho 2 việc: (1) hiển thị trong brief để LLM chọn red_flags;
# (2) bốc NGẪU NHIÊN đáp án đúng của câu Phần I (thay vì để LLM tự chọn — LLM luôn chọn dấu hiệu
# quen thuộc nhất là "tên miền khác").
# Mỗi phần tử: (nội dung, kênh áp dụng | None = mọi kênh, bối cảnh áp dụng | None = mọi bối cảnh)
# ---------------------------------------------------------------------------
_EMAIL = ("email",)
_EMAIL_SMS = ("email", "sms")

_RED_FLAG_LIBRARY: dict[str, dict[str, list[tuple]]] = {
    "leader": {
        "co_ban": [
            ("yêu cầu chuyển tiền/đổi tài khoản khẩn cấp (kèm số tiền cụ thể)", None, None),
            ("tên miền/email người gửi gần giống nhưng không đúng nội bộ", _EMAIL, None),
            ("lỗi chính tả hoặc văn phong lạ so với lãnh đạo", None, None),
            ("yêu cầu giữ bí mật, không trao đổi với người khác", None, None),
        ],
        "trung_binh": [
            ("yêu cầu bỏ qua hoặc đi tắt quy trình phê duyệt", None, None),
            ("thời điểm gửi bất thường (cuối giờ, cuối tuần, sát giờ đóng cửa ngân hàng)", None, None),
            ("nhà cung cấp mới hoặc thay đổi tài khoản đột ngột vào phút chót", None, None),
            ("số tiền sát ngưỡng phê duyệt", None, None),
        ],
        "nang_cao": [
            ("chuỗi email giả lập có vẻ hợp lý (Re:/Fwd: với đồng nghiệp)", _EMAIL, None),
            ("văn phong rất tự nhiên, dùng đúng thuật ngữ/tên dự án nội bộ", None, None),
            ("kết hợp nhiều nguyên tắc tâm lý cùng lúc (quyền lực + khẩn cấp + bí mật)", None, None),
            ("đề nghị xác minh/liên hệ qua kênh không chính thống (email cá nhân, chat riêng, số di động lạ)", None, None),
        ],
    },
    "it": {
        "co_ban": [
            ("yêu cầu đổi mật khẩu/xác minh tài khoản khẩn cấp", _EMAIL_SMS, ("reset_mat_khau", "canh_bao_bao_mat_tai_khoan", "hop_thu_day_hoac_het_han")),
            ("tên miền/email người gửi gần giống nhưng không đúng nội bộ", _EMAIL, None),
            ("liên kết không khớp cổng nội bộ", _EMAIL_SMS, None),
            ("ngôn ngữ đe dọa, gây áp lực (\"24 giờ\", \"bị khóa\")", None, None),
        ],
        "trung_binh": [
            ("đòi mật khẩu hoặc mã MFA/OTP qua email, tin nhắn hoặc cuộc gọi", None, ("reset_mat_khau", "canh_bao_bao_mat_tai_khoan", "ho_tro_ky_thuat_tu_xa", "hop_thu_day_hoac_het_han", "xac_nhan_dang_nhap_mfa")),
            ("đòi cài phần mềm điều khiển từ xa ngoài quy trình ticket", None, ("ho_tro_ky_thuat_tu_xa",)),
            ("liên hệ ngoài giờ hoặc khi không có yêu cầu hỗ trợ trước đó", None, None),
            ("biểu mẫu đòi nhập tên đăng nhập và mật khẩu hiện tại", _EMAIL_SMS, ("reset_mat_khau", "canh_bao_bao_mat_tai_khoan", "hop_thu_day_hoac_het_han")),
        ],
        "nang_cao": [
            ("người gọi/gửi biết thông tin nội bộ (tên phòng ban, phần mềm đang dùng)", None, None),
            ("số gọi hoặc email giả mạo giống nội bộ", None, None),
            ("kết hợp nhiều cơ chế tâm lý (quyền lực + khẩn cấp + sợ mất dữ liệu)", None, None),
            ("đề nghị trao đổi ngoài kênh chính thống (chat cá nhân, số di động)", None, None),
        ],
    },
    "it_reverse": {  # người học là IT Helpdesk, kẻ tấn công giả danh nhân viên/lãnh đạo
        "co_ban": [
            ("áp lực gấp, nhấn mạnh phải làm ngay", None, None),
            ("địa chỉ gửi hoặc số gọi lạ, không phải nội bộ", None, None),
            ("người yêu cầu từ chối xác minh danh tính", None, None),
        ],
        "trung_binh": [
            ("đòi gửi mật khẩu hoặc mã qua email/chat", None, None),
            ("đòi bỏ qua việc tạo ticket", None, None),
            ("viện cớ không thể gọi điện hoặc không thể tự xử lý", None, None),
        ],
        "nang_cao": [
            ("biết thông tin nội bộ hoặc bối cảnh dự án thật", None, None),
            ("kết hợp quyền lực + khẩn cấp + bí mật", None, None),
        ],
    },
    "bank": {
        "co_ban": [
            ("yêu cầu xác minh/cập nhật khẩn cấp", _EMAIL_SMS, None),
            ("tên miền/email người gửi gần giống ngân hàng nhưng không đúng chính thức", _EMAIL, None),
            ("liên kết không khớp website chính thức của ngân hàng", _EMAIL_SMS, None),
            ("ngôn ngữ đe dọa, gây áp lực (\"24 giờ\", \"bị khóa\", \"mất tiền\")", None, None),
        ],
        "trung_binh": [
            ("đòi thông tin cá nhân nhạy cảm (CMND/CCCD, mật khẩu, số thẻ) qua email hoặc biểu mẫu", _EMAIL_SMS, None),
            ("đòi mã OTP/MFA qua điện thoại hoặc tin nhắn", None, None),
            ("liên hệ ngoài giờ hoặc khi không có giao dịch nào gần đây", None, None),
            ("biểu mẫu đòi nhiều thông tin định danh", _EMAIL_SMS, ("xac_minh_giao_dich_ngan_hang", "cap_nhat_thong_tin_ekyc", "the_tai_khoan_bi_khoa")),
        ],
        "nang_cao": [
            ("người gửi/gọi biết một số thông tin cơ bản về tài khoản (tên ngân hàng, 4 số cuối)", None, None),
            ("số gọi hoặc email giả mạo giống kênh chính thức của ngân hàng", None, None),
            ("kết hợp nhiều cơ chế tâm lý (quyền lực nhân viên ngân hàng + khẩn cấp + sợ mất tiền + giữ bí mật)", None, None),
            ("đề nghị trao đổi ngoài kênh chính thức (chat cá nhân, số di động)", None, None),
        ],
    },
}

# --- Bổ sung cho các bối cảnh IT / ngân hàng mới. NỘI DUNG DƯỚI ĐÂY KHÔNG CÓ TRONG LUẬN VĂN (mục 3.4.2/3.5.2
#     chỉ phủ 3 bối cảnh IT và 1 bối cảnh ngân hàng) — soạn từ kiến thức chung, cần rà soát trước khi trích.
_RED_FLAG_LIBRARY["it"]["co_ban"] += [
    ("thông báo hộp thư đầy hoặc mật khẩu sắp hết hạn kèm hạn chót gấp", _EMAIL_SMS, ("hop_thu_day_hoac_het_han",)),
    ("yêu cầu cài đặt khẩn cấp 'bản vá bắt buộc' kèm đe dọa hậu quả", None, ("cai_phan_mem_ban_va",)),
    ("yêu cầu xác nhận một lần đăng nhập mà người học không hề thực hiện", None, ("xac_nhan_dang_nhap_mfa",)),
]
_RED_FLAG_LIBRARY["it"]["trung_binh"] += [
    ("đòi cài phần mềm/bản vá từ liên kết hoặc file đính kèm, ngoài kênh phân phối nội bộ", None, ("cai_phan_mem_ban_va",)),
    ("đòi đọc mã MFA hoặc bấm 'chấp nhận' thông báo xác thực", None, ("xac_nhan_dang_nhap_mfa",)),
]
_RED_FLAG_LIBRARY["it"]["nang_cao"] += [
    ("tên và phiên bản phần mềm khớp đúng phần mềm công ty đang dùng", None, ("cai_phan_mem_ban_va",)),
    ("dồn dập nhiều thông báo xác nhận liên tục để gây mệt mỏi và buộc chấp nhận", None, ("xac_nhan_dang_nhap_mfa",)),
]
_RED_FLAG_LIBRARY["bank"]["co_ban"] += [
    ("yêu cầu cập nhật thông tin theo 'quy định mới' kèm hạn chót", None, ("cap_nhat_thong_tin_ekyc",)),
    ("thông báo thẻ hoặc tài khoản bị khóa, yêu cầu mở khóa gấp", None, ("the_tai_khoan_bi_khoa",)),
    ("ưu đãi/hoàn tiền/nâng hạn mức hấp dẫn mà người học không hề đăng ký", None, ("uu_dai_hoan_tien_han_muc",)),
    ("yêu cầu cập nhật hoặc kích hoạt lại ứng dụng qua liên kết lạ", _EMAIL_SMS, ("cap_nhat_ung_dung_smart_otp",)),
]
_RED_FLAG_LIBRARY["bank"]["trung_binh"] += [
    ("đòi ảnh chụp CCCD và ảnh chân dung qua liên kết ngoài ứng dụng ngân hàng", _EMAIL_SMS, ("cap_nhat_thong_tin_ekyc",)),
    ("đòi nhập số thẻ, ngày hết hạn và mã CVV để 'mở khóa'", None, ("the_tai_khoan_bi_khoa",)),
    ("đòi phí nhỏ hoặc thông tin thẻ trước khi 'nhận ưu đãi'", None, ("uu_dai_hoan_tien_han_muc",)),
    ("đòi cài ứng dụng ngoài kho ứng dụng chính thức hoặc cấp quyền đặc biệt cho ứng dụng", None, ("cap_nhat_ung_dung_smart_otp",)),
]
_RED_FLAG_LIBRARY["bank"]["nang_cao"] += [
    ("đòi mã kích hoạt Smart OTP hoặc mã xác thực thiết bị mới", None, ("cap_nhat_ung_dung_smart_otp",)),
]

# Nhóm "Khác" (tình huống mới — dùng cho Phần IV). Cùng ghi chú: soạn từ kiến thức chung, cần rà soát.
_G, _GOV, _DEL, _REC, _CLD, _PHY, _BAIT, _SUR = (
    ("nho_mua_the_qua_tang",), ("gia_danh_co_quan_nha_nuoc",), ("giao_hang_phi_theo_doi",),
    ("nha_tuyen_dung_doi_tac",), ("dich_vu_dam_may_tai_lieu",), ("ra_vao_van_phong",),
    ("thiet_bi_ma_qr_la",), ("khao_sat_nhan_qua",),
)
_RED_FLAG_LIBRARY["other"] = {
    "co_ban": [
        ("nhờ gửi tài liệu nội bộ hoặc cấp quyền cho tài khoản cá nhân", None, ("dong_nghiep_nho_ho_tro",)),
        ("tài khoản lạ tự xưng đồng nghiệp để nhờ hỗ trợ", None, ("dong_nghiep_nho_ho_tro",)),
        ("đòi mật khẩu hoặc OTP trong biểu mẫu đăng ký phúc lợi", None, ("dang_ky_cong_doan_phuc_loi",)),
        ("thu phí đăng ký dù thông báo phúc lợi chính thức nói miễn phí", None, ("dang_ky_cong_doan_phuc_loi",)),
        ("thúc ép chuyển tiền đặt cọc trước khi kiểm tra hàng thanh lý", None, ("mua_ban_thanh_ly_noi_bo",)),
        ("giá thanh lý thấp bất thường so với tình trạng thiết bị được mô tả", None, ("mua_ban_thanh_ly_noi_bo",)),
        ("áp lực thời gian, nhấn mạnh phải làm ngay", None, None),
        ("tài khoản chat hoặc số điện thoại mới/lạ nhưng xưng là người quen hay đồng nghiệp", None, _G),
        ("nhờ mua thẻ quà tặng hoặc chuyển tiền gấp và hứa hoàn lại sau", None, _G),
        ("đe dọa trách nhiệm pháp lý hoặc xử phạt nếu không làm ngay", None, _GOV),
        ("yêu cầu chuyển tiền hoặc cung cấp thông tin cá nhân qua điện thoại/tin nhắn", None, _GOV),
        ("đòi trả phí giao hàng hoặc phí hải quan qua liên kết", _EMAIL_SMS, _DEL),
        ("liên kết theo dõi đơn hàng không thuộc tên miền của đơn vị vận chuyển", _EMAIL_SMS, _DEL),
        ("cơ hội hoặc mức lương hấp dẫn bất thường, người lạ chủ động tiếp cận", None, _REC),
        ("yêu cầu mở file đính kèm hoặc tải bài test không rõ nguồn gốc", None, _REC),
        ("thông báo có tài liệu được chia sẻ hoặc cần ký từ người gửi không quen", None, _CLD),
        ("liên kết dẫn tới trang đăng nhập không thuộc dịch vụ chính thức", _EMAIL, _CLD),
        ("người lạ không có thẻ ra vào nhờ giữ cửa hoặc đi theo vào", None, _PHY),
        ("xưng là giao hàng/kỹ thuật viên/khách nhưng không có lịch hẹn", None, _PHY),
        ("thiết bị lưu trữ bị bỏ quên có nhãn hấp dẫn (ví dụ 'Lương', 'Bí mật')", None, _BAIT),
        ("mã QR dán ở nơi công cộng hoặc trong văn phòng không rõ nguồn gốc", None, _BAIT),
        ("hứa quà hoặc phần thưởng để đổi lấy thông tin", None, _SUR),
        ("khảo sát đòi thông tin cá nhân hoặc thông tin tài khoản", None, _SUR),
    ],
    "trung_binh": [
        ("đề nghị chuyển sang kênh khác hoặc làm ngoài quy trình thông thường", None, None),
        ("viện cớ mất quyền truy cập để bỏ qua quy trình chia sẻ tài liệu", None, ("dong_nghiep_nho_ho_tro",)),
        ("từ chối xác nhận qua kênh nội bộ đã biết của đồng nghiệp", None, ("dong_nghiep_nho_ho_tro",)),
        ("biểu mẫu phúc lợi yêu cầu dữ liệu nhạy cảm không liên quan quyền lợi", None, ("dang_ky_cong_doan_phuc_loi",)),
        ("yêu cầu đóng phí phúc lợi vào tài khoản cá nhân ngoài quy trình", None, ("dang_ky_cong_doan_phuc_loi",)),
        ("người bán từ chối cho kiểm tra hàng hoặc xác minh qua danh bạ nội bộ", None, ("mua_ban_thanh_ly_noi_bo",)),
        ("lấy lý do nhiều người đang chờ mua để yêu cầu bỏ qua xác minh", None, ("mua_ban_thanh_ly_noi_bo",)),
        ("viện cớ không nghe máy được để người học không thể xác nhận", None, _G),
        ("yêu cầu gửi mã thẻ quà tặng thay vì chuyển khoản thông thường", None, _G),
        ("yêu cầu giữ bí mật vụ việc, không báo cho người thân hay cơ quan", None, _GOV),
        ("yêu cầu cài ứng dụng hoặc truy cập 'cổng dịch vụ' không phải kênh chính thức của cơ quan", None, _GOV),
        ("đơn hàng mà người học không đặt hoặc không nhớ", None, _DEL),
        ("trang thanh toán đòi nhập thông tin thẻ để trả một khoản phí nhỏ", _EMAIL_SMS, _DEL),
        ("yêu cầu chuyển sang ứng dụng chat khác hoặc bấm liên kết ngoài nền tảng", None, _REC),
        ("đòi thông tin cá nhân/CCCD quá sớm, trước cả buổi phỏng vấn", None, _REC),
        ("trang đăng nhập đòi mật khẩu chỉ để xem tài liệu", None, _CLD),
        ("tài liệu chia sẻ không đúng bối cảnh công việc hiện tại", None, _CLD),
        ("không muốn hoặc không thể đăng ký tại quầy lễ tân", None, _PHY),
        ("viện cớ khẩn cấp (tay đầy đồ, sắp trễ họp) để được bỏ qua kiểm soát ra vào", None, _PHY),
        ("khuyến khích cắm thiết bị vào máy công ty để 'tìm chủ nhân'", None, _BAIT),
        ("mã QR dẫn tới trang đòi thông tin đăng nhập", None, _BAIT),
        ("đòi thông tin đăng nhập hoặc mã OTP để 'nhận quà'", None, _SUR),
        ("thời hạn nhận quà rất gấp", None, _SUR),
    ],
    "nang_cao": [
        ("kết hợp nhiều cơ chế tâm lý cùng lúc", None, None),
        ("biết đúng dự án nhưng yêu cầu cấp quyền tài liệu ra ngoài phạm vi được phê duyệt", None, ("dong_nghiep_nho_ho_tro",)),
        ("dùng đúng tên chương trình phúc lợi nhưng hướng dẫn đăng ký khác thông báo trên cổng nội bộ", None, ("dang_ky_cong_doan_phuc_loi",)),
        ("dùng hồ sơ nhân viên có vẻ hợp lệ để khiến người mua bỏ qua việc xác minh tài khoản nhận cọc", None, ("mua_ban_thanh_ly_noi_bo",)),
        ("biết thông tin cá nhân hoặc công việc của người học lấy từ mạng xã hội", None, _G),
        ("tin nhắn nối tiếp một cuộc trò chuyện thật trước đó", None, _G),
        ("đọc đúng họ tên và thông tin hồ sơ của người học", None, _GOV),
        ("nhiều 'cán bộ' lần lượt tiếp quản cuộc gọi để tăng độ tin cậy", None, _GOV),
        ("mã vận đơn và tên người nhận khớp một đơn hàng thật vừa đặt", None, _DEL),
        ("trang thanh toán giống hệt giao diện đơn vị vận chuyển", _EMAIL, _DEL),
        ("hồ sơ nhà tuyển dụng và công ty trông thật, có nhiều kết nối chung", None, _REC),
        ("tên file bài test có đuôi kép gây nhầm lẫn", None, _REC),
        ("gửi từ tài khoản đồng nghiệp đã bị chiếm quyền, nối tiếp chuỗi hội thoại thật", None, _CLD),
        ("tiêu đề và nội dung khớp dự án đang chạy", None, _CLD),
        ("trang phục và thẻ trông hợp lệ", None, _PHY),
        ("nêu đúng tên nhân viên hoặc phòng ban nội bộ", None, _PHY),
        ("thiết bị hoặc tem QR trông giống tài sản hợp lệ của công ty (logo, nhãn nội bộ)", None, _BAIT),
        ("đặt đúng chỗ nhiều người qua lại (máy in, phòng họp)", None, _BAIT),
        ("nhân danh một phòng ban hoặc đối tác có thật của công ty", None, _SUR),
        ("phần quà giá trị nhỏ, hợp lý nên dễ hạ cảnh giác", None, _SUR),
    ],
}

# Tier đủ điều kiện làm ĐÁP ÁN theo độ khó: beginner -> cơ bản; intermediate -> cơ bản + trung bình;
# advanced -> trung bình + nâng cao. Nếu nhóm quá ít lựa chọn (<3, vd kênh gọi điện) thì mở rộng sang tier kế.
_TIER_ORDER = {
    "beginner": ["co_ban", "trung_binh", "nang_cao"],
    "intermediate": ["co_ban", "trung_binh", "nang_cao"],
    "advanced": ["trung_binh", "nang_cao", "co_ban"],
}
_TIER_PRIMARY_COUNT = {"beginner": 1, "intermediate": 2, "advanced": 2}


def _active_group(params: ScenarioParams) -> str | None:
    """Nhóm kịch bản đang áp dụng, lấy trực tiếp từ lựa chọn "Nhóm kịch bản" của người dùng
    (kèm guard: bối cảnh phải có dữ liệu brief). None = không có brief."""
    ctx = params.business_context.value
    group = _GROUP_KEYS[params.scenario_group.value]
    if group == "leader" and ctx in _LEADER_PRETEXT:
        return "leader"
    if group == "it" and ctx in _IT_CONTEXTS:
        return "it"
    if group == "bank" and ctx in _BANK_PRETEXT:
        return "bank"
    if group == "other" and ctx in _OTHER_PRETEXT:
        return "other"
    return None


def _library_key(params: ScenarioParams) -> str | None:
    group = _active_group(params)
    if group == "it" and params.learner_role.value == "it_helpdesk":
        return "it_reverse"
    return group


def _group_channel(params: ScenarioParams, key: str) -> str:
    if key == "leader":
        return "email"
    if key == "it":
        return _it_channel(params)
    if key == "bank":
        return _bank_channel(params)
    if key == "other":
        return _other_channel(params)
    return "email"  # it_reverse: các dấu hiệu không phụ thuộc kênh


def _library_for(params: ScenarioParams, key: str) -> dict[str, list[str]]:
    """Thư viện dấu hiệu đã lọc theo KÊNH và BỐI CẢNH của bài này (bỏ dấu hiệu không áp dụng được)."""
    channel, ctx = _group_channel(params, key), params.business_context.value
    out: dict[str, list[str]] = {}
    for tier, items in _RED_FLAG_LIBRARY[key].items():
        out[tier] = [t for (t, chs, ctxs) in items
                     if (chs is None or channel in chs) and (ctxs is None or ctx in ctxs)]
    return out


def _format_library(params: ScenarioParams, key: str) -> str:
    lib = _library_for(params, key)
    return "\n".join(f"    {tier}: " + "; ".join(lib[tier]) + "."
                     for tier in ("co_ban", "trung_binh", "nang_cao") if lib[tier])


def _pick_target_flag(params: ScenarioParams) -> tuple[str, str] | None:
    """Bốc NGẪU NHIÊN 1 dấu hiệu làm đáp án đúng cho câu Phần I -> (nội dung, tier).
    Trả None nếu bài không thuộc nhóm nào (vd tailgating/quid_pro_quo): khi đó không ép đáp án."""
    key = _library_key(params)
    if key is None:
        return None
    lib = _library_for(params, key)
    diff = params.difficulty_level.value
    if diff == "advanced" and params.red_flags_required == 1:
        tiers = ["nang_cao"]  # chỉ có 1 red flag mà bài nâng cao phải có dấu hiệu nâng cao
    else:
        order, k = _TIER_ORDER[diff], _TIER_PRIMARY_COUNT[diff]
        tiers = order[:k]
        while sum(len(lib[t]) for t in tiers) < 3 and k < len(order):
            k += 1
            tiers = order[:k]
    pool = [(text, tier) for tier in tiers for text in lib[tier]]
    if not pool:
        return None
    return random.Random(f"{params.scenario_id}:target").choice(pool)


def _target_flag_block(target: tuple[str, str] | None) -> str:
    if target is None:
        return ""
    text, tier = target
    return f"""
- ĐÁP ÁN ĐÚNG CỦA CÂU NÀY ĐÃ ĐƯỢC CHỌN NGẪU NHIÊN — bắt buộc bám theo, KHÔNG tự đổi sang dấu hiệu khác:
    "{text}"  (tier: {tier})
  + Narrative phải cài dấu hiệu này một cách tự nhiên; option đúng (is_safe_choice=true) phải diễn đạt
    CHÍNH dấu hiệu này; red_flags ở Lớp 2 phải có dấu hiệu này (gán tier "{tier}").
  + KHÔNG mặc định chọn "tên miền người gửi khác tên miền chính thức" làm đáp án nếu đó không phải dấu hiệu
    đã chọn ở trên. Nếu narrative vẫn chứa các dấu hiệu khác (ví dụ email gửi từ tên miền giả mạo), các
    dấu hiệu đó KHÔNG được xuất hiện trong bất kỳ option nào.
  + Nếu dấu hiệu này cần mốc đối chiếu (tên miền chính thức, văn phong thường ngày của người gửi, giờ làm
    việc thông thường, ngưỡng phê duyệt, quy trình thanh toán/hỗ trợ...), narrative PHẢI cung cấp đúng mốc
    cần thiết ở vị trí liên quan, ngắn gọn và trung tính. Với tên miền nội bộ, dùng dòng Từ/Đến;
    không bắt buộc viết thêm câu dẫn ở mở đầu. Với ngưỡng phê duyệt, số tiền phải khớp điều kiện vi phạm.
"""


_GROUP_KEYS = {
    "gia_danh_lanh_dao": "leader",
    "gia_danh_it": "it",
    "gia_danh_ngan_hang": "bank",
    "tinh_huong_khac": "other",
}


def _scenario_brief(params: ScenarioParams, names: dict) -> str:
    group = _active_group(params)
    if group == "leader":
        return _brief_leader(params, names)
    if group == "it":
        return _brief_it(params, names)
    if group == "bank":
        return _brief_bank(params, names)
    if group == "other":
        return _brief_other(params, names)
    return ""


def build_user_prompt(params: ScenarioParams) -> str:
    payload = {
        "scenario_id": params.scenario_id,
        "attack_type": params.attack_type.value,
        "learner_role": params.learner_role.value,
        "business_context": params.business_context.value,
        "manipulation_mechanism": params.manipulation_mechanism.value,
        "difficulty_level": params.difficulty_level.value,
        "competency_group": params.competency_group.value,
        "scenario_group": params.scenario_group.value,
        "red_flags_required": params.red_flags_required,
        "language": params.language,
    }

    specific_instructions = _INSTRUCTION_BUILDERS[params.competency_group.value](params)
    names = _pick_names(params)
    names_block = _fictional_names_block(params, names)
    brief = _scenario_brief(params, names)

    instructions = (
        "Hãy soạn MỘT bài tập tình huống 3 lớp (Challenge/Explanation/Transferable Knowledge) "
        "về nhận diện social engineering dựa trên tham số JSON dưới đây.\n"
        f"{_learner_role_block(params)}\n"
        f"{brief}\n"
        f"{specific_instructions}\n"
        f"{names_block}\n"
        "Trường 'primary_competency' trong output PHẢI đúng bằng giá trị 'competency_group' cho "
        "dưới đây. Trả lời DUY NHẤT bằng JSON đúng schema đã nêu trong system prompt.\n\n"
        f"Tham số:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return instructions


def build_messages(params: ScenarioParams) -> list[dict]:
    return [{"role": "user", "content": build_user_prompt(params)}]

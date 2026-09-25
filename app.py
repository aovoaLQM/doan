"""
app.py
-------
Giao diện web (Streamlit), 3 tab:
  Tab 1: Sinh kịch bản — chọn tham số qua dropdown, gọi pipeline [1]->[4].
  Tab 2: Duyệt kịch bản — Human review gate [5], chuyên gia duyệt/từ chối.
  Tab 3: Học viên làm bài — luồng 3 lớp Challenge -> Explanation -> Transferable
         Knowledge; đáp án/giải thích CHỈ hiện ra SAU khi học viên đã chọn.

Chạy:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from schema_builder import (
    AttackType,
    LearnerRole,
    BusinessContext,
    ManipulationMechanism,
    DifficultyLevel,
    _RED_FLAG_BOUNDS,
)
from pipeline import run_pipeline
from review import review_store

LABELS = {
    AttackType: {
        "phishing_email": "Phishing qua email",
        "vishing": "Vishing (điện thoại)",
        "smishing": "Smishing (SMS)",
        "bec": "BEC (giả mạo email lãnh đạo)",
        "pretexting": "Pretexting (giả danh)",
        "tailgating": "Tailgating (bám đuôi ra vào)",
        "quid_pro_quo": "Quid pro quo (đổi chác lợi ích)",
    },
    LearnerRole: {
        "nhan_vien_ke_toan": "Nhân viên kế toán",
        "it_helpdesk": "IT Helpdesk",
        "quan_ly_cap_trung": "Quản lý cấp trung",
        "le_tan": "Lễ tân",
        "nhan_vien_moi": "Nhân viên mới",
        "nhan_vien_hr": "Nhân viên HR",
        "nhan_vien_van_phong": "Nhân viên văn phòng (chung)",
    },
    BusinessContext: {
        "chuyen_khoan_khan": "Chuyển khoản khẩn",
        "reset_mat_khau": "Reset mật khẩu",
        "ky_hop_dong": "Ký hợp đồng",
        "xu_ly_hoa_don": "Xử lý hóa đơn",
        "tuyen_dung": "Tuyển dụng",
        "onboard_nha_cung_cap": "Onboard nhà cung cấp",
        "canh_bao_bao_mat_tai_khoan": "Cảnh báo bảo mật tài khoản",
        "ho_tro_ky_thuat_tu_xa": "Hỗ trợ kỹ thuật từ xa",
        "xac_minh_giao_dich_ngan_hang": "Xác minh giao dịch ngân hàng",
    },
    ManipulationMechanism: {
        "authority": "Authority (quyền lực/chức vụ)",
        "urgency": "Urgency (khẩn cấp)",
        "scarcity": "Scarcity (khan hiếm)",
        "social_proof": "Social proof (số đông)",
        "familiarity_liking": "Familiarity/Liking (thiện cảm)",
        "fear_intimidation": "Fear/Intimidation (sợ hãi)",
    },
    DifficultyLevel: {
        "beginner": "Beginner (cơ bản)",
        "intermediate": "Intermediate (trung bình)",
        "advanced": "Advanced (nâng cao)",
    },
}

# Nhãn hiển thị cho tier của từng red flag — dùng chung cho cả admin preview và learner view
TIER_LABELS = {
    "co_ban": "🟢 Cơ bản",
    "trung_binh": "🟡 Trung bình",
    "nang_cao": "🔴 Nâng cao",
}


def select_enum(enum_cls, label: str, key: str) -> str:
    options = list(enum_cls)
    display_labels = [LABELS[enum_cls][o.value] for o in options]
    choice = st.selectbox(label, display_labels, key=key)
    idx = display_labels.index(choice)
    return options[idx].value


# ---------------------------------------------------------------------------
# Tab 1 — Sinh kịch bản
# ---------------------------------------------------------------------------

def render_generate_tab() -> None:
    st.subheader("Sinh kịch bản đào tạo (3 lớp)")

    col1, col2 = st.columns(2)
    with col1:
        attack_type = select_enum(AttackType, "Loại tấn công", "attack_type")
        business_context = select_enum(BusinessContext, "Bối cảnh nghiệp vụ", "business_context")
        difficulty_level = select_enum(DifficultyLevel, "Cấp độ khó", "difficulty_level")
    with col2:
        learner_role = select_enum(LearnerRole, "Vai trò người học", "learner_role")
        manipulation_mechanism = select_enum(ManipulationMechanism, "Cơ chế thao túng tâm lý", "manipulation_mechanism")

    lo, hi = _RED_FLAG_BOUNDS[DifficultyLevel(difficulty_level)]
    red_flags_required = st.slider(f"Số lượng red flags ({lo}-{hi})", min_value=lo, max_value=hi, value=lo)

    if st.button("🚀 Sinh kịch bản", type="primary"):
        with st.spinner("Đang gọi LLM để sinh bài tập 3 lớp..."):
            outcome = run_pipeline(
                attack_type=attack_type,
                learner_role=learner_role,
                business_context=business_context,
                manipulation_mechanism=manipulation_mechanism,
                difficulty_level=difficulty_level,
                red_flags_required=red_flags_required,
            )
        render_generation_result(outcome)


def render_generation_result(outcome) -> None:
    payload = outcome.to_review_payload()
    status = payload["status"]

    if status == "input_rejected":
        st.error(f"Tham số đầu vào không hợp lệ: {payload['error_message']}")
        return
    if status == "llm_error":
        st.error(f"Lỗi khi gọi LLM: {payload['error_message']}")
        return
    if status == "validation_failed":
        st.warning("Bài tập KHÔNG đạt kiểm tra an toàn/schema — không đưa vào hàng đợi duyệt.")
        for issue in payload["validation_issues"]:
            icon = "🔴" if issue["severity"] == "error" else "🟡"
            st.write(f"{icon} **{issue['field']}**: {issue['message']}")
        return

    review_store.save_pipeline_outcome(payload)
    st.success("Bài tập đạt kiểm tra tự động — đã vào hàng đợi chờ duyệt (tab 'Duyệt kịch bản').")
    render_admin_preview(payload["llm_output"], payload["validation_issues"], key_prefix=f"gen_{payload['scenario_id']}")


def render_admin_preview(llm_output: dict, issues: list, key_prefix: str) -> None:
    """Xem trước ĐẦY ĐỦ cả 3 lớp — dùng cho người sinh/người duyệt, KHÔNG dùng cho học viên."""
    st.markdown(f"### {llm_output['title']}")
    st.caption(f"Kênh: {llm_output['channel']} · Độ khó: {llm_output['difficulty_level']}")

    l1 = llm_output["layer1_challenge"]
    st.markdown("**Lớp 1 — Challenge**")
    st.text_area("Narrative", l1["narrative"], height=200, disabled=True, key=f"narrative_{key_prefix}")
    st.write(f"Câu hỏi: {l1['decision_prompt']}")
    for opt in l1["options"]:
        tag = "✅ AN TOÀN" if opt["is_safe_choice"] else f"⚠️ score={opt['score']}"
        st.write(f"- **{opt['option_id']}**. {opt['text']}  _{tag}_")

    l2 = llm_output["layer2_explanation"]
    st.markdown("**Lớp 2 — Explanation**")
    for fb in l2["option_feedback"]:
        st.write(f"- **{fb['option_id']}**: {fb['explanation']}")
    st.markdown("Red flags:")
    for rf in l2["red_flags"]:
        tier = TIER_LABELS.get(rf.get("tier"), "")
        st.write(f"- {tier} **{rf['flag']}** — {rf['explanation']}")

    l3 = llm_output["layer3_transferable_knowledge"]
    st.markdown("**Lớp 3 — Transferable Knowledge**")
    st.write(f"Nguyên tắc: {l3['principle']}")
    st.write(f"Áp dụng cho: {', '.join(l3['applicable_situations'])}")
    st.write(f"Lời khuyên: {l3['general_advice']}")

    if issues:
        st.markdown("**Cảnh báo (warning):**")
        for issue in issues:
            st.write(f"🟡 {issue['field']}: {issue['message']}")


# ---------------------------------------------------------------------------
# Tab 2 — Duyệt kịch bản (Human review gate)
# ---------------------------------------------------------------------------

def render_review_tab() -> None:
    st.subheader("Hàng đợi chờ duyệt")

    pending = review_store.list_pending()
    if not pending:
        st.info("Không có bài tập nào đang chờ duyệt.")
    else:
        for item in pending:
            with st.expander(f"{item.llm_output['title']}  ·  tạo lúc {item.created_at}", expanded=False):
                render_admin_preview(item.llm_output, item.validation_issues, key_prefix=f"review_{item.scenario_id}")

                reviewer_name = st.text_input("Tên người duyệt", key=f"reviewer_{item.scenario_id}")
                review_note = st.text_area("Ghi chú (tùy chọn)", key=f"note_{item.scenario_id}", height=80)

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Duyệt (Approve)", key=f"approve_{item.scenario_id}"):
                        if not reviewer_name.strip():
                            st.error("Vui lòng nhập tên người duyệt.")
                        else:
                            review_store.record_decision(item.scenario_id, "approved", reviewer_name, review_note)
                            st.success("Đã duyệt.")
                            st.rerun()
                with c2:
                    if st.button("❌ Từ chối (Reject)", key=f"reject_{item.scenario_id}"):
                        if not reviewer_name.strip():
                            st.error("Vui lòng nhập tên người duyệt.")
                        else:
                            review_store.record_decision(item.scenario_id, "rejected", reviewer_name, review_note)
                            st.warning("Đã từ chối.")
                            st.rerun()

    st.divider()
    st.subheader("Lịch sử đã duyệt (audit log)")
    reviewed = review_store.list_reviewed()
    if not reviewed:
        st.caption("Chưa có bài tập nào được duyệt.")
    else:
        for item in reviewed:
            icon = "✅" if item.review_decision == "approved" else "❌"
            title = item.llm_output["title"] if item.llm_output else item.scenario_id
            st.write(f"{icon} **{title}** — {item.review_decision} bởi {item.reviewer_name} lúc {item.reviewed_at}")
            if item.review_note:
                st.caption(f"Ghi chú: {item.review_note}")


# ---------------------------------------------------------------------------
# Tab 3 — Học viên làm bài (luồng 3 lớp thật sự, ẩn đáp án cho tới khi chọn)
# ---------------------------------------------------------------------------

def render_learner_tab() -> None:
    st.subheader("Làm bài đánh giá nhận diện Social Engineering")

    approved = review_store.list_approved_scenarios()
    if not approved:
        st.info("Chưa có bài tập nào được duyệt để đưa vào luyện tập.")
        return

    learner_name = st.text_input("Tên học viên", key="learner_name")
    titles = [s.llm_output["title"] for s in approved]
    chosen_title = st.selectbox("Chọn bài tập", titles, key="learner_scenario_choice")
    scenario = approved[titles.index(chosen_title)]
    sid = scenario.scenario_id
    llm_output = scenario.llm_output
    l1 = llm_output["layer1_challenge"]

    answered_key = f"answered_{sid}"
    chosen_key = f"chosen_{sid}"

    st.markdown("---")
    st.markdown(f"### {llm_output['title']}")
    st.caption(f"Kênh: {llm_output['channel']} · Độ khó: {llm_output['difficulty_level']}")

    st.markdown("#### 🎯 Lớp 1 — Tình huống")
    st.text_area("", l1["narrative"], height=220, disabled=True, key=f"learner_narrative_{sid}")
    st.write(f"**{l1['decision_prompt']}**")

    option_labels = [f"{opt['option_id']}. {opt['text']}" for opt in l1["options"]]

    if not st.session_state.get(answered_key, False):
        picked = st.radio("Chọn hành động của bạn:", option_labels, key=f"radio_{sid}", index=None)

        if st.button("Xác nhận câu trả lời", key=f"submit_{sid}", disabled=(picked is None)):
            if not learner_name.strip():
                st.error("Vui lòng nhập tên học viên trước khi nộp bài.")
            else:
                chosen_option_id = picked.split(".")[0]
                st.session_state[answered_key] = True
                st.session_state[chosen_key] = chosen_option_id
                st.rerun()
    else:
        chosen_option_id = st.session_state[chosen_key]
        chosen_opt = next(o for o in l1["options"] if o["option_id"] == chosen_option_id)

        recorded_key = f"recorded_{sid}"
        if not st.session_state.get(recorded_key, False):
            review_store.record_attempt(
                scenario_id=sid,
                learner_name=learner_name.strip() or "(chưa đặt tên)",
                chosen_option_id=chosen_option_id,
                is_safe_choice=chosen_opt["is_safe_choice"],
                score=int(chosen_opt["score"]),
            )
            st.session_state[recorded_key] = True

        if chosen_opt["is_safe_choice"]:
            st.success(f"Bạn chọn: {chosen_option_id}. {chosen_opt['text']}  →  Điểm: {chosen_opt['score']}/100 ✅")
        elif chosen_opt["score"] >= 40:
            st.warning(f"Bạn chọn: {chosen_option_id}. {chosen_opt['text']}  →  Điểm: {chosen_opt['score']}/100 ⚠️")
        else:
            st.error(f"Bạn chọn: {chosen_option_id}. {chosen_opt['text']}  →  Điểm: {chosen_opt['score']}/100 ❌")

        l2 = llm_output["layer2_explanation"]
        st.markdown("#### 📖 Lớp 2 — Giải thích")
        for fb in l2["option_feedback"]:
            marker = "👉 " if fb["option_id"] == chosen_option_id else "• "
            st.write(f"{marker}**{fb['option_id']}**: {fb['explanation']}")

        st.markdown("**Các dấu hiệu nhận biết (red flags) trong tình huống này:**")
        for rf in l2["red_flags"]:
            tier = TIER_LABELS.get(rf.get("tier"), "")
            st.write(f"- {tier} **{rf['flag']}** — {rf['explanation']}")

        l3 = llm_output["layer3_transferable_knowledge"]
        st.markdown("#### 🧠 Lớp 3 — Nguyên tắc chuyển giao")
        st.info(l3["principle"])
        st.write(f"**Áp dụng được cho:** {', '.join(l3['applicable_situations'])}")
        st.write(f"**Ghi nhớ:** {l3['general_advice']}")

        if st.button("Làm bài tập khác", key=f"reset_{sid}"):
            st.session_state[answered_key] = False
            st.session_state[recorded_key] = False
            st.rerun()

    if learner_name.strip():
        st.divider()
        summary = review_store.get_learner_summary(learner_name.strip())
        if summary["count"] > 0:
            st.markdown("#### 📊 Kết quả luyện tập của bạn")
            c1, c2, c3 = st.columns(3)
            c1.metric("Số bài đã làm", summary["count"])
            c2.metric("Điểm trung bình", summary["average_score"])
            c3.metric("Tỷ lệ chọn an toàn", f"{summary['safe_choice_rate']}%")


def main() -> None:
    st.set_page_config(page_title="SE Training Scenario Generator", layout="wide")
    st.title("🎯 Công cụ đào tạo nhận diện Social Engineering")

    tab1, tab2, tab3 = st.tabs(["🛠️ Sinh kịch bản", "📋 Duyệt kịch bản", "🎓 Học viên làm bài"])
    with tab1:
        render_generate_tab()
    with tab2:
        render_review_tab()
    with tab3:
        render_learner_tab()


if __name__ == "__main__":
    main()
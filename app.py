"""
app.py — 3 tab: Sinh kịch bản / Duyệt kịch bản / (Học viên làm bài - đã ẩn).
Chạy: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from schema_builder import (
    AttackType,
    LearnerRole,
    BusinessContext,
    ManipulationMechanism,
    DifficultyLevel,
    CompetencyGroup,
    ScenarioGroup,
    allowed_groups,
    allowed_contexts,
    allowed_attacks,
    _RED_FLAG_BOUNDS,
)
from pipeline import run_pipeline
from review import review_store

LABELS = {
    AttackType: {
        "phishing_email": "Phishing qua email (IT / ngân hàng)",
        "vishing": "Vishing - điện thoại (IT / ngân hàng)",
        "smishing": "Smishing - SMS (IT / ngân hàng)",
        "bec": "BEC (giả danh lãnh đạo)",
        "pretexting": "Pretexting (giả danh IT/Helpdesk)",
        "tailgating": "Tailgating (bám đuôi ra vào)",
        "quid_pro_quo": "Quid pro quo (đổi chác lợi ích)",
    },
    LearnerRole: {
        "nhan_vien_ke_toan": "Nhân viên kế toán",
        "it_helpdesk": "IT Helpdesk (người học là nhân viên IT)",
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
    CompetencyGroup: {
        "nhan_dien_dau_hieu": "Nhận diện dấu hiệu cảnh báo",
        "nhan_biet_co_che_thao_tung": "Nhận biết cơ chế thao túng tâm lý",
        "lua_chon_hanh_vi_ung_pho": "Lựa chọn hành vi ứng phó",
        "van_dung_nguyen_tac": "Vận dụng nguyên tắc phòng vệ",
    },
}

LABELS[AttackType].update({
    "phishing_email": "Phishing qua email",
    "vishing": "Vishing (điện thoại)",
    "smishing": "Smishing (SMS)",
    "bec": "BEC (email giả danh lãnh đạo)",
    "pretexting": "Pretexting (giả danh IT/Helpdesk)",
    "tailgating": "Tailgating (bám đuôi ra vào)",
    "quid_pro_quo": "Quid pro quo (đổi chác lợi ích)",
    "chat_impersonation": "Giả danh qua chat / mạng xã hội",
    "quishing": "Quishing (mã QR giả)",
    "baiting": "Baiting (vật mồi: USB, thiết bị bỏ quên)",
})
LABELS[BusinessContext].update({
    "hop_thu_day_hoac_het_han": "Hộp thư đầy / mật khẩu hết hạn",
    "cai_phan_mem_ban_va": "Cài phần mềm / bản vá bắt buộc",
    "xac_nhan_dang_nhap_mfa": "Xác nhận đăng nhập (MFA)",
    "cap_nhat_thong_tin_ekyc": "Cập nhật thông tin khách hàng / eKYC",
    "huy_giao_dich_doc_otp": "Hủy giao dịch (đòi đọc OTP)",
    "the_tai_khoan_bi_khoa": "Thẻ / tài khoản bị khóa",
    "uu_dai_hoan_tien_han_muc": "Ưu đãi / hoàn tiền / nâng hạn mức",
    "cap_nhat_ung_dung_smart_otp": "Cập nhật / kích hoạt ứng dụng, Smart OTP",
    "nho_mua_the_qua_tang": "Nhờ mua thẻ quà tặng / chuyển tiền hộ",
    "gia_danh_co_quan_nha_nuoc": "Giả danh cơ quan nhà nước",
    "giao_hang_phi_theo_doi": "Giao hàng: phí / liên kết theo dõi",
    "nha_tuyen_dung_doi_tac": "Nhà tuyển dụng / đối tác (file, bài test)",
    "dich_vu_dam_may_tai_lieu": "Dịch vụ đám mây: chia sẻ / ký tài liệu",
    "ra_vao_van_phong": "Ra vào văn phòng (tailgating)",
    "thiet_bi_ma_qr_la": "Thiết bị / mã QR lạ",
    "khao_sat_nhan_qua": "Khảo sát nhận quà",
})
LABELS[ScenarioGroup] = {
    "gia_danh_lanh_dao": "Giả danh lãnh đạo (CEO Fraud / BEC)",
    "gia_danh_it": "Giả danh IT / Helpdesk",
    "gia_danh_ngan_hang": "Giả danh ngân hàng",
    "tinh_huong_khac": "Khác: tình huống mới",
}

TIER_LABELS = {
    "co_ban": "🟢 Cơ bản",
    "trung_binh": "🟡 Trung bình",
    "nang_cao": "🔴 Nâng cao",
}


def select_enum(enum_cls, label: str, key: str, allowed=None) -> str:
    options = list(allowed) if allowed is not None else list(enum_cls)
    display_labels = [LABELS[enum_cls][o.value] for o in options]
    choice = st.selectbox(label, display_labels, key=key)
    idx = display_labels.index(choice)
    return options[idx].value


def render_generate_tab() -> None:
    st.subheader("Sinh kịch bản đào tạo (3 lớp)")

    # Bố cục được tạo trước theo thứ tự HIỂN THỊ; các ô được gọi theo thứ tự PHỤ THUỘC:
    #   Nhóm năng lực -> Nhóm kịch bản -> Bối cảnh -> Loại tấn công (kênh/kỹ thuật)
    r1c1, r1c2 = st.columns(2)   # Nhóm kịch bản | Bối cảnh nghiệp vụ
    r2c1, r2c2 = st.columns(2)   # Loại tấn công | Vai trò người học
    r3c1, r3c2 = st.columns(2)   # Cấp độ khó    | Nhóm năng lực
    r4c1, _ = st.columns(2)      # Cơ chế thao túng tâm lý

    with r3c2:
        competency_group = select_enum(CompetencyGroup, "Nhóm năng lực", "competency_group")
    comp = CompetencyGroup(competency_group)

    with r1c1:
        scenario_group = select_enum(
            ScenarioGroup, "Nhóm kịch bản", f"scenario_group_{competency_group}",
            allowed=allowed_groups(comp),
        )
    group = ScenarioGroup(scenario_group)

    with r1c2:
        business_context = select_enum(
            BusinessContext, "Bối cảnh nghiệp vụ", f"business_context_{scenario_group}",
            allowed=allowed_contexts(group),
        )
    with r2c1:
        attack_type = select_enum(
            AttackType, "Loại tấn công (kênh / kỹ thuật)", f"attack_type_{business_context}",
            allowed=allowed_attacks(BusinessContext(business_context)),
        )
    with r2c2:
        learner_role = select_enum(LearnerRole, "Vai trò người học", "learner_role")
    with r3c1:
        difficulty_level = select_enum(DifficultyLevel, "Cấp độ khó", "difficulty_level")
    with r4c1:
        manipulation_mechanism = select_enum(ManipulationMechanism, "Cơ chế thao túng tâm lý", "manipulation_mechanism")

    if comp == CompetencyGroup.PRINCIPLE_APPLICATION:
        st.caption("Phần IV (vận dụng nguyên tắc, tình huống chưa huấn luyện trực tiếp) chỉ dùng nhóm kịch bản \"Khác\".")
    else:
        st.caption("Phần I–III dùng 3 nhóm huấn luyện chính. Nhóm \"Khác\" dành cho Phần IV.")

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
                competency_group=competency_group,
                scenario_group=scenario_group,
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
    st.markdown(f"### {llm_output['title']}")
    competency_label = LABELS[CompetencyGroup].get(llm_output.get("primary_competency"), "")
    st.caption(f"Kênh: {llm_output['channel']} · Độ khó: {llm_output['difficulty_level']} · Nhóm năng lực: {competency_label}")

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


def render_preview_test_tab() -> None:
    """Preview Test — làm thử bài kiểm tra theo luồng 3 lớp trên các kịch bản ĐÃ DUYỆT.
    Đáp án/giải thích chỉ hiện SAU khi chọn và xác nhận."""
    st.subheader("Preview Test")
    st.caption("Làm thử các bài đã được duyệt đúng như học viên sẽ thấy: chọn đáp án trước, "
               "điểm và giải thích chỉ hiện sau khi xác nhận.")

    approved = review_store.list_approved_scenarios()
    if not approved:
        st.info("Chưa có bài tập nào được duyệt. Hãy duyệt ít nhất một kịch bản ở tab 'Duyệt kịch bản'.")
        return

    learner_name = st.text_input("Tên người làm thử", key="preview_learner_name")

    # Nhãn chọn bài: tiêu đề + nhóm năng lực; kèm 8 ký tự đầu scenario_id để tránh trùng tiêu đề
    def _label(s) -> str:
        comp = LABELS[CompetencyGroup].get(s.llm_output.get("primary_competency"), "")
        return f"{s.llm_output['title']} — {comp} [{s.scenario_id[:8]}]"

    labels = [_label(s) for s in approved]
    chosen_label = st.selectbox("Chọn bài kiểm tra", labels, key="preview_scenario_choice")
    scenario = approved[labels.index(chosen_label)]
    sid = scenario.scenario_id
    llm_output = scenario.llm_output
    l1 = llm_output["layer1_challenge"]

    answered_key = f"preview_answered_{sid}"
    chosen_key = f"preview_chosen_{sid}"
    recorded_key = f"preview_recorded_{sid}"

    st.markdown("---")
    st.markdown(f"### {llm_output['title']}")
    comp_label = LABELS[CompetencyGroup].get(llm_output.get("primary_competency"), "")
    st.caption(f"Kênh: {llm_output['channel']} · Độ khó: {llm_output['difficulty_level']} · Nhóm năng lực: {comp_label}")

    # LỚP 1 — chỉ hiện tình huống + câu hỏi + các lựa chọn (KHÔNG hiện is_safe_choice/score)
    st.markdown("#### 🎯 Lớp 1 — Tình huống")
    st.text_area("Tình huống", l1["narrative"], height=220, disabled=True,
                 key=f"preview_narrative_{sid}", label_visibility="collapsed")
    st.write(f"**{l1['decision_prompt']}**")

    # Ánh xạ nhãn hiển thị -> option_id bằng dict (không tách chuỗi, tránh lỗi khi id/nội dung chứa dấu chấm)
    label_to_id = {f"{opt['option_id']}. {opt['text']}": opt["option_id"] for opt in l1["options"]}

    if not st.session_state.get(answered_key, False):
        picked = st.radio("Chọn đáp án của bạn:", list(label_to_id.keys()),
                          key=f"preview_radio_{sid}", index=None)
        if st.button("Xác nhận câu trả lời", key=f"preview_submit_{sid}", disabled=(picked is None)):
            if not learner_name.strip():
                st.error("Vui lòng nhập tên người làm thử trước khi nộp bài.")
            else:
                st.session_state[answered_key] = True
                st.session_state[chosen_key] = label_to_id[picked]
                st.rerun()
        return

    # ---- Đã trả lời: chấm điểm + hiện Lớp 2, Lớp 3 ----
    chosen_option_id = st.session_state[chosen_key]
    chosen_opt = next(o for o in l1["options"] if o["option_id"] == chosen_option_id)

    # Ghi nhận lượt làm bài đúng 1 lần (Streamlit rerun nhiều lần, tránh ghi trùng)
    if not st.session_state.get(recorded_key, False):
        review_store.record_attempt(
            scenario_id=sid,
            learner_name=learner_name.strip() or "(chưa đặt tên)",
            chosen_option_id=chosen_option_id,
            is_safe_choice=chosen_opt["is_safe_choice"],
            score=int(chosen_opt["score"]),
        )
        st.session_state[recorded_key] = True

    result_text = f"Bạn chọn: {chosen_option_id}. {chosen_opt['text']}  →  Điểm: {chosen_opt['score']}/100"
    if chosen_opt["is_safe_choice"]:
        st.success(result_text + " ✅")
    elif chosen_opt["score"] >= 40:
        st.warning(result_text + " ⚠️")
    else:
        st.error(result_text + " ❌")

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

    if st.button("Làm lại bài này", key=f"preview_reset_{sid}"):
        st.session_state[answered_key] = False
        st.session_state[recorded_key] = False
        st.rerun()

    if learner_name.strip():
        summary = review_store.get_learner_summary(learner_name.strip())
        if summary["count"] > 0:
            st.divider()
            st.markdown("#### 📊 Kết quả làm thử của bạn")
            c1, c2, c3 = st.columns(3)
            c1.metric("Số bài đã làm", summary["count"])
            c2.metric("Điểm trung bình", summary["average_score"])
            c3.metric("Tỷ lệ chọn đáp án đúng", f"{summary['safe_choice_rate']}%")


def main() -> None:
    st.set_page_config(page_title="SE Training Scenario Generator", layout="wide")
    st.title("🎯 Công cụ đào tạo nhận diện Social Engineering")

    tab1, tab2, tab3 = st.tabs(["🛠️ Sinh kịch bản", "📋 Duyệt kịch bản", "🧪 Preview Test"])
    with tab1:
        render_generate_tab()
    with tab2:
        render_review_tab()
    with tab3:
        render_preview_test_tab()


if __name__ == "__main__":
    main()
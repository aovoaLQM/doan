from unittest.mock import patch
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pipeline import PipelineOutcome
from schema_builder import BusinessContext, ScenarioGroup, allowed_contexts, allowed_attacks


def test_part_ii_bec_to_it_and_generation():
    # Error outcome exercises button feedback without an API call or database writes.
    with patch("pipeline.run_pipeline", return_value=PipelineOutcome(
        status="llm_error", error_message="TEST_FEEDBACK"
    )) as run:
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
        app.selectbox(key="competency_group").select("nhan_biet_co_che_thao_tung").run()
        assert app.selectbox(key="attack_type").value == "bec"
        app.selectbox(key="scenario_group").select("gia_danh_it").run()
        for context in allowed_contexts(ScenarioGroup.IT):
            app.selectbox(key="business_context").select(context.value).run()
            attacks = allowed_attacks(context)
            assert app.selectbox(key="attack_type").value == attacks[0].value
            app.selectbox(key="attack_type").select(attacks[-1].value).run()
            next(button for button in app.button if "Sinh" in button.label).click().run()
            assert not app.exception
            assert any("TEST_FEEDBACK" in error.value for error in app.error)
            assert run.call_args.kwargs["business_context"] == context.value
            assert run.call_args.kwargs["attack_type"] == attacks[-1].value
            assert run.call_args.kwargs["competency_group"] == "nhan_biet_co_che_thao_tung"
        app.selectbox(key="scenario_group").select("gia_danh_lanh_dao").run()
        assert app.selectbox(key="business_context").value == BusinessContext.URGENT_TRANSFER.value
        assert app.selectbox(key="attack_type").value == "bec"
        app.selectbox(key="competency_group").select("van_dung_nguyen_tac").run()
        app.selectbox(key="scenario_group").select("tinh_huong_khac").run()
        app.selectbox(key="competency_group").select("nhan_biet_co_che_thao_tung").run()
        assert app.selectbox(key="scenario_group").value != "tinh_huong_khac"
        assert not app.exception

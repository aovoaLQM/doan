from unittest.mock import patch
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_hidden_tabs_do_not_load_review_data():
    with (
        patch("review.review_store.list_pending", return_value=[]) as pending,
        patch("review.review_store.list_reviewed", return_value=[]) as reviewed,
        patch("review.review_store.list_approved_scenarios", return_value=[]) as approved,
        patch("pipeline.call_llm") as llm,
    ):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
        assert not app.exception
        app.selectbox(key="scenario_group").select_index(1).run()
        assert not app.exception
        pending.assert_not_called()
        reviewed.assert_not_called()
        approved.assert_not_called()
        llm.assert_not_called()

        app.session_state["main_tab"] = "📋 Duyệt kịch bản"
        app.run()
        assert not app.exception
        pending.assert_called_once()
        reviewed.assert_called_once()
        approved.assert_not_called()

        app.session_state["main_tab"] = "🧪 Preview Test"
        app.run()
        assert not app.exception
        approved.assert_called_once()
        llm.assert_not_called()

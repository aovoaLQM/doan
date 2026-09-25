"""
review/review_store.py
------------------------
Lưu trữ kết quả pipeline chờ duyệt + audit log quyết định của chuyên gia,
dùng SQLite (file, không cần cài server riêng).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "reviewed_scenarios.db"


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenarios (
            scenario_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            input_params TEXT NOT NULL,
            llm_output TEXT,
            validation_issues TEXT,
            pipeline_status TEXT NOT NULL,
            review_decision TEXT,          -- 'approved' | 'rejected' | NULL (chưa duyệt)
            reviewer_name TEXT,
            review_note TEXT,
            reviewed_at TEXT
        )
        """
    )
    return conn


@dataclass
class StoredScenario:
    scenario_id: str
    created_at: str
    input_params: dict
    llm_output: Optional[dict]
    validation_issues: list
    pipeline_status: str
    review_decision: Optional[str]
    reviewer_name: Optional[str]
    review_note: Optional[str]
    reviewed_at: Optional[str]


def save_pipeline_outcome(review_payload: dict) -> None:
    """Lưu một outcome từ pipeline.to_review_payload() vào DB, chờ duyệt."""
    conn = _get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO scenarios
            (scenario_id, created_at, input_params, llm_output, validation_issues, pipeline_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            review_payload["scenario_id"],
            datetime.now(timezone.utc).isoformat(),
            json.dumps(review_payload.get("input_params"), ensure_ascii=False),
            json.dumps(review_payload.get("llm_output"), ensure_ascii=False) if review_payload.get("llm_output") else None,
            json.dumps(review_payload.get("validation_issues"), ensure_ascii=False),
            review_payload["status"],
        ),
    )
    conn.commit()
    conn.close()


def list_pending() -> list[StoredScenario]:
    """Lấy các kịch bản đã qua validate (status=ready_for_review) và CHƯA có quyết định duyệt."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT scenario_id, created_at, input_params, llm_output, validation_issues,
               pipeline_status, review_decision, reviewer_name, review_note, reviewed_at
        FROM scenarios
        WHERE pipeline_status = 'ready_for_review' AND review_decision IS NULL
        ORDER BY created_at DESC
        """
    ).fetchall()
    conn.close()
    return [_row_to_scenario(r) for r in rows]


def list_reviewed(limit: int = 50) -> list[StoredScenario]:
    """Lấy lịch sử các kịch bản đã được duyệt (approved/rejected) — phục vụ audit log."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT scenario_id, created_at, input_params, llm_output, validation_issues,
               pipeline_status, review_decision, reviewer_name, review_note, reviewed_at
        FROM scenarios
        WHERE review_decision IS NOT NULL
        ORDER BY reviewed_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_scenario(r) for r in rows]


def record_decision(
    scenario_id: str,
    decision: str,  # "approved" | "rejected"
    reviewer_name: str,
    review_note: str = "",
) -> None:
    if decision not in ("approved", "rejected"):
        raise ValueError("decision phải là 'approved' hoặc 'rejected'")

    conn = _get_conn()
    conn.execute(
        """
        UPDATE scenarios
        SET review_decision = ?, reviewer_name = ?, review_note = ?, reviewed_at = ?
        WHERE scenario_id = ?
        """,
        (decision, reviewer_name, review_note, datetime.now(timezone.utc).isoformat(), scenario_id),
    )
    conn.commit()
    conn.close()


def _row_to_scenario(row: tuple) -> StoredScenario:
    (scenario_id, created_at, input_params, llm_output, validation_issues,
     pipeline_status, review_decision, reviewer_name, review_note, reviewed_at) = row
    return StoredScenario(
        scenario_id=scenario_id,
        created_at=created_at,
        input_params=json.loads(input_params),
        llm_output=json.loads(llm_output) if llm_output else None,
        validation_issues=json.loads(validation_issues) if validation_issues else [],
        pipeline_status=pipeline_status,
        review_decision=review_decision,
        reviewer_name=reviewer_name,
        review_note=review_note,
        reviewed_at=reviewed_at,
    )


# ---------------------------------------------------------------------------
# Learner attempts — ghi nhận lượt làm bài của học viên (Layer 1 -> điểm số)
# ---------------------------------------------------------------------------

def _ensure_attempts_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id TEXT NOT NULL,
            learner_name TEXT NOT NULL,
            chosen_option_id TEXT NOT NULL,
            is_safe_choice INTEGER NOT NULL,
            score INTEGER NOT NULL,
            submitted_at TEXT NOT NULL
        )
        """
    )


@dataclass
class Attempt:
    scenario_id: str
    learner_name: str
    chosen_option_id: str
    is_safe_choice: bool
    score: int
    submitted_at: str


def record_attempt(
    scenario_id: str,
    learner_name: str,
    chosen_option_id: str,
    is_safe_choice: bool,
    score: int,
) -> None:
    conn = _get_conn()
    _ensure_attempts_table(conn)
    conn.execute(
        """
        INSERT INTO attempts (scenario_id, learner_name, chosen_option_id, is_safe_choice, score, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (scenario_id, learner_name, chosen_option_id, int(is_safe_choice), score,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def list_attempts_for_learner(learner_name: str) -> list[Attempt]:
    conn = _get_conn()
    _ensure_attempts_table(conn)
    rows = conn.execute(
        """
        SELECT scenario_id, learner_name, chosen_option_id, is_safe_choice, score, submitted_at
        FROM attempts
        WHERE learner_name = ?
        ORDER BY submitted_at DESC
        """,
        (learner_name,),
    ).fetchall()
    conn.close()
    return [
        Attempt(scenario_id=r[0], learner_name=r[1], chosen_option_id=r[2],
                is_safe_choice=bool(r[3]), score=r[4], submitted_at=r[5])
        for r in rows
    ]


def get_learner_summary(learner_name: str) -> dict:
    attempts = list_attempts_for_learner(learner_name)
    if not attempts:
        return {"count": 0, "average_score": 0.0, "safe_choice_rate": 0.0}
    count = len(attempts)
    avg_score = sum(a.score for a in attempts) / count
    safe_rate = sum(1 for a in attempts if a.is_safe_choice) / count
    return {"count": count, "average_score": round(avg_score, 1), "safe_choice_rate": round(safe_rate * 100, 1)}


def list_approved_scenarios() -> list[StoredScenario]:
    """Lấy các kịch bản đã được chuyên gia DUYỆT (approved) — dùng cho học viên làm bài."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT scenario_id, created_at, input_params, llm_output, validation_issues,
               pipeline_status, review_decision, reviewer_name, review_note, reviewed_at
        FROM scenarios
        WHERE review_decision = 'approved'
        ORDER BY reviewed_at DESC
        """
    ).fetchall()
    conn.close()
    return [_row_to_scenario(r) for r in rows]
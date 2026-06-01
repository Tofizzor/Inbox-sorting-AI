"""Data access for messages, analyses, guide, and audit."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from models.classifier_models import EmailAnalysis, EmailInput, ExtractedFields

from db.database import db_session


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def record_audit(
    conn,
    *,
    entity_type: str,
    entity_id: Optional[str],
    action: str,
    actor: str = "system",
    payload: Optional[dict] = None,
) -> str:
    audit_id = _new_id()
    conn.execute(
        """
        INSERT INTO audit_events (id, entity_type, entity_id, action, actor, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            entity_type,
            entity_id,
            action,
            actor,
            json.dumps(payload) if payload is not None else None,
            _utc_now(),
        ),
    )
    return audit_id


def create_message(email: EmailInput, source: str = "api") -> str:
    message_id = _new_id()
    received_at = email.timestamp.isoformat() if email.timestamp else None
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO messages (id, subject, body, sender, received_at, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                email.subject,
                email.body,
                email.sender,
                received_at,
                source,
                _utc_now(),
            ),
        )
        record_audit(
            conn,
            entity_type="message",
            entity_id=message_id,
            action="ingested",
            payload={"source": source, "subject": email.subject},
        )
    return message_id


def save_analysis_attempt(
    message_id: str,
    attempt_number: int,
    raw_llm_response: Optional[str],
    error_type: str,
    error_detail: str,
) -> str:
    attempt_id = _new_id()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO analysis_attempts
            (id, message_id, attempt_number, raw_llm_response, error_type, error_detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                message_id,
                attempt_number,
                raw_llm_response,
                error_type,
                error_detail,
                _utc_now(),
            ),
        )
    return attempt_id


def save_analysis(
    message_id: str,
    analysis: EmailAnalysis,
    *,
    model_name: str,
    needs_review: bool,
    attempt_count: int,
) -> str:
    analysis_id = _new_id()
    extracted = analysis.extracted_fields.model_dump()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO analyses
            (id, message_id, category, priority, suggested_action, reason, destination,
             extracted_fields, model_name, needs_review, attempt_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                message_id,
                analysis.category.value,
                analysis.priority.value,
                analysis.suggested_action.value,
                analysis.reason,
                analysis.destination,
                json.dumps(extracted),
                model_name,
                1 if needs_review else 0,
                attempt_count,
                _utc_now(),
            ),
        )
        record_audit(
            conn,
            entity_type="message",
            entity_id=message_id,
            action="analyzed",
            payload={
                "analysis_id": analysis_id,
                "destination": analysis.destination,
                "category": analysis.category.value,
                "needs_review": needs_review,
            },
        )
    return analysis_id


def record_analyze_failed(message_id: str, detail: str, attempt_count: int) -> None:
    with db_session() as conn:
        record_audit(
            conn,
            entity_type="message",
            entity_id=message_id,
            action="analyze_failed",
            payload={"detail": detail, "attempt_count": attempt_count},
        )


def get_latest_analysis(conn, message_id: str) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT * FROM analyses
        WHERE message_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (message_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_analysis_dict(row)


def _row_to_analysis_dict(row) -> dict:
    return {
        "id": row["id"],
        "category": row["category"],
        "priority": row["priority"],
        "suggested_action": row["suggested_action"],
        "reason": row["reason"],
        "destination": row["destination"],
        "extracted_fields": json.loads(row["extracted_fields"]),
        "model_name": row["model_name"],
        "needs_review": bool(row["needs_review"]),
        "attempt_count": row["attempt_count"],
        "created_at": row["created_at"],
    }


def get_message_with_latest_analysis(message_id: str) -> Optional[dict]:
    with db_session() as conn:
        msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if msg is None:
            return None
        analysis = get_latest_analysis(conn, message_id)
        return {
            "id": msg["id"],
            "email": {
                "subject": msg["subject"],
                "body": msg["body"],
                "sender": msg["sender"],
                "received_at": msg["received_at"],
            },
            "source": msg["source"],
            "created_at": msg["created_at"],
            "analysis": analysis,
        }


def list_messages(limit: int = 50, offset: int = 0) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.subject, m.sender, m.source, m.created_at,
                   a.destination, a.priority, a.category, a.needs_review
            FROM messages m
            LEFT JOIN analyses a ON a.id = (
                SELECT id FROM analyses
                WHERE message_id = m.id
                ORDER BY created_at DESC
                LIMIT 1
            )
            ORDER BY m.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "subject": r["subject"],
                "sender": r["sender"],
                "source": r["source"],
                "created_at": r["created_at"],
                "destination": r["destination"],
                "priority": r["priority"],
                "category": r["category"],
                "needs_review": bool(r["needs_review"]) if r["needs_review"] is not None else None,
            }
            for r in rows
        ]


def get_guide_config() -> dict:
    with db_session() as conn:
        row = conn.execute("SELECT config FROM guide_config WHERE id = 1").fetchone()
        if row is None:
            from db.database import _seed_guide_if_empty

            _seed_guide_if_empty(conn)
            row = conn.execute("SELECT config FROM guide_config WHERE id = 1").fetchone()
        return json.loads(row["config"])


def update_guide_config(config: dict, updated_by: str = "user") -> dict:
    text = json.dumps(config, indent=2)
    with db_session() as conn:
        conn.execute(
            """
            UPDATE guide_config
            SET config = ?, updated_at = ?, updated_by = ?
            WHERE id = 1
            """,
            (text, _utc_now(), updated_by),
        )
        record_audit(
            conn,
            entity_type="guide",
            entity_id="1",
            action="guide_updated",
            actor=updated_by,
            payload={"schema_version": config.get("schema_version")},
        )
    return config


def get_message_audit(message_id: str) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, entity_type, entity_id, action, actor, payload, created_at
            FROM audit_events
            WHERE (entity_type = 'message' AND entity_id = ?)
               OR (entity_type = 'analysis' AND entity_id IN (
                    SELECT id FROM analyses WHERE message_id = ?
               ))
            ORDER BY created_at ASC
            """,
            (message_id, message_id),
        ).fetchall()
        attempts = conn.execute(
            """
            SELECT id, attempt_number, error_type, error_detail, created_at
            FROM analysis_attempts
            WHERE message_id = ?
            ORDER BY attempt_number ASC
            """,
            (message_id,),
        ).fetchall()
    events = [
        {
            "id": r["id"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "action": r["action"],
            "actor": r["actor"],
            "payload": json.loads(r["payload"]) if r["payload"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    for a in attempts:
        events.append(
            {
                "id": a["id"],
                "entity_type": "message",
                "entity_id": message_id,
                "action": "analysis_attempt_failed",
                "actor": "system",
                "payload": {
                    "attempt_number": a["attempt_number"],
                    "error_type": a["error_type"],
                    "error_detail": a["error_detail"],
                },
                "created_at": a["created_at"],
            }
        )
    events.sort(key=lambda e: e["created_at"])
    return events


def message_exists(message_id: str) -> bool:
    with db_session() as conn:
        row = conn.execute("SELECT 1 FROM messages WHERE id = ?", (message_id,)).fetchone()
        return row is not None

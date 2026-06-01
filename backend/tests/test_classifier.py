"""Unit tests for classifier, destination mapping, and repository."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from models.classifier_models import (
    Category,
    EmailInput,
    Priority,
    compute_destination,
)
from services.classifier import (
    AnalysisFailedError,
    parse_llm_response,
    to_email_analysis,
    validate_analysis,
)


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "phase_1_email_triage_examples.json"


def load_examples() -> list[dict]:
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)["examples"]


class TestParseLlmResponse:
    def test_plain_json(self):
        raw = '{"category": "human", "priority": "urgent_action", "suggested_action": "acknowledge", "reason": "test", "extracted_fields": {}}'
        data = parse_llm_response(raw)
        assert data["category"] == "human"

    def test_json_in_code_fence(self):
        raw = '```json\n{"category": "human", "priority": "urgent_action", "suggested_action": "acknowledge", "reason": "x", "extracted_fields": {}}\n```'
        data = parse_llm_response(raw)
        assert data["category"] == "human"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_llm_response("not json at all")


class TestValidateAnalysis:
    def test_valid_payload(self):
        data = {
            "category": "human",
            "priority": "urgent_action",
            "suggested_action": "acknowledge",
            "reason": "Trading issue reported.",
            "extracted_fields": {"order_ids": ["PUKOID123"]},
        }
        out = validate_analysis(data)
        analysis = to_email_analysis(out)
        assert analysis.destination == "urgent_human"
        assert analysis.extracted_fields.order_ids == ["PUKOID123"]

    def test_invalid_label_rejected(self):
        data = {
            "category": "not_a_label",
            "priority": "urgent_action",
            "suggested_action": "acknowledge",
            "reason": "x",
            "extracted_fields": {},
        }
        with pytest.raises(ValidationError):
            validate_analysis(data)


class TestComputeDestination:
    def test_urgent_human(self):
        assert compute_destination(Category.HUMAN, Priority.URGENT_ACTION) == "urgent_human"

    def test_spam(self):
        assert compute_destination(Category.SPAM, Priority.IGNORE) == "spam"

    def test_alerts_archive(self):
        assert (
            compute_destination(Category.MACHINE_GENERATED, Priority.IGNORE)
            == "alerts_archive"
        )


class TestRepository:
    def test_message_round_trip(self, monkeypatch):
        import db.database as database
        import db.repository as repo

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"

            def fake_path():
                return db_path

            monkeypatch.setattr(database, "get_database_path", fake_path)
            database.init_db()

            email = EmailInput(subject="Test", body="Body text")
            message_id = repo.create_message(email, source="test")
            assert repo.message_exists(message_id)

            detail = repo.get_message_with_latest_analysis(message_id)
            assert detail is not None
            assert detail["email"]["subject"] == "Test"


class TestAnalyzeEmailRetry:
    def test_retries_then_fails(self, monkeypatch):
        from services import classifier

        email = EmailInput(subject="S", body="B")
        calls = {"n": 0}

        def fake_llm(system, user):
            calls["n"] += 1
            return "not valid json"

        class FakeSettings:
            max_llm_retries = 2
            llm_model = "test"

        monkeypatch.setattr(classifier, "get_settings", lambda: FakeSettings())
        monkeypatch.setattr(classifier.llm_client, "call_llm", fake_llm)
        monkeypatch.setattr(
            classifier.repository,
            "save_analysis_attempt",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            classifier.repository,
            "record_analyze_failed",
            lambda *a, **k: None,
        )

        with pytest.raises(AnalysisFailedError):
            classifier.analyze_email(email, message_id="fake-id", persist=True)

        assert calls["n"] == 2

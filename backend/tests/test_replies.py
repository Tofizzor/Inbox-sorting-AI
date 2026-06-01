"""Phase 2 reply lifecycle + safety tests (offline, mock provider).

The headline invariant: nothing is sent without explicit human approval (HTTP 409).
"""

from fastapi.testclient import TestClient


def _ingest_and_analyze(client: TestClient) -> str:
    created = client.post(
        "/messages",
        json={"email": {"subject": "Order PUKOID123 stuck", "body": "POV order stopped trading."}},
    )
    assert created.status_code == 201
    message_id = created.json()["id"]

    analyzed = client.post(f"/messages/{message_id}/analyze")
    assert analyzed.status_code == 200
    return message_id


def _audit_actions(client: TestClient, message_id: str) -> list[str]:
    res = client.get(f"/messages/{message_id}/audit")
    assert res.status_code == 200
    return [e["action"] for e in res.json()]


def test_send_without_approval_returns_409(mock_client: TestClient):
    """Core safety invariant: a draft (or edited) reply cannot be sent."""
    message_id = _ingest_and_analyze(mock_client)

    draft = mock_client.post(f"/messages/{message_id}/draft-reply")
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"

    # Send straight from draft -> blocked.
    blocked = mock_client.post(f"/messages/{message_id}/reply/send")
    assert blocked.status_code == 409

    # Edit (still not approved) -> still blocked.
    edited = mock_client.patch(
        f"/messages/{message_id}/reply", json={"edited_text": "Edited but unapproved."}
    )
    assert edited.status_code == 200
    blocked_again = mock_client.post(f"/messages/{message_id}/reply/send")
    assert blocked_again.status_code == 409

    # Nothing was sent: status never became 'sent', no sent_at, no reply_sent audit.
    latest = mock_client.get(f"/messages/{message_id}/reply").json()
    assert latest["status"] == "edited"
    assert latest["sent_at"] is None
    assert "reply_sent" not in _audit_actions(mock_client, message_id)


def test_approve_then_send_transitions_to_sent_and_audits(mock_client: TestClient):
    message_id = _ingest_and_analyze(mock_client)
    mock_client.post(f"/messages/{message_id}/draft-reply")

    approved = mock_client.post(
        f"/messages/{message_id}/reply/approve", json={"approved_by": "alice"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "alice"

    sent = mock_client.post(f"/messages/{message_id}/reply/send", json={"actor": "alice"})
    assert sent.status_code == 200
    body = sent.json()
    assert body["status"] == "sent"
    assert body["sent_at"] is not None

    actions = _audit_actions(mock_client, message_id)
    for expected in ("draft_created", "reply_approved", "reply_sent"):
        assert expected in actions

    audit = mock_client.get(f"/messages/{message_id}/audit").json()
    sent_event = next(e for e in audit if e["action"] == "reply_sent")
    assert sent_event["actor"] == "alice"


def test_edit_updates_text_and_status(mock_client: TestClient):
    message_id = _ingest_and_analyze(mock_client)
    mock_client.post(f"/messages/{message_id}/draft-reply")

    new_text = "Hi, thanks for flagging order PUKOID123. We're investigating now."
    edited = mock_client.patch(
        f"/messages/{message_id}/reply",
        json={"edited_text": new_text, "editor": "bob"},
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["status"] == "edited"
    assert body["edited_text"] == new_text
    assert body["current_text"] == new_text
    assert "reply_edited" in _audit_actions(mock_client, message_id)


def test_edit_after_approve_reopens_and_blocks_send(mock_client: TestClient):
    """Editing an approved reply clears approval so it cannot be sent un-reviewed."""
    message_id = _ingest_and_analyze(mock_client)
    mock_client.post(f"/messages/{message_id}/draft-reply")
    mock_client.post(f"/messages/{message_id}/reply/approve")

    reopened = mock_client.patch(
        f"/messages/{message_id}/reply", json={"edited_text": "Changed after approval."}
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "edited"
    assert reopened.json()["approved_by"] is None

    blocked = mock_client.post(f"/messages/{message_id}/reply/send")
    assert blocked.status_code == 409


def test_regenerate_creates_new_unapproved_draft(mock_client: TestClient):
    """Approve a draft, then regenerate: the new latest reply is an unapproved draft."""
    message_id = _ingest_and_analyze(mock_client)
    first = mock_client.post(f"/messages/{message_id}/draft-reply").json()
    mock_client.post(f"/messages/{message_id}/reply/approve")

    second = mock_client.post(f"/messages/{message_id}/draft-reply").json()
    assert second["id"] != first["id"]
    assert second["status"] == "draft"

    latest = mock_client.get(f"/messages/{message_id}/reply").json()
    assert latest["id"] == second["id"]
    blocked = mock_client.post(f"/messages/{message_id}/reply/send")
    assert blocked.status_code == 409


def test_draft_requires_analysis_returns_409(mock_client: TestClient):
    created = mock_client.post(
        "/messages", json={"email": {"subject": "No analysis yet", "body": "Body"}}
    )
    message_id = created.json()["id"]

    res = mock_client.post(f"/messages/{message_id}/draft-reply")
    assert res.status_code == 409


def test_generation_failure_sets_needs_review_and_logs_attempt(
    mock_client: TestClient, monkeypatch
):
    """Invalid AI output must not persist a draft: flag needs_review + log attempts."""
    message_id = _ingest_and_analyze(mock_client)

    # Force the SECOND (reply) LLM call to return unparseable output for every attempt.
    monkeypatch.setattr("services.llm_client.call_llm", lambda system, user: "")

    res = mock_client.post(f"/messages/{message_id}/draft-reply")
    assert res.status_code == 422

    # No usable draft was persisted.
    assert mock_client.get(f"/messages/{message_id}/reply").status_code == 404

    # The analysis is flagged for human review.
    detail = mock_client.get(f"/messages/{message_id}").json()
    assert detail["analysis"]["needs_review"] is True

    # Attempts were logged and surfaced in the audit trail.
    actions = _audit_actions(mock_client, message_id)
    assert "reply_attempt_failed" in actions
    assert "reply_generation_failed" in actions


def test_get_reply_404_when_none(mock_client: TestClient):
    message_id = _ingest_and_analyze(mock_client)
    assert mock_client.get(f"/messages/{message_id}/reply").status_code == 404

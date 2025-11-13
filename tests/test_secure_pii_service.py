"""
Unit tests for the secure PII FastAPI service.
"""

from fastapi.testclient import TestClient

from secure_pii_service import app, pii_maps


client = TestClient(app)


def test_sanitize_and_rehydrate_round_trip() -> None:
    pii_maps.clear()
    session_id = "session-123"
    text = "John Doe met Alice Smith in Paris."

    sanitize_resp = client.post(
        "/sanitize",
        json={"session_id": session_id, "text": text},
        timeout=5,
    )
    assert sanitize_resp.status_code == 200
    body = sanitize_resp.json()
    assert body["session_id"] == session_id
    masked = body["masked_text"]
    assert "[PERSON_1]" in masked
    assert "[PERSON_2]" in masked

    rehydrate_resp = client.post(
        "/rehydrate",
        json={"session_id": session_id, "text": masked},
        timeout=5,
    )
    assert rehydrate_resp.status_code == 200
    rehydrated = rehydrate_resp.json()["rehydrated_text"]
    assert rehydrated == text


def test_rehydrate_unknown_session() -> None:
    pii_maps.clear()
    response = client.post(
        "/rehydrate",
        json={"session_id": "missing", "text": "Hi [PERSON_1]"},
        timeout=5,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session_id"

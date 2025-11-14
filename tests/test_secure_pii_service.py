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


def test_sanitize_is_idempotent_for_known_pii() -> None:
    pii_maps.clear()
    session_id = "session-repeat"
    text = "John Doe called John Doe again."

    first = client.post(
        "/sanitize", json={"session_id": session_id, "text": text}, timeout=5
    ).json()["masked_text"]
    second = client.post(
        "/sanitize", json={"session_id": session_id, "text": text}, timeout=5
    ).json()["masked_text"]

    assert first == second
    assert first.count("[PERSON_1]") == 2


def test_sanitize_without_detectable_pii_returns_original_text() -> None:
    pii_maps.clear()
    payload = {"session_id": "session-none", "text": "Nothing sensitive here."}
    response = client.post("/sanitize", json=payload, timeout=5)
    data = response.json()
    assert data["masked_text"] == payload["text"]
    assert data["replacements"] == {}


def test_session_isolation_between_clients() -> None:
    pii_maps.clear()
    first_masked = client.post(
        "/sanitize",
        json={"session_id": "session-a", "text": "John Doe works here."},
        timeout=5,
    ).json()["masked_text"]

    second_masked = client.post(
        "/sanitize",
        json={"session_id": "session-b", "text": "John Doe works here."},
        timeout=5,
    ).json()["masked_text"]

    assert first_masked == second_masked

    rehydrated_a = client.post(
        "/rehydrate",
        json={"session_id": "session-a", "text": first_masked},
        timeout=5,
    ).json()["rehydrated_text"]
    rehydrated_b = client.post(
        "/rehydrate",
        json={"session_id": "session-b", "text": second_masked},
        timeout=5,
    ).json()["rehydrated_text"]

    assert rehydrated_a == "John Doe works here."
    assert rehydrated_b == "John Doe works here."

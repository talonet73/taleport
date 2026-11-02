from fastapi.testclient import TestClient


def test_api_requires_session_token(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-TALeport-Token": "wrong"})
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "unauthorized", "params": {}}}

    assert client.get("/api/health").json()["ok"] is True


def test_token_accepted_as_query_param_for_event_stream(client: TestClient) -> None:
    del client.headers["X-TALeport-Token"]
    assert client.get("/api/health?t=test-token").status_code == 200


def test_non_loopback_host_is_rejected(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Host": "evil.example.com"})
    assert response.status_code == 403
    response = client.get("/", headers={"Host": "evil.example.com:80"})
    assert response.status_code == 403


def test_settings_roundtrip_and_validation_error(client: TestClient) -> None:
    assert client.get("/api/settings").json()["language"] == "it"

    response = client.patch("/api/settings", json={"language": "en", "default_ai": "ollama"})
    assert response.status_code == 200
    assert response.json()["language"] == "en"
    assert client.get("/api/settings").json()["default_ai"] == "ollama"

    response = client.patch("/api/settings", json={"scan_time": "7am"})
    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "settings.invalid", "params": {"fields": ["scan_time"]}}
    }


def test_secrets_api_never_returns_values(client: TestClient) -> None:
    assert client.put("/api/secrets/openai", json={"value": "sk-secret"}).status_code == 204
    status = client.get("/api/secrets").json()
    assert status["openai"] is True
    assert "sk-secret" not in str(status)

    assert client.delete("/api/secrets/openai").status_code == 204
    assert client.get("/api/secrets").json()["openai"] is False
    assert client.put("/api/secrets/nope", json={"value": "x"}).status_code == 404


def test_topics_api(client: TestClient) -> None:
    payload = {
        "name": "Test",
        "editions": ["it-IT"],
        "keywords": {"it": ["ia"]},
    }
    created = client.post("/api/topics", json=payload)
    assert created.status_code == 201
    topic_id = created.json()["id"]

    response = client.put(f"/api/topics/{topic_id}", json={**payload, "keywords": {}})
    assert response.json() == {"error": {"code": "topics.keywords_required", "params": {}}}

    assert (
        client.patch(f"/api/topics/{topic_id}/active", json={"active": False}).json()["active"]
        is False
    )
    assert (
        client.patch(f"/api/topics/{topic_id}/active", json={}).json()["error"]["code"]
        == "validation"
    )
    assert len(client.get("/api/topics/meta").json()["editions"]) >= 5
    assert client.delete(f"/api/topics/{topic_id}").status_code == 204
    assert client.get(f"/api/topics/{topic_id}").status_code == 404


def test_open_url_only_allows_web_links(client: TestClient, ctx) -> None:
    opened: list[str] = []
    ctx.open_url = opened.append
    assert client.post("/api/app/open-url", json={"url": "https://example.com"}).status_code == 204
    assert client.post("/api/app/open-url", json={"url": "file:///C:/Windows"}).status_code == 400
    assert opened == ["https://example.com"]


def test_frontend_served_with_spa_fallback(client: TestClient) -> None:
    assert "TALeport" in client.get("/").text
    assert "TALeport" in client.get("/settings").text  # client-side route
    assert client.get("/assets/app.js").text == "console.log('ok')"
    assert "TALeport" in client.get("/../../etc/passwd").text  # no path traversal
    assert client.get("/api/does-not-exist").status_code == 404

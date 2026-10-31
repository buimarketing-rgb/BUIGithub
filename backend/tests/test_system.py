def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_voice_capabilities_and_disabled_whisper(client, member_h):
    caps = client.get("/api/voice/capabilities", headers=member_h).json()
    assert caps["server_transcription"] is False
    r = client.post("/api/voice/transcribe", files={"file": ("a.webm", b"\x1aE\xdf\xa3fake", "audio/webm")}, headers=member_h)
    assert r.status_code == 501


def test_voice_conversation_flag(client, member_h):
    r = client.post("/api/chat/stream", json={"message": "hello there", "is_voice": True}, headers=member_h)
    assert r.status_code == 200
    convs = client.get("/api/chat/conversations", headers=member_h).json()["items"]
    assert convs[0]["is_voice"] is True


def test_system_health_and_settings(client, admin_h, super_h):
    h = client.get("/api/system/health", headers=admin_h).json()
    assert h["database"]["ok"] and h["embeddings"]["detail"] == "hash-v3"
    assert h["llm"]["provider"] == "extractive"
    s = client.get("/api/settings", headers=admin_h).json()
    assert "answer_min_score" in s
    bad = client.put("/api/settings", json={"values": {"llm_provider": "skynet"}}, headers=super_h)
    assert bad.status_code == 400
    assert client.put("/api/settings", json={"values": {"nope": 1}}, headers=super_h).status_code == 400


def test_reindex_and_export(client, admin_h, super_h, product):
    r = client.post("/api/knowledge/reindex", headers=admin_h).json()
    assert r["counts"]["products"] == 1
    assert client.get("/api/admin/export", headers=admin_h).status_code == 403
    exp = client.get("/api/admin/export", headers=super_h).json()
    assert exp["products"][0]["name"] == "HydroMax 900"


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_demo_seed_loads_and_answers(client, member_h):
    from app.seeds.demo import remove, seed
    from tests.conftest import ask

    seed(with_users=False)
    a = ask(client, member_h, "What is the maximum head of AF-700?")
    assert "45 m" in a["content"]
    remove()
    a = ask(client, member_h, "What is the maximum head of AF-700?")
    assert a["answered"] is False

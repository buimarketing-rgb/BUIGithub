from tests.conftest import SAMPLE_PRODUCT, ask, login, make_user


def test_team_member_cannot_modify_knowledge(client, member_h):
    assert client.post("/api/products", json=SAMPLE_PRODUCT, headers=member_h).status_code == 403
    assert client.post("/api/documents", json={"title": "x", "content": "y"}, headers=member_h).status_code == 403
    assert client.post("/api/faqs", json={"question": "abc?", "answer": "b"}, headers=member_h).status_code == 403
    assert client.post("/api/research/jobs", json={"query": "x"}, headers=member_h).status_code == 403
    assert client.put("/api/settings", json={"values": {}}, headers=member_h).status_code == 403
    assert client.get("/api/audit-logs", headers=member_h).status_code == 403
    assert client.get("/api/users", headers=member_h).status_code == 403
    files = {"file": ("a.txt", b"hello world", "text/plain")}
    assert client.post("/api/documents/upload", files=files, headers=member_h).status_code == 403


def test_team_member_can_read(client, member_h, product):
    assert client.get("/api/products", headers=member_h).status_code == 200
    assert client.get(f"/api/products/{product['id']}", headers=member_h).status_code == 200
    assert client.get("/api/analytics/dashboard", headers=member_h).status_code == 200


def test_admin_cannot_manage_admins_but_super_admin_can(client, admin_h, super_h):
    body = {"email": "new-admin@test.local", "full_name": "New Admin", "role": "admin", "password": "StrongPass123"}
    assert client.post("/api/users", json=body, headers=admin_h).status_code == 403
    assert client.post("/api/users", json=body, headers=super_h).status_code == 201
    member = {**body, "email": "tm@test.local", "role": "team_member"}
    assert client.post("/api/users", json=member, headers=admin_h).status_code == 201


def test_only_super_admin_changes_settings(client, admin_h, super_h):
    assert client.put("/api/settings", json={"values": {"company_name": "X"}}, headers=admin_h).status_code == 403
    r = client.put("/api/settings", json={"values": {"company_name": "Acme"}}, headers=super_h)
    assert r.status_code == 200 and r.json()["company_name"]["value"] == "Acme"


def test_last_super_admin_protected(client, super_h):
    me = client.get("/api/auth/me", headers=super_h).json()
    assert client.delete(f"/api/users/{me['id']}", headers=super_h).status_code == 400


def test_restricted_and_draft_content_hidden_from_members(client, admin_h, member_h):
    client.post("/api/documents", json={"title": "Secret margins", "content": "Dealer margin for Zentrix is 42 percent.", "visibility": "restricted", "category": "sales_information"}, headers=admin_h)
    draft = client.post("/api/products", json={**SAMPLE_PRODUCT, "name": "Draftomatic", "model_number": "DR-1", "status": "draft"}, headers=admin_h).json()
    docs = client.get("/api/documents", headers=member_h).json()
    assert all(d["title"] != "Secret margins" for d in docs["items"])
    assert client.get(f"/api/products/{draft['id']}", headers=member_h).status_code == 404
    ans = ask(client, member_h, "What is the dealer margin for Zentrix?")
    assert "42" not in ans["content"]
    assert ans["answered"] is False
    # Admins can see restricted knowledge
    ans_admin = ask(client, admin_h, "What is the dealer margin for Zentrix?")
    assert "42" in ans_admin["content"]


def test_chat_history_is_private(client, member_h, product):
    ans = ask(client, member_h, "What is the warranty of HydroMax 900?")
    make_user("other@test.local", "team_member")
    other = login(client, "other@test.local")
    assert client.get(f"/api/chat/conversations/{ans['conversation_id']}", headers=other).status_code == 404
    assert client.get("/api/chat/conversations", headers=other).json()["total"] == 0

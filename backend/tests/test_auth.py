from tests.conftest import login, make_user


def test_login_success_and_me(client, super_h):
    r = client.get("/api/auth/me", headers=super_h)
    assert r.status_code == 200
    assert r.json()["role"] == "super_admin"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "root@test.local", "password": "nope"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/products", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    r = client.post("/api/auth/login", json={"email": "root@test.local", "password": "RootPassw0rd!"})
    first_cookie = r.cookies.get("bui_refresh")
    assert first_cookie
    # CSRF header required
    assert client.post("/api/auth/refresh").status_code == 403
    r2 = client.post("/api/auth/refresh", headers={"X-Requested-With": "BUI"})
    assert r2.status_code == 200
    second_cookie = r2.cookies.get("bui_refresh")
    assert second_cookie and second_cookie != first_cookie
    # Re-using the rotated (old) token revokes the family
    client.cookies.set("bui_refresh", first_cookie, path="/api/auth")
    assert client.post("/api/auth/refresh", headers={"X-Requested-With": "BUI"}).status_code == 401
    client.cookies.set("bui_refresh", second_cookie, path="/api/auth")
    assert client.post("/api/auth/refresh", headers={"X-Requested-With": "BUI"}).status_code == 401


def test_logout_revokes_refresh(client):
    client.post("/api/auth/login", json={"email": "root@test.local", "password": "RootPassw0rd!"})
    assert client.post("/api/auth/logout", headers={"X-Requested-With": "BUI"}).status_code == 204
    assert client.post("/api/auth/refresh", headers={"X-Requested-With": "BUI"}).status_code == 401


def test_password_reset_via_admin_link(client, super_h):
    make_user("bob@test.local", "team_member")
    users = client.get("/api/users", headers=super_h).json()["items"]
    bob = next(u for u in users if u["email"] == "bob@test.local")
    link = client.post(f"/api/users/{bob['id']}/reset-link", headers=super_h).json()["reset_url"]
    token = link.split("token=")[1]
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "weakpassword"}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewStrongPass1"}).status_code == 204
    # token is single-use
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewStrongPass2"}).status_code == 400
    login(client, "bob@test.local", "NewStrongPass1")


def test_forgot_password_does_not_enumerate(client):
    a = client.post("/api/auth/forgot-password", json={"email": "root@test.local"}).json()
    b = client.post("/api/auth/forgot-password", json={"email": "nobody@test.local"}).json()
    assert a == b


def test_change_password(client, member_h):
    r = client.post("/api/auth/change-password", json={"current_password": "wrong", "new_password": "AnotherPass123"}, headers=member_h)
    assert r.status_code == 400
    r = client.post("/api/auth/change-password", json={"current_password": "Passw0rdTest!", "new_password": "AnotherPass123"}, headers=member_h)
    assert r.status_code == 204
    login(client, "member@test.local", "AnotherPass123")


def test_disabled_user_cannot_login(client, super_h):
    make_user("gone@test.local", "team_member")
    uid = next(u["id"] for u in client.get("/api/users", headers=super_h).json()["items"] if u["email"] == "gone@test.local")
    client.patch(f"/api/users/{uid}", json={"is_active": False}, headers=super_h)
    r = client.post("/api/auth/login", json={"email": "gone@test.local", "password": "Passw0rdTest!"})
    assert r.status_code == 403


def test_login_rate_limit(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "login_rate_limit_per_minute", 3)
    codes = [client.post("/api/auth/login", json={"email": "x@test.local", "password": "bad"}).status_code for _ in range(5)]
    assert codes[-1] == 429

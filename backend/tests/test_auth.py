"""Access + refresh token lifecycle."""

from __future__ import annotations

from tests.conftest import requires_db

CREDS = {"email": "alice@example.com", "password": "hunter2hunter2", "name": "Alice"}


@requires_db
def test_signup_login_me(client):
    r = client.post("/auth/signup", json=CREDS)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == CREDS["email"]
    assert body["access_token"] and body["refresh_token"]

    r = client.post("/auth/login", json={"email": CREDS["email"], "password": CREDS["password"]})
    assert r.status_code == 200
    access = r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["email"] == CREDS["email"]


@requires_db
def test_signup_duplicate_email(client):
    assert client.post("/auth/signup", json=CREDS).status_code == 201
    assert client.post("/auth/signup", json=CREDS).status_code == 409


@requires_db
def test_login_wrong_password(client):
    client.post("/auth/signup", json=CREDS)
    r = client.post("/auth/login", json={"email": CREDS["email"], "password": "nope"})
    assert r.status_code == 401


@requires_db
def test_refresh_rotates_and_old_token_is_rejected(client):
    refresh = client.post("/auth/signup", json=CREDS).json()["refresh_token"]

    r1 = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert new_refresh != refresh

    # The old refresh token is now burned.
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    # The new one works.
    assert client.post("/auth/refresh", json={"refresh_token": new_refresh}).status_code == 200


@requires_db
def test_logout_revokes_refresh_token(client):
    refresh = client.post("/auth/signup", json=CREDS).json()["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": refresh}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401


@requires_db
def test_protected_route_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401

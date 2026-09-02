def test_login_returns_token_and_profile(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"
    assert "hashed_password" not in body["user"]


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


def test_protected_route_requires_a_token(client):
    assert client.get("/api/v1/vehicles").status_code == 401


def test_me_returns_the_current_user(client, admin_headers):
    response = client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


def test_inspector_cannot_create_users(client, admin_headers):
    created = client.post(
        "/api/v1/users",
        json={
            "email": "insp@example.com",
            "full_name": "Test Inspector",
            "role": "inspector",
            "password": "InspPass123!",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201

    token = client.post(
        "/api/v1/auth/login",
        json={"email": "insp@example.com", "password": "InspPass123!"},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/users",
        json={
            "email": "another@example.com",
            "full_name": "Another",
            "role": "inspector",
            "password": "Password123!",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

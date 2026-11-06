import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"

def test_register_and_login_holder():
    unique_email = f"holder_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"

    # 1. Register
    reg_res = client.post(
        "/auth/register",
        json={"email": unique_email, "password": password, "role": "holder"},
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == unique_email
    assert reg_data["user"]["role"] == "holder"
    assert reg_data["user"]["account_id"] is not None

    # 2. Duplicate registration rejected
    dup_res = client.post(
        "/auth/register",
        json={"email": unique_email, "password": password, "role": "holder"},
    )
    assert dup_res.status_code == 409

    # 3. Login success
    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 4. Access /auth/me
    me_res = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == unique_email

    # 5. Access holder-only route
    holder_res = client.get(
        "/auth/holder-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert holder_res.status_code == 200

    # 6. Holder cannot access admin-only route
    admin_res = client.get(
        "/auth/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert admin_res.status_code == 403

def test_login_invalid_credentials():
    res = client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrong"},
    )
    assert res.status_code == 401

def test_roles_enforcement():
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    auditor_email = f"auditor_{uuid.uuid4().hex[:8]}@example.com"

    # Register admin
    adm_res = client.post(
        "/auth/register",
        json={"email": admin_email, "password": "AdminPassword123!", "role": "admin"},
    )
    assert adm_res.status_code == 201
    adm_token = adm_res.json()["access_token"]

    # Register auditor
    aud_res = client.post(
        "/auth/register",
        json={"email": auditor_email, "password": "AuditorPassword123!", "role": "auditor"},
    )
    assert aud_res.status_code == 201
    aud_token = aud_res.json()["access_token"]

    # Admin access admin-only
    res = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {adm_token}"})
    assert res.status_code == 200

    # Auditor access admin-only -> 403
    res = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {aud_token}"})
    assert res.status_code == 403

    # Auditor access auditor-only -> 200
    res = client.get("/auth/auditor-only", headers={"Authorization": f"Bearer {aud_token}"})
    assert res.status_code == 200

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

def test_register_and_login():
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    pw = "SecretPass123!"

    # 1. Register: always gets role 'holder'
    reg_res = client.post("/auth/register", json={"email": unique_email, "password": pw})
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == unique_email
    assert user_data["role"] == "holder"

    # 2. Duplicate registration rejected
    dup_res = client.post("/auth/register", json={"email": unique_email, "password": pw})
    assert dup_res.status_code == 409

    # 3. Login
    login_res = client.post("/auth/login", json={"email": unique_email, "password": pw})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 4. /me returns authenticated user
    me_res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == unique_email
    assert me_res.json()["role"] == "holder"

    # 5. Holder accessing /admin/ping returns 403
    admin_res = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert admin_res.status_code == 403

def test_unauthenticated():
    res = client.get("/me")
    assert res.status_code == 401

def test_seed_users_and_roles():
    pw = "DemoPassword123!"

    # Test Admin
    adm_login = client.post("/auth/login", json={"email": "admin@ledgerline.test", "password": pw})
    assert adm_login.status_code == 200
    adm_token = adm_login.json()["access_token"]

    adm_ping = client.get("/admin/ping", headers={"Authorization": f"Bearer {adm_token}"})
    assert adm_ping.status_code == 200
    assert adm_ping.json() == {"ok": True}

    # Test Auditor
    aud_login = client.post("/auth/login", json={"email": "auditor@ledgerline.test", "password": pw})
    assert aud_login.status_code == 200
    aud_token = aud_login.json()["access_token"]

    aud_ping = client.get("/admin/ping", headers={"Authorization": f"Bearer {aud_token}"})
    assert aud_ping.status_code == 403

    # Test Holder
    hld_login = client.post("/auth/login", json={"email": "holder@ledgerline.test", "password": pw})
    assert hld_login.status_code == 200
    hld_token = hld_login.json()["access_token"]

    hld_ping = client.get("/admin/ping", headers={"Authorization": f"Bearer {hld_token}"})
    assert hld_ping.status_code == 403

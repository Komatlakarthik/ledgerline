import httpx

base = "https://ledgerline-api-2kf3.onrender.com"
pw = "DemoPassword123!"

print("=== 1. Login as holder@ledgerline.test ===")
r = httpx.post(f"{base}/auth/login", json={"email": "holder@ledgerline.test", "password": pw}, timeout=25)
print("Status:", r.status_code)
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

print("\n=== 2. Create account 'main' ===")
r = httpx.post(f"{base}/accounts", headers=h, json={"name": "main"}, timeout=25)
print("Status:", r.status_code, "Response:", r.json())
account_id = r.json().get("id")

if not account_id:
    r = httpx.get(f"{base}/accounts", headers=h, timeout=25)
    print("Existing accounts:", r.json())
    account_id = r.json()[0]["id"]

print(f"\n=== 3. Deposit 50,000 paise (Rs 500) into account {account_id} with key dep-0000001 ===")
dep_h = {**h, "Idempotency-Key": "dep-0000001"}
r = httpx.post(f"{base}/deposits", headers=dep_h, json={"account_id": account_id, "amount_paise": 50000}, timeout=25)
print("Status:", r.status_code, "Response:", r.json())

print("\n=== 4. Replay EXACT same deposit curl (expect same response, unchanged balance) ===")
r2 = httpx.post(f"{base}/deposits", headers=dep_h, json={"account_id": account_id, "amount_paise": 50000}, timeout=25)
print("Status:", r2.status_code, "Response:", r2.json())
print("Idempotent match:", r.json() == r2.json())

print("\n=== 5. Same key, different amount (expect 422 error) ===")
r3 = httpx.post(f"{base}/deposits", headers=dep_h, json={"account_id": account_id, "amount_paise": 99999}, timeout=25)
print("Status:", r3.status_code, "Response:", r3.json())

print("\n=== 6. Withdraw too much (expect 409 refused) ===")
wd_h = {**h, "Idempotency-Key": "wd-0000001"}
r4 = httpx.post(f"{base}/withdrawals", headers=wd_h, json={"account_id": account_id, "amount_paise": 1000000}, timeout=25)
print("Status:", r4.status_code, "Response:", r4.json())

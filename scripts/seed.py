import os, psycopg
from dotenv import load_dotenv

load_dotenv()
from app.config import DATABASE_URL
from app.security import hash_password

pw = os.environ.get("SEED_PASSWORD", "DemoPassword123!")
USERS = [("admin@ledgerline.test", "admin"),
         ("auditor@ledgerline.test", "auditor"),
         ("holder@ledgerline.test", "holder")]

with psycopg.connect(DATABASE_URL) as conn:
    for email, role in USERS:
        conn.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (%s,%s,%s) "
            "ON CONFLICT (email) DO NOTHING", (email, hash_password(pw), role))
    print("Seed users created successfully!")

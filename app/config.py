import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:dev@localhost:5432/ledgerline"
)
JWT_SECRET = os.environ["JWT_SECRET"]   # no default on purpose: app refuses to start without it

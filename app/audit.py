import os
import logging
import psycopg
from psycopg.types.json import Jsonb
from .config import DATABASE_URL

log_ = logging.getLogger("audit")


def log(user_id, action, detail):
    """Own connection + autocommit, so the row survives the caller's rollback."""
    db_url = os.environ.get("DATABASE_URL", DATABASE_URL)
    try:
        with psycopg.connect(db_url, autocommit=True) as c:
            c.execute("INSERT INTO audit_logs (user_id, action, detail) VALUES (%s,%s,%s)",
                      (user_id, action, Jsonb(detail)))
    except psycopg.Error:
        log_.exception("audit write failed")     # a failed audit write must not hide the denial

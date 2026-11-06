from contextlib import contextmanager
from typing import Generator
import psycopg
from psycopg_pool import ConnectionPool
from app.config import DATABASE_URL

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=10,
    open=True,
    timeout=10.0,
)

@contextmanager
def get_db() -> Generator[psycopg.Connection, None, None]:
    """Context manager for obtaining a database connection from the pool."""
    with pool.connection() as conn:
        yield conn

def get_db_conn() -> Generator[psycopg.Connection, None, None]:
    """FastAPI dependency for obtaining a database connection."""
    with pool.connection() as conn:
        yield conn

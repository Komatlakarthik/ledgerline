import psycopg
from psycopg.rows import dict_row
from .config import DATABASE_URL

def get_conn():
    # one connection per request; commits on success, rolls back on exception
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn

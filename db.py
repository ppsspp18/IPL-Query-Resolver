import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_CONFIG = {
    "host": os.getenv("IPL_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("IPL_DB_PORT", "3306")),
    "user": os.getenv("IPL_DB_USER", "psp"),
    "password": os.getenv("IPL_DB_PASSWORD", "123456"),
    "database": os.getenv("IPL_DB_NAME", "ipl_normalized"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

# Optional dedicated read-only account used by the Text-to-SQL pipeline.
READONLY_CONFIG = None
_ro_user = os.getenv("IPL_RO_USER")
if _ro_user:
    READONLY_CONFIG = {
        **DB_CONFIG,
        "user": _ro_user,
        "password": os.getenv("IPL_RO_PASSWORD", ""),
    }


def get_connection(config=None):
    return pymysql.connect(**(config or DB_CONFIG))


def get_readonly_connection():
    """Return a connection restricted to read-only SQL (if a dedicated account
    is configured, otherwise fall back to the main account)."""
    return get_connection(READONLY_CONFIG or DB_CONFIG)


def run_query(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def run_many(sqls):
    results = []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for sql, params in sqls:
                cur.execute(sql, params or ())
                results.append(cur.fetchall())
        return results
    finally:
        conn.close()


def fetch_scalar(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return list(row.values())[0] if row else None
    finally:
        conn.close()

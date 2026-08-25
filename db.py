import os
import pymysql

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


def get_connection():
    return pymysql.connect(**DB_CONFIG)


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

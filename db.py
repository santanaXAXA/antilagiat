import sqlite3
import hashlib
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "submissions.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS submissions (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        created   TEXT DEFAULT (datetime('now')),
        text_hash TEXT UNIQUE,
        shingles  TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT UNIQUE NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created       TEXT DEFAULT (datetime('now'))
    )""")
    conn.commit()
    conn.close()


def create_user(username: str, email: str, password_hash: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
            (username.strip(), email.strip().lower(), password_hash),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_email(email: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _shingles(text: str, n: int = 5) -> set:
    words = text.lower().split()
    result = set()
    for i in range(len(words) - n + 1):
        gram = " ".join(words[i : i + n])
        result.add(hashlib.md5(gram.encode()).hexdigest()[:10])
    return result


def store(text: str):
    text_hash = hashlib.md5(text.encode()).hexdigest()
    shingles  = list(_shingles(text))
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO submissions (text_hash, shingles) VALUES (?,?)",
        (text_hash, json.dumps(shingles)),
    )
    conn.commit()
    conn.close()


def compare(text: str) -> dict:
    shingles = _shingles(text)
    if not shingles:
        return {"score": 0, "total_docs": 0}

    conn  = sqlite3.connect(DB_PATH)
    rows  = conn.execute("SELECT shingles FROM submissions").fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        return {"score": 0, "total_docs": 0}

    max_sim = 0.0
    for (s_json,) in rows:
        stored  = set(json.loads(s_json))
        inter   = len(shingles & stored)
        union   = len(shingles | stored)
        sim     = inter / union if union else 0
        if sim > max_sim:
            max_sim = sim

    return {"score": round(max_sim * 100), "total_docs": total}


init_db()

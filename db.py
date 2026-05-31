import sqlite3
import hashlib
import json
import os

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "submissions.db"))


def _open():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _open()
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
        is_admin      INTEGER DEFAULT 0,
        created       TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS checks (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL,
        created      TEXT DEFAULT (datetime('now')),
        text_snippet TEXT,
        char_count   INTEGER DEFAULT 0,
        originality  INTEGER DEFAULT 0,
        borrowing    INTEGER DEFAULT 0,
        citation     INTEGER DEFAULT 0,
        ai           INTEGER DEFAULT 0
    )""")
    conn.commit()
    # migration: add is_admin if old DB exists without it
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    conn.close()


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(username: str, email: str, password_hash: str) -> bool:
    conn = _open()
    try:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.execute(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?,?,?,?)",
            (username.strip(), email.strip().lower(), password_hash, 1 if count == 0 else 0),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_email(email: str):
    conn = _open()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    conn = _open()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    conn = _open()
    rows = conn.execute("""
        SELECT u.id, u.username, u.email, u.is_admin, u.created,
               COUNT(c.id) AS total_checks,
               MAX(c.created) AS last_check
        FROM users u LEFT JOIN checks c ON c.user_id = u.id
        GROUP BY u.id ORDER BY u.created DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Checks ─────────────────────────────────────────────────────────────────────

def save_check(user_id: int, text: str, result: dict):
    snippet = text[:120] + ("…" if len(text) > 120 else "")
    conn = _open()
    conn.execute(
        "INSERT INTO checks (user_id, text_snippet, char_count, originality, borrowing, citation, ai) VALUES (?,?,?,?,?,?,?)",
        (user_id, snippet, len(text), result["originality"], result["borrowing"], result["citation"], result["ai"]),
    )
    conn.commit()
    conn.close()


def get_user_checks(user_id: int, limit: int = 30):
    conn = _open()
    rows = conn.execute(
        "SELECT * FROM checks WHERE user_id=? ORDER BY created DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_count(user_id: int) -> int:
    conn = _open()
    n = conn.execute(
        "SELECT COUNT(*) FROM checks WHERE user_id=? AND date(created)=date('now')",
        (user_id,),
    ).fetchone()[0]
    conn.close()
    return n


def get_user_stats(user_id: int) -> dict:
    conn = _open()
    total = conn.execute("SELECT COUNT(*) FROM checks WHERE user_id=?", (user_id,)).fetchone()[0]
    avg   = conn.execute("SELECT AVG(originality) FROM checks WHERE user_id=?", (user_id,)).fetchone()[0]
    best  = conn.execute("SELECT MAX(originality) FROM checks WHERE user_id=?", (user_id,)).fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM checks WHERE user_id=? AND date(created)=date('now')", (user_id,)
    ).fetchone()[0]
    conn.close()
    return {
        "total_checks": total,
        "avg_originality": round(avg) if avg else 0,
        "best_originality": best or 0,
        "today_checks": today,
    }


def get_admin_stats() -> dict:
    conn = _open()
    total_users  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_checks = conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    today_checks = conn.execute("SELECT COUNT(*) FROM checks WHERE date(created)=date('now')").fetchone()[0]
    avg_orig     = conn.execute("SELECT AVG(originality) FROM checks").fetchone()[0]
    conn.close()
    return {
        "total_users":    total_users,
        "total_checks":   total_checks,
        "today_checks":   today_checks,
        "avg_originality": round(avg_orig) if avg_orig else 0,
    }


# ── Submissions (shingle DB) ────────────────────────────────────────────────────

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
    conn = _open()
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
    conn  = _open()
    rows  = conn.execute("SELECT shingles FROM submissions").fetchall()
    conn.close()
    total = len(rows)
    if not total:
        return {"score": 0, "total_docs": 0}
    max_sim = 0.0
    for (s_json,) in rows:
        stored = set(json.loads(s_json))
        inter  = len(shingles & stored)
        union  = len(shingles | stored)
        sim    = inter / union if union else 0
        if sim > max_sim:
            max_sim = sim
    return {"score": round(max_sim * 100), "total_docs": total}


def compare_two(text1: str, text2: str) -> dict:
    s1 = _shingles(text1)
    s2 = _shingles(text2)
    if not s1 or not s2:
        return {"similarity": 0, "shared": 0, "total1": len(s1), "total2": len(s2)}
    inter = len(s1 & s2)
    union = len(s1 | s2)
    return {
        "similarity": round(inter / union * 100) if union else 0,
        "shared":     inter,
        "total1":     len(s1),
        "total2":     len(s2),
    }


init_db()

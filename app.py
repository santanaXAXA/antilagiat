import io
import os
import functools
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from analyzer import analyze, rewrite, split_sentences
from db import (
    store, compare, compare_two,
    create_user, get_user_by_email, get_user_by_id,
    save_check, get_user_checks, get_daily_count, get_user_stats,
    get_all_users, get_admin_stats,
)
from web_check import check_wikipedia, check_google

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ll-secret-key-2026")

DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "10"))


# ── Decorators ─────────────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.is_json:
                return jsonify({"error": "Требуется авторизация"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"]  = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(user["is_admin"])
            return redirect(url_for("index"))
        error = "Неверный email или пароль"
    return render_template("login.html", error=error, mode="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        if not username or not email or not password:
            error = "Заполните все поля"
        elif len(password) < 6:
            error = "Пароль минимум 6 символов"
        elif password != confirm:
            error = "Пароли не совпадают"
        else:
            ok = create_user(username, email, generate_password_hash(password))
            if ok:
                user = get_user_by_email(email)
                session["user_id"]  = user["id"]
                session["username"] = user["username"]
                session["is_admin"] = bool(user["is_admin"])
                return redirect(url_for("index"))
            error = "Такой email или имя уже зарегистрированы"
    return render_template("login.html", error=error, mode="register")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Main ───────────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html",
        username=session["username"],
        is_admin=session.get("is_admin", False),
        daily_limit=DAILY_LIMIT,
    )


# ── Check ──────────────────────────────────────────────────────────────────────

@app.route("/check", methods=["POST"])
@login_required
def check():
    user_id = session["user_id"]
    if not session.get("is_admin") and get_daily_count(user_id) >= DAILY_LIMIT:
        return jsonify({"error": f"Достигнут дневной лимит ({DAILY_LIMIT} проверок). Попробуйте завтра."}), 429

    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст не может быть пустым"}), 400
    if len(text) < 50:
        return jsonify({"error": "Текст слишком короткий (минимум 50 символов)"}), 400
    if len(text) > 10000:
        return jsonify({"error": "Текст слишком длинный (максимум 10 000 символов)"}), 400

    result    = analyze(text)
    sentences = split_sentences(text)
    db_result = compare(text)
    store(text)

    wiki_matches   = check_wikipedia(sentences)
    google_matches = check_google(sentences)
    all_sources    = wiki_matches + google_matches

    source_boost = min(40, len(all_sources) * 12)
    new_bor = min(100, result["borrowing"] + source_boost + db_result["score"] // 3)
    diff    = new_bor - result["borrowing"]
    result["borrowing"]   = new_bor
    result["originality"] = max(0, result["originality"] - diff)
    result["db"]          = db_result
    result["sources"]     = all_sources

    save_check(user_id, text, result)
    return jsonify(result)


@app.route("/rewrite", methods=["POST"])
@login_required
def rewrite_text():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст не может быть пустым"}), 400
    return jsonify(rewrite(text))


# ── File upload ────────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Файл не выбран"}), 400
    name = f.filename.lower()
    if name.endswith(".txt"):
        text = f.read().decode("utf-8", errors="ignore")
    elif name.endswith(".docx"):
        from docx import Document
        doc  = Document(io.BytesIO(f.read()))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        return jsonify({"error": "Поддерживаются только .txt и .docx"}), 400
    return jsonify({"text": text[:10000]})


# ── Compare ────────────────────────────────────────────────────────────────────

@app.route("/compare_texts", methods=["POST"])
@login_required
def compare_endpoint():
    data  = request.get_json()
    text1 = data.get("text1", "").strip()
    text2 = data.get("text2", "").strip()
    if not text1 or not text2:
        return jsonify({"error": "Оба текста обязательны"}), 400
    if len(text1) < 20 or len(text2) < 20:
        return jsonify({"error": "Тексты слишком короткие (минимум 20 символов)"}), 400
    return jsonify(compare_two(text1, text2))


# ── API helpers ────────────────────────────────────────────────────────────────

@app.route("/api/quota")
@login_required
def api_quota():
    used = get_daily_count(session["user_id"])
    return jsonify({"used": used, "limit": DAILY_LIMIT, "is_admin": session.get("is_admin", False)})


@app.route("/api/history")
@login_required
def api_history():
    return jsonify(get_user_checks(session["user_id"]))


# ── Profile ────────────────────────────────────────────────────────────────────

@app.route("/profile")
@login_required
def profile():
    user   = get_user_by_id(session["user_id"])
    stats  = get_user_stats(session["user_id"])
    checks = get_user_checks(session["user_id"], limit=10)
    return render_template("profile.html",
        user=user, stats=stats, checks=checks,
        username=session["username"],
        is_admin=session.get("is_admin", False),
        daily_limit=DAILY_LIMIT,
    )


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.route("/admin")
@login_required
@admin_required
def admin():
    return render_template("admin.html",
        stats=get_admin_stats(),
        users=get_all_users(),
        username=session["username"],
    )


# ── Public API ─────────────────────────────────────────────────────────────────

@app.route("/api/check", methods=["POST"])
def api_check():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text is required"}), 400
    if len(text) < 50:
        return jsonify({"ok": False, "error": "text too short (min 50 chars)"}), 400
    if len(text) > 10000:
        return jsonify({"ok": False, "error": "text too long (max 10000 chars)"}), 400
    result = analyze(text)
    result["ok"] = True
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5050)

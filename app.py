import functools
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from analyzer import analyze, rewrite, split_sentences
from db import store, compare, create_user, get_user_by_email, get_user_by_id
from web_check import check_wikipedia, check_google

app = Flask(__name__)
app.secret_key = "ll-secret-key-2026-change-in-prod"


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.is_json:
                return jsonify({"error": "Требуется авторизация"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
@login_required
def index():
    user = get_user_by_id(session["user_id"])
    return render_template("index.html", username=user["username"])


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
            session["user_id"] = user["id"]
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
                session["user_id"] = user["id"]
                return redirect(url_for("index"))
            error = "Такой email или имя уже зарегистрированы"
    return render_template("login.html", error=error, mode="register")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/check", methods=["POST"])
@login_required
def check():
    data = request.get_json()
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "Текст не может быть пустым"}), 400
    if len(text) < 50:
        return jsonify({"error": "Текст слишком короткий (минимум 50 символов)"}), 400
    if len(text) > 10000:
        return jsonify({"error": "Текст слишком длинный (максимум 10 000 символов)"}), 400

    result = analyze(text)
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

    result["db"]      = db_result
    result["sources"] = all_sources

    return jsonify(result)


@app.route("/rewrite", methods=["POST"])
@login_required
def rewrite_text():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст не может быть пустым"}), 400
    return jsonify(rewrite(text))


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

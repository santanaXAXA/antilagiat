from flask import Flask, render_template, request, jsonify
from analyzer import analyze, rewrite

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/check", methods=["POST"])
def check():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст не может быть пустым"}), 400
    if len(text) < 50:
        return jsonify({"error": "Текст слишком короткий (минимум 50 символов)"}), 400
    if len(text) > 10000:
        return jsonify({"error": "Текст слишком длинный (максимум 10 000 символов)"}), 400
    return jsonify(analyze(text))


@app.route("/rewrite", methods=["POST"])
def rewrite_text():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст не может быть пустым"}), 400
    return jsonify(rewrite(text))


# ── Public API ────────────────────────────────────────────────────────────────
# Usage: POST /api/check   {"text": "..."}
# Returns JSON with originality, borrowing, citation, ai scores + stats
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

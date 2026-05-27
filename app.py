from flask import Flask, render_template, request, jsonify
from analyzer import analyze, rewrite, split_sentences
from db import store, compare
from web_check import check_wikipedia, check_google

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

    result = analyze(text)
    sentences = split_sentences(text)

    # Local DB comparison
    db_result = compare(text)
    store(text)

    # Wikipedia + Google
    wiki_matches   = check_wikipedia(sentences)
    google_matches = check_google(sentences)
    all_sources    = wiki_matches + google_matches

    # Boost borrowing score if sources found
    source_boost = min(40, len(all_sources) * 12)
    new_bor = min(100, result["borrowing"] + source_boost + db_result["score"] // 3)
    diff    = new_bor - result["borrowing"]
    result["borrowing"]   = new_bor
    result["originality"] = max(0, result["originality"] - diff)

    result["db"]      = db_result
    result["sources"] = all_sources

    return jsonify(result)


@app.route("/rewrite", methods=["POST"])
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

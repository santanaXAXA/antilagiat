from flask import Flask, render_template, request, jsonify
from analyzer import analyze

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
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5050)

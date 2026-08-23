from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return "EarnPool is running!"


@app.route("/api/status")
def status():
    return jsonify({
        "success": True,
        "message": "EarnPool API is working"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

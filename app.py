from flask import Flask, jsonify, render_template

from database import init_db


app = Flask(__name__)


# Initialize database when the server starts
init_db()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "success": True,
        "message": "EarnPool API is working",
        "database": "connected"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )

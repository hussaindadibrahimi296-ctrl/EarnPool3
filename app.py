from flask import Flask, jsonify, render_template, request

from database import init_db, get_db


app = Flask(__name__)


# Initialize database
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


@app.route("/api/user", methods=["POST"])
def create_user():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400


    telegram_id = data.get("telegram_id")

    if not telegram_id:
        return jsonify({
            "success": False,
            "message": "Telegram ID is required"
        }), 400


    first_name = data.get("first_name", "")
    username = data.get("username", "")
    language = data.get("language", "en")


    conn = get_db()
    cursor = conn.cursor()


    cursor.execute("""
        INSERT INTO users (
            telegram_id,
            first_name,
            username,
            language
        )
        VALUES (%s, %s, %s, %s)

        ON CONFLICT (telegram_id)

        DO UPDATE SET
            first_name = EXCLUDED.first_name,
            username = EXCLUDED.username,
            language = EXCLUDED.language

        RETURNING *
    """, (
        telegram_id,
        first_name,
        username,
        language
    ))


    user = cursor.fetchone()

    conn.commit()

    cursor.close()
    conn.close()


    return jsonify({
        "success": True,
        "user": user
    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
)

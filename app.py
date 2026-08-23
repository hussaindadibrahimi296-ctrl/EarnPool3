from flask import Flask, jsonify, render_template, request
from datetime import datetime, timedelta

from database import init_db, get_db


app = Flask(__name__)


# =========================
# DATABASE
# =========================

init_db()


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# API STATUS
# =========================

@app.route("/api/status")
def status():

    return jsonify({
        "success": True,
        "message": "EarnPool API is working",
        "database": "connected"
    })


# =========================
# CREATE / UPDATE USER
# =========================

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


# =========================
# GET USER
# =========================

@app.route("/api/user/<int:telegram_id>", methods=["GET"])
def get_user(telegram_id):

    conn = get_db()
    cursor = conn.cursor()


    cursor.execute("""
        SELECT
            telegram_id,
            first_name,
            username,
            coins,
            language,
            referral_count,
            last_daily_reward
        FROM users
        WHERE telegram_id = %s
    """, (telegram_id,))


    user = cursor.fetchone()


    cursor.close()
    conn.close()


    if not user:

        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404


    return jsonify({
        "success": True,
        "user": user
    })


# =========================
# DAILY REWARD
# =========================

@app.route("/api/daily-reward", methods=["POST"])
def daily_reward():

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


    conn = get_db()
    cursor = conn.cursor()


    # Get user
    cursor.execute("""
        SELECT
            telegram_id,
            coins,
            last_daily_reward
        FROM users
        WHERE telegram_id = %s
        FOR UPDATE
    """, (telegram_id,))


    user = cursor.fetchone()


    if not user:

        cursor.close()
        conn.close()

        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404


    now = datetime.utcnow()


    last_reward =
        user["last_daily_reward"]


    # =========================
    # CHECK 12 HOURS
    # =========================

    if last_reward:

        next_reward_time = (
            last_reward +
            timedelta(hours=12)
        )


        if now < next_reward_time:

            remaining =
                next_reward_time - now


            total_seconds =
                int(
                    remaining.total_seconds()
                )


            hours =
                total_seconds // 3600


            minutes =
                (
                    total_seconds % 3600
                ) // 60


            cursor.close()
            conn.close()


            return jsonify({

                "success": False,

                "message":
                    "Daily reward is not ready",

                "hours": hours,

                "minutes": minutes,

                "next_reward":
                    next_reward_time.isoformat()

            })


    # =========================
    # GIVE 1000 COINS
    # =========================

    reward = 1000


    cursor.execute("""
        UPDATE users

        SET
            coins = coins + %s,
            last_daily_reward = %s

        WHERE telegram_id = %s

        RETURNING
            telegram_id,
            coins,
            last_daily_reward
    """, (
        reward,
        now,
        telegram_id
    ))


    updated_user =
        cursor.fetchone()


    conn.commit()


    cursor.close()
    conn.close()


    return jsonify({

        "success": True,

        "message":
            "Daily reward claimed",

        "reward":
            reward,

        "user":
            updated_user

    })


# =========================
# RUN
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )

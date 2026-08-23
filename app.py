import os
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor

from flask import Flask, jsonify, render_template, request


# =========================================================
# APP
# =========================================================

app = Flask(__name__)


# =========================================================
# CONFIG
# =========================================================

DAILY_REWARD = 1000
DAILY_INTERVAL_HOURS = 12

AD_REWARD = 2000
MAX_ADS = 10
AD_INTERVAL_HOURS = 12

TASK_REWARD = 1000

# AdsGram Block IDs
ADS_BLOCK_ID = "44182"
TASK_BLOCK_ID = "task-44183"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured"
        )

    return psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db()
    cursor = conn.cursor()

    try:

        # =================================================
        # USERS
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,

                telegram_id BIGINT UNIQUE NOT NULL,

                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',

                coins BIGINT DEFAULT 0,

                language TEXT DEFAULT 'en',

                referral_count INTEGER DEFAULT 0,

                referred_by BIGINT,

                last_daily_reward TIMESTAMP,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # =================================================
        # WITHDRAWALS
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id SERIAL PRIMARY KEY,

                telegram_id BIGINT NOT NULL,

                coins BIGINT NOT NULL,

                amount_usd NUMERIC(20, 6) NOT NULL,

                method TEXT,
                account TEXT,

                status TEXT DEFAULT 'pending',

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # =================================================
        # AD USAGE
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_usage (
                telegram_id BIGINT PRIMARY KEY,

                ads_watched INTEGER DEFAULT 0,

                window_started_at
                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                updated_at
                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # =================================================
        # AD CLAIM HISTORY
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ad_claims (
                id SERIAL PRIMARY KEY,

                telegram_id BIGINT NOT NULL,

                reward_coins BIGINT NOT NULL,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # =================================================
        # TASKS
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,

                title TEXT NOT NULL,

                description TEXT DEFAULT '',

                link TEXT DEFAULT '',

                reward_coins BIGINT DEFAULT 1000,

                active BOOLEAN DEFAULT TRUE,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # =================================================
        # COMPLETED TASKS
        # =================================================

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS completed_tasks (
                id SERIAL PRIMARY KEY,

                telegram_id BIGINT NOT NULL,

                task_id INTEGER NOT NULL,

                reward_coins BIGINT NOT NULL,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE (
                    telegram_id,
                    task_id
                )
            )
        """)


        conn.commit()

        print("Database initialized successfully.")

    except Exception as e:

        conn.rollback()

        print(
            "Database initialization error:",
            repr(e)
        )

        raise

    finally:

        cursor.close()
        conn.close()


# =========================================================
# INITIALIZE DATABASE
# =========================================================

init_db()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# HEALTH / STATUS
# =========================================================

@app.route("/api/status")
def status():

    database_status = "connected"

    conn = None
    cursor = None

    try:

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT 1")

        cursor.fetchone()

    except Exception as e:

        print(
            "Status database error:",
            repr(e)
        )

        database_status = "error"

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return jsonify({
        "success": True,
        "message": "EarnPool API is working",
        "database": database_status,

        "ads_block_id": ADS_BLOCK_ID,
        "task_block_id": TASK_BLOCK_ID
    })


# =========================================================
# CREATE / UPDATE USER
# =========================================================

@app.route(
    "/api/user",
    methods=["POST"]
)
def create_user():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400


    telegram_id = data.get(
        "telegram_id"
    )

    if not telegram_id:

        return jsonify({
            "success": False,
            "message":
                "Telegram ID is required"
        }), 400


    first_name = str(
        data.get(
            "first_name",
            ""
        )
    )

    username = str(
        data.get(
            "username",
            ""
        )
    )

    language = str(
        data.get(
            "language",
            "en"
        )
    )


    if language not in (
        "en",
        "fa",
        "ar"
    ):

        language = "en"


    conn = get_db()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO users (
                telegram_id,
                first_name,
                username,
                language
            )

            VALUES (
                %s,
                %s,
                %s,
                %s
            )

            ON CONFLICT (telegram_id)

            DO UPDATE SET

                first_name =
                    EXCLUDED.first_name,

                username =
                    EXCLUDED.username,

                language =
                    EXCLUDED.language

            RETURNING *
        """, (
            telegram_id,
            first_name,
            username,
            language
        ))


        user = cursor.fetchone()

        conn.commit()


        return jsonify({
            "success": True,
            "user": user
        })


    except Exception as e:

        conn.rollback()

        print(
            "Create user error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Could not save user"
        }), 500


    finally:

        cursor.close()
        conn.close()


# =========================================================
# GET USER
# =========================================================

@app.route(
    "/api/user/<int:telegram_id>",
    methods=["GET"]
)
def get_user(telegram_id):

    conn = get_db()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                telegram_id,
                first_name,
                username,
                coins,
                language,
                referral_count,
                referred_by,
                last_daily_reward,
                created_at

            FROM users

            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))


        user = cursor.fetchone()


        if not user:

            return jsonify({
                "success": False,
                "message":
                    "User not found"
            }), 404


        return jsonify({
            "success": True,
            "user": user
        })


    except Exception as e:

        print(
            "Get user error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Could not load user"
        }), 500


    finally:

        cursor.close()
        conn.close()


# =========================================================
# DAILY REWARD
# 1000 COINS EVERY 12 HOURS
# =========================================================

@app.route(
    "/api/daily-reward",
    methods=["POST"]
)
def daily_reward():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "success": False,
            "message":
                "No data received"
        }), 400


    telegram_id = data.get(
        "telegram_id"
    )

    if not telegram_id:

        return jsonify({
            "success": False,
            "message":
                "Telegram ID is required"
        }), 400


    conn = get_db()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                telegram_id,
                coins,
                last_daily_reward

            FROM users

            WHERE telegram_id = %s

            FOR UPDATE
        """, (
            telegram_id,
        ))


        user = cursor.fetchone()


        if not user:

            return jsonify({
                "success": False,
                "message":
                    "User not found"
            }), 404


        now = datetime.utcnow()

        last_reward = (
            user["last_daily_reward"]
        )


        # =============================================
        # CHECK 12 HOURS
        # =============================================

        if last_reward:

            next_reward_time = (
                last_reward
                + timedelta(
                    hours=DAILY_INTERVAL_HOURS
                )
            )


            if now < next_reward_time:

                remaining = (
                    next_reward_time
                    - now
                )


                total_seconds = max(
                    0,
                    int(
                        remaining.total_seconds()
                    )
                )


                hours = (
                    total_seconds // 3600
                )

                minutes = (
                    total_seconds % 3600
                ) // 60


                conn.rollback()


                return jsonify({
                    "success": False,

                    "message":
                        "Daily reward is not ready",

                    "hours":
                        hours,

                    "minutes":
                        minutes,

                    "next_reward":
                        next_reward_time.isoformat()
                })


        # =============================================
        # GIVE REWARD
        # =============================================

        cursor.execute("""
            UPDATE users

            SET
                coins =
                    coins + %s,

                last_daily_reward =
                    %s

            WHERE telegram_id = %s

            RETURNING
                telegram_id,
                coins,
                last_daily_reward
        """, (
            DAILY_REWARD,
            now,
            telegram_id
        ))


        updated_user = (
            cursor.fetchone()
        )


        conn.commit()


        return jsonify({
            "success": True,

            "message":
                "Daily reward claimed",

            "reward":
                DAILY_REWARD,

            "user":
                updated_user
        })


    except Exception as e:

        conn.rollback()

        print(
            "Daily reward error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Daily reward error"
        }), 500


    finally:

        cursor.close()
        conn.close()


# =========================================================
# ADS STATUS
# =========================================================

@app.route(
    "/api/ads/status/<int:telegram_id>",
    methods=["GET"]
)
def ads_status(telegram_id):

    conn = get_db()
    cursor = conn.cursor()

    try:

        # =============================================
        # CHECK USER
        # =============================================

        cursor.execute("""
            SELECT telegram_id

            FROM users

            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))


        user = cursor.fetchone()


        if not user:

            return jsonify({
                "success": False,
                "message":
                    "User not found"
            }), 404


        # =============================================
        # GET USAGE
        # =============================================

        cursor.execute("""
            SELECT
                ads_watched,
                window_started_at

            FROM ad_usage

            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))


        usage = cursor.fetchone()

        now = datetime.utcnow()


        # =============================================
        # FIRST WINDOW
        # =============================================

        if not usage:

            return jsonify({

                "success": True,

                "ads_watched": 0,

                "ads_remaining":
                    MAX_ADS,

                "limit":
                    MAX_ADS,

                "reward_per_ad":
                    AD_REWARD,

                "window_hours":
                    AD_INTERVAL_HOURS,

                "block_id":
                    ADS_BLOCK_ID
            })


        window_started = (
            usage["window_started_at"]
        )


        next_window = (
            window_started
            + timedelta(
                hours=AD_INTERVAL_HOURS
            )
        )


        # =============================================
        # RESET WINDOW
        # =============================================

        if now >= next_window:

            cursor.execute("""
                UPDATE ad_usage

                SET
                    ads_watched = 0,

                    window_started_at =
                        %s,

                    updated_at =
                        %s

                WHERE telegram_id = %s
            """, (
                now,
                now,
                telegram_id
            ))


            conn.commit()


            return jsonify({

                "success": True,

                "ads_watched": 0,

                "ads_remaining":
                    MAX_ADS,

                "limit":
                    MAX_ADS,

                "reward_per_ad":
                    AD_REWARD,

                "window_hours":
                    AD_INTERVAL_HOURS,

                "block_id":
                    ADS_BLOCK_ID
            })


        watched = (
            usage["ads_watched"]
        )


        remaining_ads = max(
            0,
            MAX_ADS - watched
        )


        remaining_seconds = max(
            0,
            int(
                (
                    next_window - now
                ).total_seconds()
            )
        )


        hours = (
            remaining_seconds // 3600
        )


        minutes = (
            remaining_seconds % 3600
        ) // 60


        return jsonify({

            "success": True,

            "ads_watched":
                watched,

            "ads_remaining":
                remaining_ads,

            "limit":
                MAX_ADS,

            "reward_per_ad":
                AD_REWARD,

            "window_hours":
                AD_INTERVAL_HOURS,

            "hours_until_reset":
                hours,

            "minutes_until_reset":
                minutes,

            "next_window":
                next_window.isoformat(),

            "block_id":
                ADS_BLOCK_ID
        })


    except Exception as e:

        print(
            "Ads status error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Could not load ads status"
        }), 500


    finally:

        cursor.close()
        conn.close()


# =========================================================
# CLAIM REWARDED AD
#
# 2000 COINS
# MAX 10 ADS / 12 HOURS
#
# IMPORTANT:
# AdsGram completion is checked by index.html.
# Backend then performs the coin transaction.
# =========================================================

@app.route(
    "/api/ads/claim",
    methods=["POST"]
)
def claim_ad():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "success": False,
            "message":
                "No data received"
        }), 400


    telegram_id = data.get(
        "telegram_id"
    )

    if not telegram_id:

        return jsonify({
            "success": False,
            "message":
                "Telegram ID is required"
        }), 400


    conn = get_db()
    cursor = conn.cursor()

    try:

        # =============================================
        # LOCK USER
        # =============================================

        cursor.execute("""
            SELECT
                telegram_id,
                coins

            FROM users

            WHERE telegram_id = %s

            FOR UPDATE
        """, (
            telegram_id,
        ))


        user = cursor.fetchone()


        if not user:

            return jsonify({
                "success": False,
                "message":
                    "User not found"
            }), 404


        now = datetime.utcnow()


        # =============================================
        # GET AD WINDOW
        # =============================================

        cursor.execute("""
            SELECT
                ads_watched,
                window_started_at

            FROM ad_usage

            WHERE telegram_id = %s

            FOR UPDATE
        """, (
            telegram_id,
        ))


        usage = cursor.fetchone()


        # =============================================
        # FIRST AD
        # =============================================

        if not usage:

            ads_watched = 0

            window_started = now


            cursor.execute("""
                INSERT INTO ad_usage (
                    telegram_id,
                    ads_watched,
                    window_started_at,
                    updated_at
                )

                VALUES (
                    %s,
                    0,
                    %s,
                    %s
                )
            """, (
                telegram_id,
                now,
                now
            ))


        else:

            ads_watched = (
                usage["ads_watched"]
            )

            window_started = (
                usage["window_started_at"]
            )


            # =========================================
            # RESET 12 HOURS
            # =========================================

            if (
                now - window_started
            ) >= timedelta(
                hours=AD_INTERVAL_HOURS
            ):

                ads_watched = 0

                window_started = now


                cursor.execute("""
                    UPDATE ad_usage

                    SET
                        ads_watched = 0,

                        window_started_at =
                            %s,

                        updated_at =
                            %s

                    WHERE telegram_id = %s
                """, (
                    now,
                    now,
                    telegram_id
                ))


        # =============================================
        # CHECK LIMIT
        # =============================================

        if ads_watched >= MAX_ADS:

            next_window = (
                window_started
                + timedelta(
                    hours=AD_INTERVAL_HOURS
                )
            )


            remaining = (
                next_window - now
            )


            total_seconds = max(
                0,
                int(
                    remaining.total_seconds()
                )
            )


            hours = (
                total_seconds // 3600
            )


            minutes = (
                total_seconds % 3600
            ) // 60


            conn.rollback()


            return jsonify({

                "success": False,

                "message":
                    "You have reached the ad limit",

                "ads_watched":
                    MAX_ADS,

                "ads_remaining":
                    0,

                "hours":
                    hours,

                "minutes":
                    minutes,

                "next_window":
                    next_window.isoformat()
            })


        # =============================================
        # ADD COINS
        # =============================================

        cursor.execute("""
            UPDATE users

            SET coins =
                coins + %s

            WHERE telegram_id = %s

            RETURNING
                telegram_id,
                coins
        """, (
            AD_REWARD,
            telegram_id
        ))


        updated_user = (
            cursor.fetchone()
        )


        # =============================================
        # INCREASE AD COUNT
        # =============================================

        new_count = (
            ads_watched + 1
        )


        cursor.execute("""
            UPDATE ad_usage

            SET
                ads_watched = %s,

                updated_at = %s

            WHERE telegram_id = %s
        """, (
            new_count,
            now,
            telegram_id
        ))


        # =============================================
        # SAVE HISTORY
        # =============================================

        cursor.execute("""
            INSERT INTO ad_claims (
                telegram_id,
                reward_coins
            )

            VALUES (
                %s,
                %s
            )
        """, (
            telegram_id,
            AD_REWARD
        ))


        conn.commit()


        return jsonify({

            "success": True,

            "message":
                "Ad reward claimed",

            "reward":
                AD_REWARD,

            "ads_watched":
                new_count,

            "ads_remaining":
                MAX_ADS - new_count,

            "user":
                updated_user
        })


    except Exception as e:

        conn.rollback()

        print(
            "Ad claim error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Ad reward error"
        }), 500


    finally:

        cursor.close()
        conn.close()


# =========================================================
# GET ACTIVE TASKS
#
# MAIN ENDPOINT:
# /api/tasks/<telegram_id>
#
# =========================================================

@app.route(
    "/api/tasks/<int:telegram_id>",
    methods=["GET"]
)
def get_tasks(telegram_id):

    conn = get_db()
    cursor = conn.cursor()

    try:

        # =============================================
        # CHECK USER
        # =============================================

        cursor.execute("""
            SELECT telegram_id

            FROM users

            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))


       

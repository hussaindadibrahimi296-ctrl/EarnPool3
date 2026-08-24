import os
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, render_template


# =========================================================
# APP
# =========================================================

app = Flask(__name__)


# =========================================================
# SETTINGS
# =========================================================

DAILY_REWARD = 1000
AD_REWARD = 2000
TASK_REWARD = 1000

AD_LIMIT = 10
DAILY_HOURS = 12

# AdsGram Task Block ID
ADSGRAM_TASK_ID = "task-44183"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    return psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor
    )


# =========================================================
# TIME
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


def normalize_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    return value


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db()

    try:

        cur = conn.cursor()

        # -------------------------------------------------
        # USERS
        # -------------------------------------------------

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                language TEXT DEFAULT 'en',
                coins BIGINT DEFAULT 0,
                last_daily_reward TIMESTAMPTZ,
                ads_watched INTEGER DEFAULT 0,
                ads_reset_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # -------------------------------------------------
        # ADD MISSING COLUMNS TO EXISTING USERS TABLE
        # -------------------------------------------------

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS first_name TEXT DEFAULT ''
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS username TEXT DEFAULT ''
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en'
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS coins BIGINT DEFAULT 0
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS last_daily_reward TIMESTAMPTZ
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS ads_watched INTEGER DEFAULT 0
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS ads_reset_at TIMESTAMPTZ
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()
        """)

        # -------------------------------------------------
        # TASK COMPLETIONS
        # -------------------------------------------------

        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                task_id TEXT NOT NULL,
                reward BIGINT NOT NULL DEFAULT 1000,
                completed_at TIMESTAMPTZ DEFAULT NOW(),

                UNIQUE (telegram_id, task_id)
            )
        """)

        # -------------------------------------------------
        # INDEX
        # -------------------------------------------------

        cur.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_task_completions_user
            ON task_completions (telegram_id)
        """)

        conn.commit()

    finally:

        conn.close()


# =========================================================
# DATABASE HELPERS
# =========================================================

def get_user(telegram_id):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = %s
        """, (telegram_id,))

        return cur.fetchone()

    finally:

        conn.close()


def ensure_user(
    telegram_id,
    first_name="",
    username="",
    language="en"
):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute("""
            INSERT INTO users (
                telegram_id,
                first_name,
                username,
                language,
                coins,
                ads_watched,
                ads_reset_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                0,
                0,
                %s
            )
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                first_name = EXCLUDED.first_name,
                username = EXCLUDED.username,
                language = EXCLUDED.language,
                updated_at = NOW()
            RETURNING *
        """, (
            telegram_id,
            first_name or "",
            username or "",
            language or "en",
            utc_now()
        ))

        user = cur.fetchone()

        conn.commit()

        return user

    finally:

        conn.close()


def reset_ads_if_needed(cur, user):

    now = utc_now()

    reset_at = normalize_datetime(
        user.get("ads_reset_at")
    )

    if reset_at is None:

        cur.execute("""
            UPDATE users
            SET
                ads_watched = 0,
                ads_reset_at = %s,
                updated_at = NOW()
            WHERE telegram_id = %s
        """, (
            now,
            user["telegram_id"]
        ))

        return 0, now

    if now >= reset_at + timedelta(hours=24):

        cur.execute("""
            UPDATE users
            SET
                ads_watched = 0,
                ads_reset_at = %s,
                updated_at = NOW()
            WHERE telegram_id = %s
        """, (
            now,
            user["telegram_id"]
        ))

        return 0, now

    return (
        int(user.get("ads_watched") or 0),
        reset_at
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    init_db()

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER USER
# =========================================================

@app.route(
    "/api/user",
    methods=["POST"]
)
def register_user():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        telegram_id = data.get(
            "telegram_id"
        )

        if not telegram_id:
            return jsonify({
                "success": False,
                "message": "telegram_id is required"
            }), 400

        telegram_id = int(
            telegram_id
        )

        user = ensure_user(
            telegram_id=telegram_id,
            first_name=data.get(
                "first_name",
                ""
            ),
            username=data.get(
                "username",
                ""
            ),
            language=data.get(
                "language",
                "en"
            )
        )

        return jsonify({
            "success": True,
            "user": user
        })

    except Exception as e:

        print(
            "REGISTER USER ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500


# =========================================================
# GET USER
# =========================================================

@app.route(
    "/api/user/<int:telegram_id>",
    methods=["GET"]
)
def api_get_user(telegram_id):

    try:

        user = get_user(
            telegram_id
        )

        if not user:

            user = ensure_user(
                telegram_id
            )

        return jsonify({
            "success": True,
            "user": user
        })

    except Exception as e:

        print(
            "GET USER ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500


# =========================================================
# DAILY REWARD
# =========================================================

@app.route(
    "/api/daily-reward",
    methods=["POST"]
)
def daily_reward():

    conn = get_db()

    try:

        data = request.get_json(
            silent=True
        ) or {}

        telegram_id = data.get(
            "telegram_id"
        )

        if not telegram_id:
            return jsonify({
                "success": False,
                "message": "telegram_id is required"
            }), 400

        telegram_id = int(
            telegram_id
        )

        cur = conn.cursor()

        # Lock user row
        cur.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = %s
            FOR UPDATE
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        if not user:

            cur.execute("""
                INSERT INTO users (
                    telegram_id,
                    coins,
                    ads_watched,
                    ads_reset_at
                )
                VALUES (
                    %s,
                    0,
                    0,
                    %s
                )
                RETURNING *
            """, (
                telegram_id,
                utc_now()
            ))

            user = cur.fetchone()

        last_reward = normalize_datetime(
            user.get(
                "last_daily_reward"
            )
        )

        now = utc_now()

        # -------------------------------------------------
        # CHECK 12 HOURS
        # -------------------------------------------------

        if last_reward:

            next_reward = (
                last_reward +
                timedelta(
                    hours=DAILY_HOURS
                )
            )

            if now < next_reward:

                conn.rollback()

                return jsonify({
                    "success": False,
                    "message":
                        "Daily reward is not available yet.",
                    "next_reward":
                        next_reward.isoformat()
                })

        # -------------------------------------------------
        # ADD REWARD
        # -------------------------------------------------

        cur.execute("""
            UPDATE users
            SET
                coins = COALESCE(coins, 0) + %s,
                last_daily_reward = %s,
                updated_at = NOW()
            WHERE telegram_id = %s
            RETURNING *
        """, (
            DAILY_REWARD,
            now,
            telegram_id
        ))

        updated_user = cur.fetchone()

        conn.commit()

        return jsonify({
            "success": True,
            "reward": DAILY_REWARD,
            "user": updated_user
        })

    except Exception as e:

        conn.rollback()

        print(
            "DAILY REWARD ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500

    finally:

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

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = %s
            FOR UPDATE
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        if not user:

            user = ensure_user(
                telegram_id
            )

            # Re-open transaction
            cur = conn.cursor()

            cur.execute("""
                SELECT *
                FROM users
                WHERE telegram_id = %s
                FOR UPDATE
            """, (
                telegram_id,
            ))

            user = cur.fetchone()

        ads_watched, reset_at = (
            reset_ads_if_needed(
                cur,
                user
            )
        )

        now = utc_now()

        remaining = max(
            0,
            AD_LIMIT - ads_watched
        )

        next_reset = (
            reset_at +
            timedelta(hours=24)
        )

        if remaining <= 0:

            seconds = max(
                0,
                int(
                    (
                        next_reset - now
                    ).total_seconds()
                )
            )

            hours = (
                seconds // 3600
            )

            minutes = (
                (seconds % 3600) // 60
            )

        else:

            hours = 0
            minutes = 0

        conn.commit()

        return jsonify({
            "success": True,
            "ads_watched": ads_watched,
            "limit": AD_LIMIT,
            "ads_remaining": remaining,
            "reward": AD_REWARD,
            "hours_until_reset": hours,
            "minutes_until_reset": minutes
        })

    except Exception as e:

        conn.rollback()

        print(
            "ADS STATUS ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# CLAIM REWARDED AD
# =========================================================

@app.route(
    "/api/ads/claim",
    methods=["POST"]
)
def claim_ad():

    conn = get_db()

    try:

        data = request.get_json(
            silent=True
        ) or {}

        telegram_id = data.get(
            "telegram_id"
        )

        if not telegram_id:
            return jsonify({
                "success": False,
                "message": "telegram_id is required"
            }), 400

        telegram_id = int(
            telegram_id
        )

        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = %s
            FOR UPDATE
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        if not user:

            cur.execute("""
                INSERT INTO users (
                    telegram_id,
                    coins,
                    ads_watched,
                    ads_reset_at
                )
                VALUES (
                    %s,
                    0,
                    0,
                    %s
                )
                RETURNING *
            """, (
                telegram_id,
                utc_now()
            ))

            user = cur.fetchone()

        ads_watched, reset_at = (
            reset_ads_if_needed(
                cur,
                user
            )
        )

        # -------------------------------------------------
        # LIMIT
        # -------------------------------------------------

        if ads_watched >= AD_LIMIT:

            next_reset = (
                reset_at +
                timedelta(hours=24)
            )

            conn.rollback()

            return jsonify({
                "success": False,
                "message":
                    "You have reached the daily ad limit.",
                "ads_remaining": 0,
                "next_reset":
                    next_reset.isoformat()
            })

        # -------------------------------------------------
        # GIVE REWARD
        # -------------------------------------------------

        cur.execute("""
            UPDATE users
            SET
                coins =
                    COALESCE(coins, 0) + %s,
                ads_watched =
                    COALESCE(ads_watched, 0) + 1,
                updated_at = NOW()
            WHERE telegram_id = %s
            RETURNING *
        """, (
            AD_REWARD,
            telegram_id
        ))

        updated_user = cur.fetchone()

        new_ads_watched = (
            ads_watched + 1
        )

        ads_remaining = max(
            0,
            AD_LIMIT - new_ads_watched
        )

        conn.commit()

        return jsonify({
            "success": True,
            "reward": AD_REWARD,
            "user": updated_user,
            "ads_watched":
                new_ads_watched,
            "ads_remaining":
                ads_remaining
        })

    except Exception as e:

        conn.rollback()

        print(
            "AD CLAIM ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# ADSGRAM TASK
# =========================================================

@app.route(
    "/api/tasks/available/<int:telegram_id>",
    methods=["GET"]
)
def available_tasks(telegram_id):

    conn = get_db()

    try:

        cur = conn.cursor()

        # Make sure user exists
        cur.execute("""
            SELECT telegram_id
            FROM users
            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        if not user:

            conn.rollback()

            return jsonify({
                "success": True,
                "tasks": []
            })

        # -------------------------------------------------
        # CHECK ADSGRAM TASK COMPLETION
        # -------------------------------------------------

        cur.execute("""
            SELECT id
            FROM task_completions
            WHERE telegram_id = %s
              AND task_id = %s
            LIMIT 1
        """, (
            telegram_id,
            ADSGRAM_TASK_ID
        ))

        completed = cur.fetchone()

        if completed:

            return jsonify({
                "success": True,
                "tasks": []
            })

        # -------------------------------------------------
        # RETURN ADSGRAM TASK
        # -------------------------------------------------

        task = {
            "id": ADSGRAM_TASK_ID,

            "title":
                "AdsGram Task",

            "description":
                "Complete the AdsGram task and claim your reward.",

            "reward":
                TASK_REWARD,

            "adsgram": True,

            "block_id":
                ADSGRAM_TASK_ID,

            "task_type":
                "adsgram"
        }

        return jsonify({
            "success": True,
            "tasks": [
                task
            ]
        })

    except Exception as e:

        print(
            "TASK LOAD ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# CLAIM ADSGRAM TASK
# =========================================================

@app.route(
    "/api/tasks/claim",
    methods=["POST"]
)
def claim_task():

    conn = get_db()

    try:

        data = request.get_json(
            silent=True
        ) or {}

        telegram_id = data.get(
            "telegram_id"
        )

        task_id = data.get(
            "task_id"
        )

        if not telegram_id:

            return jsonify({
                "success": False,
                "message":
                    "telegram_id is required"
            }), 400

        if not task_id:

            return jsonify({
                "success": False,
                "message":
                    "task_id is required"
            }), 400

        telegram_id = int(
            telegram_id
        )

        task_id = str(
            task_id
        )

        # -------------------------------------------------
        # ONLY OUR ADSGRAM TASK
        # -------------------------------------------------

        if task_id != ADSGRAM_TASK_ID:

            return jsonify({
                "success": False,
                "message":
                    "Invalid task."
            }), 400

        cur = conn.cursor()

        # -------------------------------------------------
        # LOCK USER
        # -------------------------------------------------

        cur.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = %s
            FOR UPDATE
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        if not user:

            cur.execute("""
                INSERT INTO users (
                    telegram_id,
                    coins,
                    ads_watched,
                    ads_reset_at
                )
                VALUES (
                    %s,
                    0,
                    0,
                    %s
                )
                RETURNING *
            """, (
                telegram_id,
                utc_now()
            ))

            user = cur.fetchone()

        # -------------------------------------------------
        # PREVENT DOUBLE REWARD
        # -------------------------------------------------

        cur.execute("""
            SELECT id
            FROM task_completions
            WHERE telegram_id = %s
              AND task_id = %s
            FOR UPDATE
        """, (
            telegram_id,
            task_id
        ))

        existing = cur.fetchone()

        if existing:

            conn.rollback()

            return jsonify({
                "success": False,
                "already_completed": True,
                "message":
                    "This task has already been completed."
            })

        # -------------------------------------------------
        # SAVE COMPLETION
        # -------------------------------------------------

        cur.execute("""
            INSERT INTO task_completions (
                telegram_id,
                task_id,
                reward
            )
            VALUES (
                %s,
                %s,
                %s
            )
        """, (
            telegram_id,
            task_id,
            TASK_REWARD
        ))

        # -------------------------------------------------
        # ADD COINS
        # -------------------------------------------------

        cur.execute("""
            UPDATE users
            SET
                coins =
                    COALESCE(coins, 0) + %s,
                updated_at = NOW()
            WHERE telegram_id = %s
            RETURNING *
        """, (
            TASK_REWARD,
            telegram_id
        ))

        updated_user = cur.fetchone()

        conn.commit()

        return jsonify({
            "success": True,
            "reward": TASK_REWARD,
            "task_id": ADSGRAM_TASK_ID,
            "user": updated_user
        })

    except psycopg2.errors.UniqueViolation:

        conn.rollback()

        return jsonify({
            "success": False,
            "already_completed": True,
            "message":
                "This task has already been completed."
        })

    except Exception as e:

        conn.rollback()

        print(
            "TASK CLAIM ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# TASK STATUS
# =========================================================

@app.route(
    "/api/tasks/status/<int:telegram_id>",
    methods=["GET"]
)
def task_status(telegram_id):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT id, completed_at
            FROM task_completions
            WHERE telegram_id = %s
              AND task_id = %s
            LIMIT 1
        """, (
            telegram_id,
            ADSGRAM_TASK_ID
        ))

        completed = cur.fetchone()

        return jsonify({
            "success": True,
            "task_id":
                ADSGRAM_TASK_ID,
            "completed":
                bool(completed),
            "reward":
                TASK_REWARD
        })

    except Exception as e:

        print(
            "TASK STATUS ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# REFERRAL / ACCOUNT BASIC API
# =========================================================

@app.route(
    "/api/account/<int:telegram_id>",
    methods=["GET"]
)
def account(telegram_id):

    try:

        user = get_user(
            telegram_id
        )

        if not user:

            return jsonify({
                "success": False,
                "message":
                    "User not found."
            }), 404

        return jsonify({
            "success": True,
            "user": user
        })

    except Exception as e:

        print(
            "ACCOUNT ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Server error"
        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    try:

        conn = get_db()

        try:

            cur = conn.cursor()

            cur.execute(
                "SELECT 1"
            )

            cur.fetchone()

        finally:

            conn.close()

        return jsonify({
            "success": True,
            "status": "ok"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "status": "error",
            "message": str(e)
        }), 500


# =========================================================
# STARTUP
# =========================================================

try:

    init_db()

except Exception as e:

    print(
        "DATABASE INITIALIZATION ERROR:",
        e
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
        )

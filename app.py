import os
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    make_response
)


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

# =========================================================
# REFERRAL SETTINGS
# =========================================================

REFERRAL_REWARD = 5000

# Telegram Bot username
BOT_USERNAME = "EarnPooll_bot"

# Referral link format:
# https://t.me/EarnPooll_bot?startapp=123456789


# =========================================================
# ADS SETTINGS
# =========================================================

AD_LIMIT = 10
DAILY_HOURS = 12

# AdsGram Task Block ID
ADSGRAM_TASK_ID = "task-44183"


# =========================================================
# DATABASE
# =========================================================

def get_db():

    database_url = os.environ.get(
        "DATABASE_URL"
    )

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

    return datetime.now(
        timezone.utc
    )


def normalize_datetime(value):

    if value is None:
        return None

    if isinstance(value, datetime):

        if value.tzinfo is None:

            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

    return value


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db()

    try:

        cur = conn.cursor()

        # =================================================
        # USERS
        # =================================================

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

        # =================================================
        # ENSURE USERS COLUMNS
        # =================================================

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

        # =================================================
        # TASK COMPLETIONS
        # =================================================

        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (

                id SERIAL PRIMARY KEY,

                telegram_id BIGINT NOT NULL,

                task_id TEXT NOT NULL,

                reward BIGINT NOT NULL DEFAULT 1000,

                completed_at TIMESTAMPTZ DEFAULT NOW(),

                UNIQUE (
                    telegram_id,
                    task_id
                )
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_task_completions_user
            ON task_completions (
                telegram_id
            )
        """)

        # =================================================
        # REFERRALS
        # =================================================

        cur.execute("""
            CREATE TABLE IF NOT EXISTS referrals (

                id SERIAL PRIMARY KEY,

                referrer_telegram_id BIGINT NOT NULL,

                referred_telegram_id BIGINT NOT NULL UNIQUE,

                reward BIGINT NOT NULL DEFAULT 5000,

                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # =================================================
        # REFERRAL INDEX
        # =================================================

        cur.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_referrals_referrer
            ON referrals (
                referrer_telegram_id
            )
        """)

        conn.commit()

    finally:

        conn.close()


# =========================================================
# GET USER
# =========================================================

def get_user(telegram_id):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))

        return cur.fetchone()

    finally:

        conn.close()


# =========================================================
# ENSURE USER
# =========================================================

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

            ON CONFLICT (
                telegram_id
            )

            DO UPDATE SET

                first_name =
                    EXCLUDED.first_name,

                username =
                    EXCLUDED.username,

                language =
                    EXCLUDED.language,

                updated_at =
                    NOW()

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


# =========================================================
# RESET ADS
# =========================================================

def reset_ads_if_needed(
    cur,
    user
):

    now = utc_now()

    reset_at = normalize_datetime(
        user.get("ads_reset_at")
    )

    # First time

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

    # 24 hours passed

    if now >= (
        reset_at +
        timedelta(hours=24)
    ):

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

        int(
            user.get(
                "ads_watched"
            ) or 0
        ),

        reset_at
    )


# =========================================================
# REFERRAL HELPER
# =========================================================

def process_referral(
    conn,
    referred_telegram_id,
    referrer_telegram_id
):

    """
    ثبت Referral واقعی.

    دعوت‌کننده:
        +5000

    دعوت‌شده:
        +5000

    هر referred فقط یک بار
    می‌تواند Referral داشته باشد.
    """

    # -----------------------------------------------------
    # VALIDATE IDS
    # -----------------------------------------------------

    try:

        referrer_telegram_id = int(
            referrer_telegram_id
        )

        referred_telegram_id = int(
            referred_telegram_id
        )

    except Exception:

        return {
            "success": False,
            "reason": "invalid_id"
        }

    # -----------------------------------------------------
    # SELF REFERRAL
    # -----------------------------------------------------

    if (
        referrer_telegram_id ==
        referred_telegram_id
    ):

        return {
            "success": False,
            "reason": "self_referral"
        }

    cur = conn.cursor()

    # -----------------------------------------------------
    # CHECK EXISTING REFERRAL
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
        FROM referrals
        WHERE referred_telegram_id = %s

        LIMIT 1

        FOR UPDATE
    """, (
        referred_telegram_id,
    ))

    existing = cur.fetchone()

    if existing:

        return {
            "success": False,
            "reason": "already_referred"
        }

    # -----------------------------------------------------
    # CHECK REFERRER
    # -----------------------------------------------------

    cur.execute("""
        SELECT *
        FROM users

        WHERE telegram_id = %s

        FOR UPDATE
    """, (
        referrer_telegram_id,
    ))

    referrer = cur.fetchone()

    if not referrer:

        return {
            "success": False,
            "reason": "referrer_not_found"
        }

    # -----------------------------------------------------
    # CHECK REFERRED USER
    # -----------------------------------------------------

    cur.execute("""
        SELECT *
        FROM users

        WHERE telegram_id = %s

        FOR UPDATE
    """, (
        referred_telegram_id,
    ))

    referred = cur.fetchone()

    if not referred:

        return {
            "success": False,
            "reason": "referred_user_not_found"
        }

    # -----------------------------------------------------
    # INSERT REFERRAL
    # -----------------------------------------------------

    cur.execute("""
        INSERT INTO referrals (

            referrer_telegram_id,

            referred_telegram_id,

            reward

        )

        VALUES (
            %s,
            %s,
            %s
        )
    """, (

        referrer_telegram_id,

        referred_telegram_id,

        REFERRAL_REWARD
    ))

    # -----------------------------------------------------
    # REWARD REFERRER
    # -----------------------------------------------------

    cur.execute("""
        UPDATE users

        SET
            coins =
                COALESCE(
                    coins,
                    0
                ) + %s,

            updated_at =
                NOW()

        WHERE telegram_id = %s
    """, (

        REFERRAL_REWARD,

        referrer_telegram_id
    ))

    # -----------------------------------------------------
    # REWARD NEW USER
    # -----------------------------------------------------

    cur.execute("""
        UPDATE users

        SET
            coins =
                COALESCE(
                    coins,
                    0
                ) + %s,

            updated_at =
                NOW()

        WHERE telegram_id = %s
    """, (

        REFERRAL_REWARD,

        referred_telegram_id
    ))

    return {

        "success": True,

        "reward":
            REFERRAL_REWARD,

        "referrer":
            referrer_telegram_id,

        "referred":
            referred_telegram_id
    }


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    init_db()

    response = make_response(
        render_template(
            "index.html"
        )
    )

    # -----------------------------------------------------
    # FALLBACK START PARAM
    # -----------------------------------------------------

    start_param = request.args.get(
        "tgWebAppStartParam"
    )

    if start_param:

        start_param = str(
            start_param
        ).strip()

        response.set_cookie(

            "earnpool_referral",

            start_param,

            max_age=86400,

            httponly=True,

            samesite="Lax"
        )

    return response


# =========================================================
# REGISTER USER
# =========================================================

@app.route(
    "/api/user",
    methods=["POST"]
)
def register_user():

    conn = None

    try:

        data = request.get_json(
            silent=True
        ) or {}

        # -------------------------------------------------
        # USER ID
        # -------------------------------------------------

        telegram_id = data.get(
            "telegram_id"
        )

        if not telegram_id:

            return jsonify({

                "success": False,

                "message":
                    "telegram_id is required"

            }), 400

        telegram_id = int(
            telegram_id
        )

        # -------------------------------------------------
        # USER DATA
        # -------------------------------------------------

        first_name = (
            data.get(
                "first_name"
            ) or ""
        )

        username = (
            data.get(
                "username"
            ) or ""
        )

        language = (
            data.get(
                "language"
            ) or "en"
        )

        # -------------------------------------------------
        # START PARAM
        #
        # index.html will send:
        #
        # start_param:
        # Telegram.WebApp.initDataUnsafe.start_param
        # -------------------------------------------------

        start_param = data.get(
            "start_param"
        )

        # -------------------------------------------------
        # FALLBACK COOKIE
        # -------------------------------------------------

        if not start_param:

            start_param = request.cookies.get(
                "earnpool_referral"
            )

        if start_param:

            start_param = str(
                start_param
            ).strip()

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        conn = get_db()

        cur = conn.cursor()

        # -------------------------------------------------
        # CHECK EXISTING USER
        # -------------------------------------------------

        cur.execute("""
            SELECT *
            FROM users

            WHERE telegram_id = %s

            FOR UPDATE
        """, (
            telegram_id,
        ))

        existing_user = cur.fetchone()

        is_new_user = (
            existing_user is None
        )

        # =================================================
        # NEW USER
        # =================================================

        if is_new_user:

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

                RETURNING *
            """, (

                telegram_id,

                first_name,

                username,

                language,

                utc_now()
            ))

            user = cur.fetchone()

        # =================================================
        # EXISTING USER
        # =================================================

        else:

            cur.execute("""
                UPDATE users

                SET

                    first_name = %s,

                    username = %s,

                    language = %s,

                    updated_at = NOW()

                WHERE telegram_id = %s

                RETURNING *
            """, (

                first_name,

                username,

                language,

                telegram_id
            ))

            user = cur.fetchone()

        # =================================================
        # PROCESS REFERRAL
        # =================================================

        referral_result = {

            "success": False,

            "reason":
                "not_new_user"

        }

        if is_new_user and start_param:

            referral_result = process_referral(

                conn=conn,

                referred_telegram_id=
                    telegram_id,

                referrer_telegram_id=
                    start_param
            )

        # -------------------------------------------------
        # COMMIT
        # -------------------------------------------------

        conn.commit()

        # -------------------------------------------------
        # GET FINAL USER
        # -------------------------------------------------

        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM users

            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        response = make_response(
            jsonify({

                "success": True,

                "user": user,

                "referral":
                    referral_result

            })
        )

        # -------------------------------------------------
        # CLEAR COOKIE
        # -------------------------------------------------

        response.delete_cookie(
            "earnpool_referral"
        )

        return response

    except psycopg2.errors.UniqueViolation:

        if conn:
            conn.rollback()

        return jsonify({

            "success": False,

            "message":
                "Referral already exists."

        }), 409

    except Exception as e:

        if conn:
            conn.rollback()

        print(
            "REGISTER USER ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
                "Server error"

        }), 500

    finally:

        if conn:
            conn.close()


# =========================================================
# GET USER
# =========================================================

@app.route(
    "/api/user/<int:telegram_id>",
    methods=["GET"]
)
def api_get_user(
    telegram_id
):

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

            "message":
                "Server error"

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

                "message":
                    "telegram_id is required"

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

        last_reward = normalize_datetime(
            user.get(
                "last_daily_reward"
            )
        )

        now = utc_now()

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

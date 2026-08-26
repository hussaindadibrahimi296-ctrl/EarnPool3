import os
from datetime import datetime, timedelta, timezone

import requests
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
# REFERRAL
# =========================================================

REFERRAL_REWARD = 5000
BOT_USERNAME = "EarnPooll_bot"


# =========================================================
# ADS
# =========================================================

AD_LIMIT = 10
DAILY_HOURS = 12


# AdsGram Task Block ID
ADSGRAM_TASK_ID = "task-44183"


# =========================================================
# TELEGRAM SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    ""
).strip()

MINI_APP_URL = os.environ.get(
    "MINI_APP_URL",
    ""
).strip()

WEBHOOK_URL = os.environ.get(
    "WEBHOOK_URL",
    ""
).strip()

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else ""
)


# =========================================================
# LANGUAGES
# =========================================================

SUPPORTED_LANGUAGES = {
    "fa": "🇦🇫 فارسی",
    "en": "🇬🇧 English",
    "ar": "🇸🇦 العربية"
}


# =========================================================
# TELEGRAM MESSAGES
# =========================================================

LANGUAGE_MESSAGES = {
    "fa": (
        "🌍 لطفاً زبان خود را انتخاب کنید:\n\n"
        "زبان مورد نظر خود را انتخاب کنید تا اطلاعات و پیام‌های "
        "EarnPool به همان زبان برای شما نمایش داده شود."
    ),

    "en": (
        "🌍 Please choose your language:\n\n"
        "Select your preferred language to receive EarnPool "
        "information and messages in your language."
    ),

    "ar": (
        "🌍 يرجى اختيار لغتك:\n\n"
        "اختر لغتك المفضلة لعرض معلومات ورسائل EarnPool "
        "باللغة التي تختارها."
    )
}


PROMOTIONAL_MESSAGES = {
    "fa": (
        "🎉 <b>به EarnPool خوش آمدید!</b>\n\n"
        "💰 در EarnPool می‌توانید با انجام کارهای ساده "
        "پاداش دریافت کنید و موجودی خود را افزایش دهید.\n\n"

        "🎁 <b>پاداش روزانه</b>\n"
        "هر روز برای دریافت پاداش وارد شوید.\n\n"

        "📺 <b>مشاهده تبلیغات</b>\n"
        "با مشاهده تبلیغات واجد شرایط، سکه دریافت کنید.\n\n"

        "✅ <b>تسک‌ها و مأموریت‌ها</b>\n"
        "کارهای مختلف را انجام دهید و پاداش بگیرید.\n\n"

        "👥 <b>دعوت دوستان</b>\n"
        "دوستان خود را دعوت کنید و از سیستم Referral پاداش بگیرید.\n\n"

        "🎡 <b>فرصت‌های بیشتر برای کسب پاداش</b>\n"
        "EarnPool برای کسانی ساخته شده که می‌خواهند با انجام "
        "فعالیت‌های ساده، پاداش بیشتری جمع کنند.\n\n"

        "🚀 <b>همین حالا اپ را باز کنید و شروع کنید!</b>"
    ),

    "en": (
        "🎉 <b>Welcome to EarnPool!</b>\n\n"
        "💰 Earn rewards by completing simple activities "
        "and growing your balance.\n\n"

        "🎁 <b>Daily Reward</b>\n"
        "Come back regularly and claim your daily reward.\n\n"

        "📺 <b>Watch Ads</b>\n"
        "Watch eligible advertisements and earn coins.\n\n"

        "✅ <b>Tasks & Missions</b>\n"
        "Complete available tasks and collect your rewards.\n\n"

        "👥 <b>Invite Friends</b>\n"
        "Invite your friends and earn rewards through the referral system.\n\n"

        "🎡 <b>More Ways to Earn</b>\n"
        "EarnPool is designed to give you more opportunities "
        "to collect rewards through simple activities.\n\n"

        "🚀 <b>Open the app now and start earning!</b>"
    ),

    "ar": (
        "🎉 <b>مرحباً بك في EarnPool!</b>\n\n"
        "💰 يمكنك في EarnPool الحصول على المكافآت من خلال "
        "تنفيذ مهام وأنشطة بسيطة وزيادة رصيدك.\n\n"

        "🎁 <b>المكافأة اليومية</b>\n"
        "ادخل يومياً للحصول على مكافأتك.\n\n"

        "📺 <b>مشاهدة الإعلانات</b>\n"
        "شاهد الإعلانات المؤهلة واحصل على العملات.\n\n"

        "✅ <b>المهام والتحديات</b>\n"
        "أكمل المهام المتاحة واحصل على مكافآتك.\n\n"

        "👥 <b>دعوة الأصدقاء</b>\n"
        "ادعُ أصدقاءك واحصل على مكافآت من خلال نظام الإحالة.\n\n"

        "🎡 <b>طرق إضافية للحصول على المكافآت</b>\n"
        "تم تصميم EarnPool لمنحك فرصاً أكثر للحصول على "
        "المكافآت من خلال أنشطة بسيطة.\n\n"

        "🚀 <b>افتح التطبيق الآن وابدأ الكسب!</b>"
    )
}


OPEN_APP_TEXT = {
    "fa": "🚀 باز کردن اپ",
    "en": "🚀 Open App",
    "ar": "🚀 فتح التطبيق"
}


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

        # -------------------------------------------------
        # ADD MISSING COLUMNS
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
            ADD COLUMN IF NOT EXISTS created_at
            TIMESTAMPTZ DEFAULT NOW()
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS updated_at
            TIMESTAMPTZ DEFAULT NOW()
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

                UNIQUE (telegram_id, task_id)
            )
        """)

        # -------------------------------------------------
        # TASK INDEX
        # -------------------------------------------------

        cur.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_task_completions_user
            ON task_completions (telegram_id)
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

        # -------------------------------------------------
        # REFERRAL INDEX
        # -------------------------------------------------

        cur.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_referrals_referrer
            ON referrals (referrer_telegram_id)
        """)

        # -------------------------------------------------
        # EXTRA UNIQUE PROTECTION
        # -------------------------------------------------

        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_referrals_referred_unique
            ON referrals (referred_telegram_id)
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
        """, (
            telegram_id,
        ))

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

    if now >= reset_at + timedelta(
        hours=24
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
            user.get("ads_watched") or 0
        ),
        reset_at
    )


# =========================================================
# TELEGRAM API HELPERS
# =========================================================

def telegram_request(
    method,
    payload=None
):

    if not BOT_TOKEN:

        print(
            "TELEGRAM ERROR: BOT_TOKEN is not configured."
        )

        return None

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )

    try:

        response = requests.post(
            url,
            json=payload or {},
            timeout=15
        )

        print(
            f"Telegram {method}: "
            f"{response.status_code}"
        )

        if not response.ok:

            print(
                "Telegram response:",
                response.text
            )

            return None

        result = response.json()

        if not result.get("ok"):

            print(
                "Telegram API error:",
                result
            )

            return None

        return result

    except Exception as e:

        print(
            "TELEGRAM REQUEST ERROR:",
            e
        )

        return None


def send_message(
    chat_id,
    text,
    reply_markup=None
):

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if reply_markup:

        payload["reply_markup"] = reply_markup

    return telegram_request(
        "sendMessage",
        payload
    )


def answer_callback_query(
    callback_query_id,
    text=""
):

    payload = {
        "callback_query_id":
            callback_query_id
    }

    if text:

        payload["text"] = text

    return telegram_request(
        "answerCallbackQuery",
        payload
    )


def edit_message_text(
    chat_id,
    message_id,
    text,
    reply_markup=None
):

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if reply_markup:

        payload["reply_markup"] = reply_markup

    return telegram_request(
        "editMessageText",
        payload
    )


# =========================================================
# LANGUAGE KEYBOARD
# =========================================================

def language_keyboard():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "🇦🇫 فارسی",
                    "callback_data": "language:fa"
                },
                {
                    "text": "🇬🇧 English",
                    "callback_data": "language:en"
                },
                {
                    "text": "🇸🇦 العربية",
                    "callback_data": "language:ar"
                }
            ]
        ]
    }


# =========================================================
# OPEN APP KEYBOARD
# =========================================================

def open_app_keyboard(language):

    if not MINI_APP_URL:

        return None

    return {
        "inline_keyboard": [
            [
                {
                    "text": OPEN_APP_TEXT.get(
                        language,
                        OPEN_APP_TEXT["en"]
                    ),
                    "web_app": {
                        "url": MINI_APP_URL
                    }
                }
            ]
        ]
    }


# =========================================================
# LANGUAGE SELECTION
# =========================================================

def send_language_selection(chat_id):

    return send_message(
        chat_id,
        (
            "🌍 <b>انتخاب زبان / Choose Language / اختر اللغة</b>\n\n"
            "لطفاً زبان خود را انتخاب کنید.\n"
            "Please choose your language.\n"
            "يرجى اختيار لغتك."
        ),
        language_keyboard()
    )


# =========================================================
# SAVE USER LANGUAGE
# =========================================================

def save_user_language(
    telegram_id,
    language
):

    if language not in SUPPORTED_LANGUAGES:

        language = "en"

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute("""
            INSERT INTO users (
                telegram_id,
                language,
                coins,
                ads_watched,
                ads_reset_at
            )
            VALUES (
                %s,
                %s,
                0,
                0,
                %s
            )
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                language = EXCLUDED.language,
                updated_at = NOW()
            RETURNING *
        """, (
            telegram_id,
            language,
            utc_now()
        ))

        user = cur.fetchone()

        conn.commit()

        return user

    finally:

        conn.close()


# =========================================================
# SEND PROMOTIONAL MESSAGE
# =========================================================

def send_promotional_message(
    chat_id,
    telegram_id,
    language
):

    user = save_user_language(
        telegram_id,
        language
    )

    text = PROMOTIONAL_MESSAGES.get(
        language,
        PROMOTIONAL_MESSAGES["en"]
    )

    keyboard = open_app_keyboard(
        language
    )

    if not keyboard:

        text += (
            "\n\n⚠️ <i>Mini App URL is not configured.</i>"
        )

    result = send_message(
        chat_id,
        text,
        keyboard
    )

    return result


# =========================================================
# PROCESS TELEGRAM /START
# =========================================================

def handle_start_message(message):

    chat = message.get("chat") or {}

    user_data = message.get("from") or {}

    chat_id = chat.get("id")

    telegram_id = user_data.get("id")

    if not chat_id or not telegram_id:

        return

    first_name = (
        user_data.get("first_name")
        or ""
    )

    username = (
        user_data.get("username")
        or ""
    )

    # -----------------------------------------------------
    # CHECK EXISTING USER
    # -----------------------------------------------------

    try:

        existing_user = get_user(
            telegram_id
        )

    except Exception as e:

        print(
            "START USER CHECK ERROR:",
            e
        )

        existing_user = None

    # -----------------------------------------------------
    # CREATE USER IF NECESSARY
    # -----------------------------------------------------

    if not existing_user:

        try:

            ensure_user(
                telegram_id=telegram_id,
                first_name=first_name,
                username=username,
                language="en"
            )

        except Exception as e:

            print(
                "START USER CREATE ERROR:",
                e
            )

    else:

        try:

            conn = get_db()

            try:

                cur = conn.cursor()

                cur.execute("""
                    UPDATE users
                    SET
                        first_name = %s,
                        username = %s,
                        updated_at = NOW()
                    WHERE telegram_id = %s
                """, (
                    first_name,
                    username,
                    telegram_id
                ))

                conn.commit()

            finally:

                conn.close()

        except Exception as e:

            print(
                "START PROFILE UPDATE ERROR:",
                e
            )

    # -----------------------------------------------------
    # ALWAYS ASK LANGUAGE ON /START
    # -----------------------------------------------------

    send_language_selection(
        chat_id
    )


# =========================================================
# PROCESS TELEGRAM CALLBACK
# =========================================================

def handle_callback_query(
    callback_query
):

    callback_id = callback_query.get(
        "id"
    )

    data = callback_query.get(
        "data",
        ""
    )

    from_user = (
        callback_query.get("from")
        or {}
    )

    telegram_id = from_user.get(
        "id"
    )

    message = (
        callback_query.get("message")
        or {}
    )

    chat = (
        message.get("chat")
        or {}
    )

    chat_id = chat.get(
        "id"
    )

    message_id = message.get(
        "message_id"
    )

    if not telegram_id:

        if callback_id:

            answer_callback_query(
                callback_id
            )

        return

    # -----------------------------------------------------
    # LANGUAGE CALLBACK
    # -----------------------------------------------------

    if data.startswith(
        "language:"
    ):

        language = data.split(
            ":",
            1
        )[1]

        if language not in SUPPORTED_LANGUAGES:

            language = "en"

        if callback_id:

            answer_callback_query(
                callback_id,
                "Language selected."
            )

        try:

            save_user_language(
                telegram_id,
                language
            )

        except Exception as e:

            print(
                "LANGUAGE SAVE ERROR:",
                e
            )

            if chat_id:

                send_message(
                    chat_id,
                    "❌ Server error. Please try again."
                )

            return

        text = PROMOTIONAL_MESSAGES.get(
            language,
            PROMOTIONAL_MESSAGES["en"]
        )

        keyboard = open_app_keyboard(
            language
        )

        if chat_id and message_id:

            edited = edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard
            )

            if not edited:

                send_promotional_message(
                    chat_id,
                    telegram_id,
                    language
                )

        elif chat_id:

            send_promotional_message(
                chat_id,
                telegram_id,
                language
            )

        return


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.route(
    "/telegram/webhook",
    methods=["POST"]
)
def telegram_webhook():

    try:

        update = request.get_json(
            silent=True
        ) or {}

        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        message = update.get(
            "message"
        )

        if message:

            text = (
                message.get("text")
                or ""
            )

            if text.startswith(
                "/start"
            ):

                handle_start_message(
                    message
                )

        # -------------------------------------------------
        # CALLBACK QUERY
        # -------------------------------------------------

        callback_query = update.get(
            "callback_query"
        )

        if callback_query:

            handle_callback_query(
                callback_query
            )

        return jsonify({
            "ok": True
        })

    except Exception as e:

        print(
            "WEBHOOK ERROR:",
            e
        )

        return jsonify({
            "ok": False
        }), 200


# =========================================================
# SET TELEGRAM WEBHOOK
# =========================================================

def set_telegram_webhook():

    if not BOT_TOKEN:

        print(
            "WEBHOOK: BOT_TOKEN is not configured."
        )

        return

    if not WEBHOOK_URL:

        print(
            "WEBHOOK: WEBHOOK_URL is not configured."
        )

        return

    webhook_endpoint = (
        WEBHOOK_URL.rstrip("/")
        + "/telegram/webhook"
    )

    result = telegram_request(
        "setWebhook",
        {
            "url": webhook_endpoint,
            "allowed_updates": [
                "message",
                "callback_query"
            ]
        }
    )

    if result:

        print(
            "Telegram webhook configured:",
            webhook_endpoint
        )


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
    # TELEGRAM MINI APP START PARAM
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

        conn = get_db()

        cur = conn.cursor()

        # -------------------------------------------------
        # CHECK IF USER ALREADY EXISTS
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

        # -------------------------------------------------
        # CREATE OR UPDATE USER
        # -------------------------------------------------

        if is_new_user:

            language = data.get(
                "language",
                "en"
            ) or "en"

            if language not in SUPPORTED_LANGUAGES:

                language = "en"

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

                data.get(
                    "first_name",
                    ""
                ) or "",

                data.get(
                    "username",
                    ""
                ) or "",

                language,

                utc_now()
            ))

            user = cur.fetchone()

        else:

            language = data.get(
                "language",
                existing_user.get(
                    "language",
                    "en"
                )
            ) or "en"

            if language not in SUPPORTED_LANGUAGES:

                language = existing_user.get(
                    "language",
                    "en"
                )

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
                data.get(
                    "first_name",
                    existing_user.get(
                        "first_name",
                        ""
                    )
                ) or "",

                data.get(
                    "username",
                    existing_user.get(
                        "username",
                        ""
                    )
                ) or "",

                language,

                telegram_id
            ))

            user = cur.fetchone()

        referral_result = None

        # =================================================
        # PROCESS REFERRAL ONLY FOR NEW USERS
        # =================================================

        if is_new_user:

            referrer_id = (
                request.cookies.get(
                    "earnpool_referral"
                )
                or data.get(
                    "referrer_id"
                )
                or data.get(
                    "referral_id"
                )
            )

            if referrer_id:

                referral_result = process_referral(
                    conn=conn,
                    referred_telegram_id=telegram_id,
                    referrer_telegram_id=referrer_id
                )

        conn.commit()

        # -------------------------------------------------
        # GET UPDATED USER
        # -------------------------------------------------

        cur.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        response = make_response(
            jsonify({
                "success": True,
                "user": user,
                "referral": (
                    referral_result
                    if referral_result
                    else {
                        "success": False,
                        "reason":
                            "not_new_user"
                    }
                )
            })
        )

        # -------------------------------------------------
        # CLEAR REFERRAL COOKIE
        # -------------------------------------------------

        response.delete_cookie(
            "earnpool_referral"
        )

        return response

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
                    "next_reward":
                        next_reward.isoformat()
                })

        cur.execute("""
            UPDATE users
            SET
                coins =
                    COALESCE(coins, 0) + %s,
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
            "message":
                "Server error"
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
            "message":
                "Server error"
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

        ads_watched, reset_at = (
            reset_ads_if_needed(
                cur,
                user
            )
        )

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
            "message":
                "Server error"
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

        # -------------------------------------------------
        # CHECK USER
        # -------------------------------------------------

        cur.execute("""
            SELECT telegram_id
            FROM users
            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        if not user:

            return jsonify({
                "success": True,
                "tasks": []
            })

        # -------------------------------------------------
        # CHECK TASK COMPLETION
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
            "title": "AdsGram Task",
            "description":
                "Complete the AdsGram task and claim your reward.",
            "reward": TASK_REWARD,
            "adsgram": True,
            "block_id": ADSGRAM_TASK_ID,
            "task_type": "adsgram"
        }

        return jsonify({
            "success": True,
            "tasks": [task]
        })

    except Exception as e:

        print(
            "TASK LOAD ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message":
                "Server error"
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

        if task_id != ADSGRAM_TASK_ID:

            return jsonify({
                "success": False,
                "message":
                    "Invalid task."
            }), 400

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

            conn.rollback()

            return jsonify({
                "success": False,
                "message":
                    "User not found."
            }), 404

        cur.execute("""
            SELECT id
            FROM task_completions
            WHERE telegram_id = %s
              AND task_id = %s
            LIMIT 1
            FOR UPDATE
        """, (
            telegram_id,
            ADSGRAM_TASK_ID
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
            ADSGRAM_TASK_ID,
            TASK_REWARD
        ))

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
            "message":
                "Server error"
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
            "message":
                "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# REFERRAL SYSTEM
# =========================================================

def process_referral(
    conn,
    referred_telegram_id,
    referrer_telegram_id
):

    """
    ثبت Referral فقط برای کاربر جدید.

    دعوت‌کننده:
        +5000

    دعوت‌شده:
        +5000

    قوانین:
    - Self referral ممنوع
    - هر کاربر فقط یک بار دعوت می‌شود
    - پاداش فقط یک بار پرداخت می‌شود
    - دعوت‌کننده باید قبلاً ثبت شده باشد
    """

    try:

        referred_telegram_id = int(
            referred_telegram_id
        )

        referrer_telegram_id = int(
            referrer_telegram_id
        )

    except (
        TypeError,
        ValueError
    ):

        return {
            "success": False,
            "reason":
                "invalid_id"
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
            "reason":
                "self_referral"
        }

    cur = conn.cursor()

    # -----------------------------------------------------
    # REFERRER MUST EXIST
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
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
            "reason":
                "referrer_not_found"
        }

    # -----------------------------------------------------
    # REFERRED USER CAN ONLY BE REFERRED ONCE
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
        FROM referrals
        WHERE referred_telegram_id = %s
        LIMIT 1
    """, (
        referred_telegram_id,
    ))

    existing_referral = cur.fetchone()

    if existing_referral:

        return {
            "success": False,
            "reason":
                "already_referred"
        }

    # -----------------------------------------------------
    # INSERT REFERRAL
    #
    # ON CONFLICT prevents duplicate reward
    # evenreward
    # even if two requests arrive at the same time.
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
        ON CONFLICT (
            referred_telegram_id
        )
        DO NOTHING
        RETURNING *
    """, (
        referrer_telegram_id,
        referred_telegram_id,
        REFERRAL_REWARD
    ))

    referral = cur.fetchone()

    if not referral:

        return {
            "success": False,
            "reason":
                "already_referred"
        }

    # -----------------------------------------------------
    # REWARD REFERRER
    # -----------------------------------------------------

    cur.execute("""
        UPDATE users
        SET
            coins =
                COALESCE(coins, 0) + %s,
            updated_at = NOW()
        WHERE telegram_id = %s
        RETURNING telegram_id, coins
    """, (
        REFERRAL_REWARD,
        referrer_telegram_id
    ))

    referrer_after = cur.fetchone()

    # -----------------------------------------------------
    # REWARD REFERRED USER
    # -----------------------------------------------------

    cur.execute("""
        UPDATE users
        SET
            coins =
                COALESCE(coins, 0) + %s,
            updated_at = NOW()
        WHERE telegram_id = %s
        RETURNING telegram_id, coins
    """, (
        REFERRAL_REWARD,
        referred_telegram_id
    ))

    referred_after = cur.fetchone()

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    return {
        "success": True,

        "reward":
            REFERRAL_REWARD,

        "referrer_reward":
            REFERRAL_REWARD,

        "referred_reward":
            REFERRAL_REWARD,

        "referrer_telegram_id":
            referrer_telegram_id,

        "referred_telegram_id":
            referred_telegram_id,

        "referrer_coins":
            (
                referrer_after["coins"]
                if referrer_after
                else None
            ),

        "referred_coins":
            (
                referred_after["coins"]
                if referred_after
                else None
            ),

        "referral_id":
            referral["id"]
    }


# =========================================================
# REFERRAL INFORMATION
# =========================================================

@app.route(
    "/api/referral/<int:telegram_id>",
    methods=["GET"]
)
def referral_info(telegram_id):

    conn = get_db()

    try:

        cur = conn.cursor()

        # -------------------------------------------------
        # CHECK USER
        # -------------------------------------------------

        cur.execute("""
            SELECT telegram_id
            FROM users
            WHERE telegram_id = %s
        """, (
            telegram_id,
        ))

        user = cur.fetchone()

        if not user:

            return jsonify({
                "success": False,
                "message":
                    "User not found."
            }), 404

        # -------------------------------------------------
        # COUNT INVITED USERS
        # -------------------------------------------------

        cur.execute("""
            SELECT COUNT(*) AS total
            FROM referrals
            WHERE referrer_telegram_id = %s
        """, (
            telegram_id,
        ))

        result = cur.fetchone()

        invited_count = int(
            result["total"] or 0
        )

        # -------------------------------------------------
        # UNIQUE REFERRAL LINK
        # -------------------------------------------------

        referral_link = (
            f"https://t.me/"
            f"{BOT_USERNAME}"
            f"?startapp={telegram_id}"
        )

        # -------------------------------------------------
        # TOTAL EARNINGS
        # -------------------------------------------------

        total_earnings = (
            invited_count *
            REFERRAL_REWARD
        )

        return jsonify({

            "success": True,

            "telegram_id":
                telegram_id,

            "invited_count":
                invited_count,

            "referral_count":
                invited_count,

            "reward_per_referral":
                REFERRAL_REWARD,

            "total_earnings":
                total_earnings,

            "referral_link":
                referral_link
        })

    except Exception as e:

        print(
            "REFERRAL INFO ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message":
                "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# REFERRAL LIST
# =========================================================

@app.route(
    "/api/referral/<int:telegram_id>/list",
    methods=["GET"]
)
def referral_list(telegram_id):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute("""
            SELECT
                r.referred_telegram_id,
                r.reward,
                r.created_at,
                u.first_name,
                u.username
            FROM referrals r
            LEFT JOIN users u
                ON u.telegram_id =
                   r.referred_telegram_id
            WHERE
                r.referrer_telegram_id = %s
            ORDER BY
                r.created_at DESC
        """, (
            telegram_id,
        ))

        referrals = cur.fetchall()

        return jsonify({
            "success": True,
            "count":
                len(referrals),
            "referrals":
                referrals
        })

    except Exception as e:

        print(
            "REFERRAL LIST ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message":
                "Server error"
        }), 500

    finally:

        conn.close()


# =========================================================
# START APP
# =========================================================

init_db()

set_telegram_webhook()

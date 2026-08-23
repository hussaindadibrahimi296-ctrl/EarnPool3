import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    return psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor
    )


def init_db():

    conn = get_db()
    cursor = conn.cursor()

    # ==========================================
    # USERS
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            first_name TEXT,
            username TEXT,
            coins BIGINT DEFAULT 0,
            language TEXT DEFAULT 'en',
            referral_count INTEGER DEFAULT 0,
            referred_by BIGINT,
            last_daily_reward TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # ==========================================
    # WITHDRAWALS
    # ==========================================

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


    # ==========================================
    # ADS USAGE
    #
    # Maximum:
    # 10 ads / 12 hours / user
    #
    # Each successful ad:
    # 2,000 coins
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ad_usage (
            id SERIAL PRIMARY KEY,

            telegram_id BIGINT UNIQUE NOT NULL,

            ads_watched INTEGER DEFAULT 0,

            window_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # ==========================================
    # AD CLAIMS
    #
    # Stores every successful rewarded ad.
    #
    # This gives us a permanent history and
    # helps prevent duplicate reward requests.
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ad_claims (
            id SERIAL PRIMARY KEY,

            telegram_id BIGINT NOT NULL,

            reward_coins BIGINT NOT NULL DEFAULT 2000,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # ==========================================
    # COMPLETED TASKS
    #
    # A user can receive a reward for a task
    # only once.
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id SERIAL PRIMARY KEY,

            telegram_id BIGINT NOT NULL,

            task_id TEXT NOT NULL,

            reward_coins BIGINT NOT NULL DEFAULT 1000,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (
                telegram_id,
                task_id
            )
        )
    """)


    # ==========================================
    # INDEXES
    #
    # Makes searches faster when the app grows.
    # ==========================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ad_claims_user
        ON ad_claims (telegram_id)
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ad_claims_created
        ON ad_claims (created_at)
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_completed_tasks_user
        ON completed_tasks (telegram_id)
    """)


    conn.commit()

    cursor.close()
    conn.close()

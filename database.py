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

    conn.commit()

    cursor.close()
    conn.close()

# bot/database.py
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

def setup_database():
    """Create or update tables if they don't exist."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            phone_number VARCHAR(20),
            ip_address VARCHAR(45),
            referred_by BIGINT,
            balance INT DEFAULT 0,
            joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # Add ip_address column if it doesn't exist (for seamless updates)
        try:
            cur.execute("ALTER TABLE users ADD COLUMN ip_address VARCHAR(45);")
        except psycopg2.errors.DuplicateColumn:
            pass # Column already exists
            
        cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL PRIMARY KEY,
            referrer_id BIGINT REFERENCES users(id),
            referred_id BIGINT REFERENCES users(id),
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            method VARCHAR(50),
            details VARCHAR(255),
            amount INT,
            status VARCHAR(20) DEFAULT 'pending',
            requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)
    conn.commit()
    conn.close()

# --- User Functions ---
def user_exists(user_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        return cur.fetchone() is not None

def add_user(user_id, username, phone_number, ip_address=None, referrer_id=None):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, username, phone_number, ip_address, referred_by) VALUES (%s, %s, %s, %s, %s)",
            (user_id, username, phone_number, ip_address, referrer_id)
        )

def get_user(user_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, username, phone_number, referred_by, balance FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()

def update_balance(user_id, amount):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET balance = balance + %s WHERE id = %s RETURNING balance", (amount, user_id))
        return cur.fetchone()[0]

def get_balance(user_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        return result[0] if result else 0

# --- Referral Functions ---
def add_referral(referrer_id, referred_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (%s, %s)",(referrer_id, referred_id))

def get_user_referrals(user_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT u.id, u.username FROM referrals r JOIN users u ON r.referred_id = u.id WHERE r.referrer_id = %s ORDER BY r.timestamp DESC", (user_id,))
        return cur.fetchall()

def get_referral_count(user_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = %s", (user_id,))
        return cur.fetchone()[0]

# --- Withdrawal Functions ---
def create_withdrawal_request(user_id, method, details, amount):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, user_id))
        cur.execute("INSERT INTO withdrawals (user_id, method, details, amount) VALUES (%s, %s, %s, %s) RETURNING id", (user_id, method, details, amount))
        return cur.fetchone()[0]

def get_pending_withdrawals():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT w.id, w.user_id, u.username, w.method, w.details, w.amount FROM withdrawals w JOIN users u ON w.user_id = u.id WHERE w.status = 'pending' ORDER BY w.requested_at ASC")
        return cur.fetchall()

def update_withdrawal_status(withdrawal_id, status):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE withdrawals SET status = %s WHERE id = %s", (status, withdrawal_id))

def get_withdrawal_for_refund(withdrawal_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT user_id, amount FROM withdrawals WHERE id = %s", (withdrawal_id,))
        return cur.fetchone()

# --- Admin & Statistics Functions ---
def get_total_user_count():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users")
        return cur.fetchone()[0]

def get_top_referrers(limit=10):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT u.username, COUNT(r.id) as ref_count, u.balance FROM users u LEFT JOIN referrals r ON u.id = r.referrer_id GROUP BY u.id ORDER BY ref_count DESC, u.balance DESC LIMIT %s", (limit,))
        return cur.fetchall()

def get_all_user_ids():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users")
        return [row[0] for row in cur.fetchall()]

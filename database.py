import sqlite3
import os
from datetime import datetime, timedelta
from config import PERSONAS, get_relationship_status

DB_PATH = "girlfriend.db"

def get_connection():
    """Returns a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # General users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Active persona pointer per user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_active_persona (
            telegram_id INTEGER PRIMARY KEY,
            active_persona TEXT DEFAULT 'karin',
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
    """)

    
    # User settings and relationship progression TRACKED PER PERSONA
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            telegram_id INTEGER,
            persona_key TEXT,
            user_nickname TEXT,
            ai_nickname TEXT,
            relationship_xp INTEGER DEFAULT 0,
            relationship_level INTEGER DEFAULT 1,
            PRIMARY KEY(telegram_id, persona_key),
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
    """)
    
    # Conversation logs per persona
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            persona_key TEXT,
            role TEXT, -- 'user' or 'assistant'
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
    """)
    
    # Billing info per user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_billing (
            telegram_id INTEGER PRIMARY KEY,
            free_messages_used INTEGER DEFAULT 0,
            chat_expires_at TIMESTAMP DEFAULT NULL,
            image_credits INTEGER DEFAULT 0,
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
    """)
    
    # Payments info per user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            payment_id TEXT UNIQUE,
            order_id TEXT,
            amount INTEGER, -- in paise
            item_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
    """)

    # Run migration to add seed column to user_settings if not exists
    try:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN seed INTEGER DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

    # Run migration to add recent_gifs column to user_settings if not exists
    try:
        cursor.execute("ALTER TABLE user_settings ADD COLUMN recent_gifs TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()


def setup_user(telegram_id, username, first_name):
    """Checks if a user exists, creating them and their default settings if not."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Upsert user general info
    cursor.execute("""
        INSERT INTO users (telegram_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
    """, (telegram_id, username, first_name))
    
    # Initialize active persona pointer if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO user_active_persona (telegram_id, active_persona)
        VALUES (?, 'karin')
    """, (telegram_id,))

    # Initialize user billing if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO user_billing (telegram_id, free_messages_used, chat_expires_at, image_credits)
        VALUES (?, 0, NULL, 0)
    """, (telegram_id,))
    
    # Initialize settings/profiles for ALL default personas separately
    import random
    for p_key, p_info in PERSONAS.items():
        random_seed = random.randint(1, 999999999)
        cursor.execute("""
            INSERT OR IGNORE INTO user_settings (telegram_id, persona_key, user_nickname, ai_nickname, relationship_xp, relationship_level, seed)
            VALUES (?, ?, ?, ?, 0, 1, ?)
        """, (telegram_id, p_key, first_name, p_info["name"], random_seed))
        
    conn.commit()
    conn.close()


def get_active_persona_key(telegram_id):
    """Retrieves the active persona key for a user, defaulting to 'karin'."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT active_persona FROM user_active_persona WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["active_persona"]
    return "karin"



def get_user_settings(telegram_id):
    """
    Retrieves settings and relationship info for the user's active persona.
    Returns a dict with 'active_persona' key added for backwards compatibility.
    """
    active_persona = get_active_persona_key(telegram_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM user_settings 
        WHERE telegram_id = ? AND persona_key = ?
    """, (telegram_id, active_persona))
    row = cursor.fetchone()
    
    if row:
        settings_dict = dict(row)
        settings_dict["active_persona"] = active_persona
        # If seed is missing, generate and save it
        if settings_dict.get("seed") is None:
            import random
            new_seed = random.randint(1, 2147483647)
            cursor.execute("""
                UPDATE user_settings SET seed = ?
                WHERE telegram_id = ? AND persona_key = ?
            """, (new_seed, telegram_id, active_persona))
            conn.commit()
            settings_dict["seed"] = new_seed
        conn.close()
        return settings_dict
        
    conn.close()
    return None


def update_active_persona(telegram_id, persona_key):
    """Updates the active persona key pointer for the user."""
    if persona_key not in PERSONAS:
        persona_key = "karin"

        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_active_persona (telegram_id, active_persona)
        VALUES (?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET active_persona = excluded.active_persona
    """, (telegram_id, persona_key))
    conn.commit()
    conn.close()


def update_nicknames(telegram_id, user_nickname=None, ai_nickname=None):
    """Updates custom nicknames specifically for the user's active companion."""
    active_persona = get_active_persona_key(telegram_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    if user_nickname is not None:
        cursor.execute("""
            UPDATE user_settings 
            SET user_nickname = ? 
            WHERE telegram_id = ? AND persona_key = ?
        """, (user_nickname, telegram_id, active_persona))
    if ai_nickname is not None:
        cursor.execute("""
            UPDATE user_settings 
            SET ai_nickname = ? 
            WHERE telegram_id = ? AND persona_key = ?
        """, (ai_nickname, telegram_id, active_persona))
    conn.commit()
    conn.close()


def add_xp(telegram_id, amount=10):
    """Adds relationship XP to the user's active companion. Returns (leveled_up: bool, new_level: int, new_title: str)."""
    active_persona = get_active_persona_key(telegram_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current settings for active persona
    cursor.execute("""
        SELECT relationship_xp, relationship_level FROM user_settings 
        WHERE telegram_id = ? AND persona_key = ?
    """, (telegram_id, active_persona))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return False, 1, "Acquaintances"
        
    current_xp = row["relationship_xp"]
    old_level = row["relationship_level"]
    
    new_xp = current_xp + amount
    status = get_relationship_status(new_xp)
    new_level = status["level"]
    new_title = status["title"]
    
    leveled_up = new_level > old_level
    
    cursor.execute("""
        UPDATE user_settings
        SET relationship_xp = ?, relationship_level = ?
        WHERE telegram_id = ? AND persona_key = ?
    """, (new_xp, new_level, telegram_id, active_persona))
    
    conn.commit()
    conn.close()
    
    return leveled_up, new_level, new_title


def add_chat_message(telegram_id, persona_key, role, message):
    """Appends a message to the conversation log for a specific persona."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chat_history (telegram_id, persona_key, role, message)
        VALUES (?, ?, ?, ?)
    """, (telegram_id, persona_key, role, message))
    conn.commit()
    conn.close()


def get_chat_history(telegram_id, persona_key, limit=20):
    """Retrieves recent conversation turns for a specific persona."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, message FROM chat_history
        WHERE telegram_id = ? AND persona_key = ?
        ORDER BY id DESC
        LIMIT ?
    """, (telegram_id, persona_key, limit))
    rows = cursor.fetchall()
    conn.close()
    
    # Reverse rows to restore chronological order
    history = [{"role": row["role"], "content": row["message"]} for row in reversed(rows)]
    return history


def clear_chat_history(telegram_id, persona_key):
    """Resets conversation logs for a specific companion."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM chat_history
        WHERE telegram_id = ? AND persona_key = ?
    """, (telegram_id, persona_key))
    conn.commit()
    conn.close()

# Initialize database schema upon import
init_db()
print("Database initialized successfully.")


def get_user_billing(telegram_id):
    """Retrieves the billing settings for a user, initializing if not exists."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_billing WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    
    # Initialize if missing
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO user_billing (telegram_id, free_messages_used, chat_expires_at, image_credits)
        VALUES (?, 0, NULL, 0)
    """, (telegram_id,))
    conn.commit()
    cursor.execute("SELECT * FROM user_billing WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def increment_free_messages(telegram_id):
    """Increments the count of free messages used by the user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_billing
        SET free_messages_used = free_messages_used + 1
        WHERE telegram_id = ?
    """, (telegram_id,))
    conn.commit()
    conn.close()


def grant_chat_pass(telegram_id, hours=3):
    """Grants or extends a chat subscription for the user by a given number of hours."""
    # Ensure user exists in billing
    get_user_billing(telegram_id)
    
    now = datetime.utcnow()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chat_expires_at FROM user_billing WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    
    current_expiry = None
    if row and row["chat_expires_at"]:
        try:
            current_expiry = datetime.fromisoformat(row["chat_expires_at"])
        except ValueError:
            pass
            
    if current_expiry and current_expiry > now:
        # Extend existing expiry
        new_expiry = current_expiry + timedelta(hours=hours)
    else:
        # Start new expiry from now
        new_expiry = now + timedelta(hours=hours)
        
    cursor.execute("""
        UPDATE user_billing
        SET chat_expires_at = ?
        WHERE telegram_id = ?
    """, (new_expiry.isoformat(), telegram_id))
    conn.commit()
    conn.close()
    return new_expiry


def is_chat_subscribed(telegram_id):
    """Checks if the user has an active chat subscription."""
    billing = get_user_billing(telegram_id)
    if not billing or not billing["chat_expires_at"]:
        return False
        
    try:
        expiry = datetime.fromisoformat(billing["chat_expires_at"])
        return datetime.utcnow() < expiry
    except Exception:
        return False


def grant_image_credits(telegram_id, amount=10):
    """Adds a number of image credits to the user's balance."""
    # Ensure user exists in billing
    get_user_billing(telegram_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_billing
        SET image_credits = image_credits + ?
        WHERE telegram_id = ?
    """, (amount, telegram_id))
    conn.commit()
    conn.close()


def use_image_credit(telegram_id):
    """Deducts 1 image credit from the user's balance. Returns True if successful, False otherwise."""
    # Ensure user exists in billing
    get_user_billing(telegram_id)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT image_credits FROM user_billing WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    
    if not row or row["image_credits"] <= 0:
        conn.close()
        return False
        
    cursor.execute("""
        UPDATE user_billing
        SET image_credits = image_credits - 1
        WHERE telegram_id = ?
    """, (telegram_id,))
    conn.commit()
    conn.close()
    return True


def log_payment(telegram_id, payment_id, order_id, amount, item_type):
    """Logs a successful payment transaction."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO payments (telegram_id, payment_id, order_id, amount, item_type)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, payment_id, order_id, amount, item_type))
        conn.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error logging payment in DB: {e}")
    finally:
        conn.close()


def get_admin_stats():
    """Retrieves general statistics for the admin dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Total users
    cursor.execute("SELECT count(*) as count FROM users")
    total_users = cursor.fetchone()["count"]
    
    # 2. Total paying users (distinct users in payments table)
    cursor.execute("SELECT count(distinct telegram_id) as count FROM payments")
    paying_users = cursor.fetchone()["count"]
    
    # 3. Total payments count
    cursor.execute("SELECT count(*) as count FROM payments")
    total_payments = cursor.fetchone()["count"]
    
    # 4. Total revenue in INR (Razorpay amount is in paise)
    cursor.execute("SELECT sum(amount) as total FROM payments")
    total_revenue_paise = cursor.fetchone()["total"]
    total_revenue_inr = (total_revenue_paise / 100.0) if total_revenue_paise else 0.0
    
    # 5. Recent payments (last 5)
    cursor.execute("""
        SELECT p.payment_id, p.amount, p.item_type, p.created_at, u.username, u.first_name, p.telegram_id
        FROM payments p
        LEFT JOIN users u ON p.telegram_id = u.telegram_id
        ORDER BY p.created_at DESC
        LIMIT 5
    """)
    recent_rows = cursor.fetchall()
    recent_payments = []
    for r in recent_rows:
        recent_payments.append({
            "payment_id": r["payment_id"],
            "amount_inr": r["amount"] / 100.0,
            "item_type": r["item_type"],
            "created_at": r["created_at"],
            "username": r["username"],
            "first_name": r["first_name"],
            "telegram_id": r["telegram_id"]
        })
        
    conn.close()
    
    return {
        "total_users": total_users,
        "paying_users": paying_users,
        "total_payments": total_payments,
        "total_revenue_inr": total_revenue_inr,
        "recent_payments": recent_payments
    }


def get_user_recent_gifs(telegram_id, persona_key):
    """Retrieves the list of recently sent GIF names for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT recent_gifs FROM user_settings 
        WHERE telegram_id = ? AND persona_key = ?
    """, (telegram_id, persona_key))
    row = cursor.fetchone()
    conn.close()
    if row and row["recent_gifs"]:
        return [g.strip() for g in row["recent_gifs"].split(",") if g.strip()]
    return []


def add_user_recent_gif(telegram_id, persona_key, gif_name):
    """Adds a GIF name to the user's recently sent list (keeps last 3)."""
    recent = get_user_recent_gifs(telegram_id, persona_key)
    # Remove if already exists, to push to the end (most recent)
    if gif_name in recent:
        recent.remove(gif_name)
    recent.append(gif_name)
    # Keep last 3 elements
    recent = recent[-3:]
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_settings 
        SET recent_gifs = ?
        WHERE telegram_id = ? AND persona_key = ?
    """, (",".join(recent), telegram_id, persona_key))
    conn.commit()
    conn.close()


import sqlite3
from config import DB_PATH, API_URL
import datetime
import json
import uuid

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            species TEXT,
            seedlings INTEGER,
            seedlot TEXT,
            spacing TEXT,
            lat REAL,
            lon REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            synced BOOLEAN DEFAULT 0,
            assess_updated BOOLEAN DEFAULT 0, 
            growth_grid TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_uuid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            username TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def list_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT user_uuid, name, email, username, created_at
        FROM users
        ORDER BY datetime(created_at) DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [
        {"user_uuid": r[0], "name": r[1], "email": r[2], "username": r[3], "created_at": r[4]}
        for r in rows
    ]

def get_current_user_uuid():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM app_state WHERE key='current_user_uuid' LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_current_user_uuid(user_uuid: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO app_state(key, value) VALUES('current_user_uuid', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (user_uuid,))
    conn.commit()
    conn.close()

def load_current_user_profile():
    user_uuid = get_current_user_uuid()
    if not user_uuid:
        return None

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT user_uuid, name, email, username, created_at
        FROM users
        WHERE user_uuid = ?
        LIMIT 1
    """, (user_uuid,))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return {"user_uuid": row[0], "name": row[1], "email": row[2], "username": row[3], "created_at": row[4]}

def create_user_profile(name, email, username):
    profile = {
        "user_uuid": str(uuid.uuid4()),
        "name": name.strip(),
        "email": email.strip(),
        "username": username.strip(),
    }
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_uuid, name, email, username)
        VALUES (?, ?, ?, ?)
    """, (profile["user_uuid"], profile["name"], profile["email"], profile["username"]))
    conn.commit()
    conn.close()

    set_current_user_uuid(profile["user_uuid"])
    return profile

def get_active_user():
    prof = load_current_user_profile()
    if not prof:
        raise RuntimeError("No active user set")
    return prof

import sqlite3
from config import DB_PATH, API_URL
import datetime
import json
import uuid
import os
import requests
from gom_logger import logger

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
            spacing REAL,
            lat REAL,
            lon REAL,
            elev REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT,
            request_key TEXT,
            notes TEXT,
            site_series TEXT,
            smr TEXT,
            snr TEXT,
            site_fact TEXT,
            site_prep TEXT,
            trial_owner TEXT,
            trial_obj TEXT,
            synced BOOLEAN DEFAULT 0,
            assess_updated BOOLEAN DEFAULT 0, 
            growth_grid TEXT,
            block_name TEXT,
            replicate_no INTEGER
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

    # create table for trial owners with id, name and contact info (email or phone)
    c.execute("""
        CREATE TABLE IF NOT EXISTS trial_owners (
            company_name TEXT,
            contact_name TEXT PRIMARY KEY,
            contact_email TEXT,
            objective TEXT,
            input_order INTEGER AUTO_INCREMENT,
            synced BOOLEAN DEFAULT 0,
            FOREIGN KEY(contact_name) REFERENCES trials(trial_owner) ON DELETE CASCADE
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS trial_photos (
          photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
          photo_uuid TEXT NOT NULL,
          trial_uuid TEXT NOT NULL,
          path TEXT NOT NULL,
          sha256 TEXT,
          bytes INT,
          sync_status TEXT,
          created_at TEXT DEFAULT (datetime('now')),
          FOREIGN KEY(trial_uuid) REFERENCES trials(uuid) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def validate_photo_cache():
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT photo_uuid, path
            FROM trial_photos
        """).fetchall()

        missing = []

        for photo_uuid, abs_path in rows:
            if not os.path.exists(abs_path):
                missing.append(photo_uuid)

        if missing:
            placeholders = ",".join(["?"] * len(missing))
            conn.execute(
                f"""
                DELETE FROM trial_photos
                WHERE photo_uuid IN ({placeholders})
                """,
                missing
            )
            conn.commit()

            logger.info(f"[PHOTO CACHE] Marked {len(missing)} missing photos for re-download")

    finally:
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
    username = username.strip()
    name = name.strip()
    email = email.strip() if email else ""

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 🔍 Check if user already exists
    c.execute("""
        SELECT user_uuid, name, email, username
        FROM users
        WHERE username = ?
    """, (username,))
    row = c.fetchone()

    if row:
        # ✅ Existing user → reuse UUID
        profile = {
            "user_uuid": row[0],
            "name": row[1],
            "email": row[2],
            "username": row[3],
        }

    else:
        # ➕ New user → create UUID + insert
        profile = {
            "user_uuid": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "username": username,
        }

        c.execute("""
            INSERT INTO users (user_uuid, name, email, username)
            VALUES (?, ?, ?, ?)
        """, (
            profile["user_uuid"],
            profile["name"],
            profile["email"],
            profile["username"]
        ))
        conn.commit()

    conn.close()

    # 🎯 Always set active user
    set_current_user_uuid(profile["user_uuid"])
    return profile
    
def get_active_user():
    prof = load_current_user_profile()
    if not prof:
        raise RuntimeError("No active user set")
    return prof

def fetch_users():
    r = requests.get(f"{API_URL}/usernames", timeout=10)
    r.raise_for_status()
    return r.json()

def create_user(user):
    r = requests.post(f"{API_URL}/users", json=user, timeout=10)
    logger.info(f"[API] Create user response: {r.status_code} - {r.text}")
    r.raise_for_status()
    return r.json()

# Download trial owners from server and update local trial_owners table
def download_trial_owners():
    r = requests.get(f"{API_URL}/trial_owners", timeout=10)
    r.raise_for_status()
    owners = r.json()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for owner in owners:
        c.execute("""
            INSERT INTO trial_owners (company_name, contact_name, contact_email, objective, synced)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(contact_name) DO UPDATE SET
                company_name=excluded.company_name,
                contact_email=excluded.contact_email,
                objective=excluded.objective,
                synced=1
        """, (
            owner["company_name"],
            owner["contact_name"],
            owner.get("contact_email"),
            owner.get("objective")
        ))

    conn.commit()
    conn.close()

# Upload new trial owners (synced=0) to server, then mark as synced
def upload_trial_owners():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT company_name, contact_name, contact_email, objective
        FROM trial_owners
        WHERE synced = 0
    """)
    new_owners = c.fetchall()

    owners = [dict(row) for row in new_owners]

    r = requests.post(f"{API_URL}/trial_owners", json=owners, timeout=10)
    logger.info(f"[API] Upload trial owner response: {r.status_code} - {r.text}")
    r.raise_for_status()

    # Mark all as synced
    c.execute("""
        UPDATE trial_owners
        SET synced = 1
        WHERE synced = 0
    """)
    conn.commit()
    conn.close()
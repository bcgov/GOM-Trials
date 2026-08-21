import sqlite3
from config import DB_PATH, API_URL
import datetime
import json
import uuid
import os
import requests
from gom_logger import logger
from contextlib import contextmanager
from utils import user_uuid

@contextmanager
def db_connection():
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()

    except:
        conn.rollback()
        raise

    finally:
        conn.close()

def column_exists(conn, table, column):

    rows = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return any(row[1] == column for row in rows)

def migrate_db(conn):
    if not column_exists(conn, "trials", "grid_direction"):
        conn.execute("""
            ALTER TABLE trials
            ADD COLUMN grid_direction TEXT
        """)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
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
            replicate_no INTEGER,
            grid_orientation TEXT
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

    c.execute("""
            CREATE TABLE IF NOT EXISTS track_logs (
                uuid TEXT PRIMARY KEY,
                name TEXT,
                created DATETIME,
                distance REAL,
                point_count INTEGER,
                track_json TEXT
            )
            """)

    init_assessment_tables(c)
    migrate_db(conn)
    conn.commit()
    conn.close()

def init_assessment_tables(c):

    c.execute("""
        CREATE TABLE IF NOT EXISTS trial_trees (
            tree_uuid TEXT PRIMARY KEY,
            trial_uuid TEXT NOT NULL,
            tree_number INTEGER NOT NULL,
            row_num INTEGER NOT NULL,
            col_num INTEGER NOT NULL,

            UNIQUE(trial_uuid, tree_number),
            UNIQUE(trial_uuid, row_num, col_num),

            FOREIGN KEY(trial_uuid)
                REFERENCES trials(uuid)
                ON DELETE CASCADE
        )
    """)

    ## should really have a foreign key constrain to users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_uuid TEXT PRIMARY KEY,
            trial_uuid TEXT NOT NULL,
            user_uuid TEXT,
            assessment_date DATETIME NOT NULL,

            trial_rating TEXT,
            notes TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            synced BOOLEAN DEFAULT 0,

            FOREIGN KEY(trial_uuid)
                REFERENCES trials(uuid)
                ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tree_assessments (
            tree_assessment_uuid TEXT PRIMARY KEY,
            assessment_uuid TEXT NOT NULL,
            tree_uuid TEXT NOT NULL,

            rating TEXT NOT NULL,
            height REAL,
            diameter REAL,

            UNIQUE(assessment_uuid, tree_uuid),

            FOREIGN KEY(assessment_uuid)
                REFERENCES assessments(assessment_uuid)
                ON DELETE CASCADE,

            FOREIGN KEY(tree_uuid)
                REFERENCES trial_trees(tree_uuid)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS assessment_damage (
            damage_uuid TEXT PRIMARY KEY,
            tree_assessment_uuid TEXT NOT NULL,
            damage_code TEXT NOT NULL,
            severity INTEGER,

            UNIQUE(tree_assessment_uuid, damage_code),

            FOREIGN KEY(tree_assessment_uuid)
                REFERENCES tree_assessments(tree_assessment_uuid)
                ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE VIEW IF NOT EXISTS assessment_performance AS
        WITH scored AS (
            SELECT
                a.assessment_uuid,
                a.trial_uuid,
                a.assessment_date,

                CASE ta.rating
                    WHEN 'D' THEN 0
                    WHEN 'P' THEN 1
                    WHEN 'F' THEN 2
                    WHEN 'G' THEN 3
                    WHEN 'E' THEN 4
                    ELSE NULL
                END AS score

            FROM assessments a
            JOIN tree_assessments ta
            ON a.assessment_uuid = ta.assessment_uuid
        ),

        summarized AS (
            SELECT
                assessment_uuid,
                trial_uuid,
                assessment_date,
                AVG(score) AS mean_score,
                COUNT(score) AS trees_scored
            FROM scored
            GROUP BY
                assessment_uuid,
                trial_uuid,
                assessment_date
        )

        SELECT
            assessment_uuid,
            trial_uuid,
            assessment_date,
            mean_score,
            trees_scored,

            CASE
                WHEN mean_score IS NULL THEN NULL
                WHEN mean_score >= 3.5 THEN 'Excellent'
                WHEN mean_score >= 2.5 THEN 'Good'
                WHEN mean_score >= 1.5 THEN 'Fair'
                WHEN mean_score >= 0.5 THEN 'Poor'
                ELSE 'Fail'
            END AS performance

        FROM summarized;
    """)

    # Useful lookup indexes
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_trial_trees_trial
        ON trial_trees(trial_uuid)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_assessments_trial
        ON assessments(trial_uuid)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_tree_assessments_assessment
        ON tree_assessments(assessment_uuid)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_tree_assessments_tree
        ON tree_assessments(tree_uuid)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_assessment_damage_tree_assessment
        ON assessment_damage(tree_assessment_uuid)
    """)

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
    download_users()  # Ensure local users table is up-to-date with server
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
        namespace = uuid.UUID("username")
        profile = {
            "user_uuid": user_uuid(username),
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

## download gom_users from server and update local users table
def download_users():

    try:
        response = requests.get(
            f"{API_URL}/users",
            timeout=30
        )

    except requests.RequestException as e:
        print(
            "User sync request failed: %s",
            e
        )
        return False

    if response.status_code != 200:
        print(
            "User sync failed. STATUS %s BODY %s",
            response.status_code,
            response.text
        )
        return False

    try:
        result = response.json()

    except ValueError:
        print(
            "User sync returned invalid JSON: %s",
            response.text
        )
        return False

    if not result.get("success", False):
        print(
            "User sync rejected by server: %s",
            result
        )
        return False

    users = result.get("users", [])

    with db_connection() as conn:

        conn.executemany("""
            INSERT INTO users (
                user_uuid,
                username,
                name,
                email
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(user_uuid)
            DO UPDATE SET
                username = excluded.username,
                name = excluded.name,
                email = excluded.email
        """, [
            (
                user["user_uuid"],
                user["username"],
                user.get("name", ""),
                user.get("email", "")
            )
            for user in users
        ])

    print(
        "Synced %d user(s) to local database.",
        len(users)
    )

    return True
    
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
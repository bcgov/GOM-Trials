import sqlite3
from config import DB_PATH, API_URL
from db_users import get_active_user
import requests
from datetime import datetime, timezone
import json
import uuid
import os
from gom_logger import logger

def upload_trials():
    user = get_active_user()["username"]
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM trials WHERE synced=0 AND user_id = ?", (user,))
    trials = [dict(row) for row in cur.fetchall()]
    conn.close()
    print(f"There are {len(trials)} records")
    if not trials:
        print("✅ No local records to upload.")
        return

    try:
        r = requests.post(f"{API_URL}/trials", json=trials, timeout=10)
        if r.status_code == 200:
            dbcon = sqlite3.connect(DB_PATH)
            cur = dbcon.cursor()
            for t in trials:
                cur.execute("UPDATE trials SET synced=1 WHERE uuid=?", (t["uuid"],))
            dbcon.commit()
            dbcon.close()
            print(f"⬆️  Uploaded {len(trials)} records")
        else:
            print("⚠️ Upload failed:", r.status_code, r.text)
    except Exception as e:
        print("⚠️ Upload error:", e)
        
def upload_assess():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT timestamp, growth_grid FROM trials WHERE assess_updated = 1")
    trials = [dict(row) for row in cur.fetchall()]
    conn.close()
    print(f"There are {len(trials)} new assessments")
    if not trials:
        print("✅ No local records to upload.")
        return

    try:
        r = requests.post(f"{API_URL}/trials", json=trials, timeout=10)
        if r.status_code == 200:
            dbcon = sqlite3.connect(DB_PATH)
            cur = dbcon.cursor()
            for t in trials:
                cur.execute("UPDATE trials SET synced=1 WHERE uuid=?", (t["uuid"],))
            dbcon.commit()
            dbcon.close()
            print(f"⬆️  Uploaded {len(trials)} records")
        else:
            print("⚠️ Upload failed:", r.status_code, r.text)
    except Exception as e:
        print("⚠️ Upload error:", e)
        
def download_trials():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT MAX(timestamp) FROM trials WHERE synced <> 0")
    last_sync = cur.fetchone()[0] or "1970-01-01T00:00:00Z"
    print(last_sync)
    conn.close()

    try:
        r = requests.get(f"{API_URL}/trials", params={"since": last_sync}, timeout=10) ##update API to use assessment table #params={"since": last_sync},
        if r.status_code != 200:
            print("⚠️ Download failed:", r.status_code, r.text)
            return

        remote_trials = r.json()
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        for t in remote_trials:
            cur.execute("""
                INSERT INTO trials (uuid, user_id, species, seedlings, seedlot, spacing, lat, lon, elev,
                                    timestamp, growth_grid, site_series, smr, snr, site_fact, site_prep, request_key, trial_owner, block_name, replicate_no, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(uuid) DO UPDATE SET
                    species=excluded.species,
                    seedlings=excluded.seedlings,
                    seedlot=excluded.seedlot,
                    spacing=excluded.spacing,
                    lat=excluded.lat,
                    lon=excluded.lon,
                    elev=excluded.elev,
                    timestamp=excluded.timestamp,
                    synced=1,
                    growth_grid=excluded.growth_grid,
                    site_series=excluded.site_series,
                    smr=excluded.smr,
                    snr=excluded.snr,
                    site_fact=excluded.site_fact,
                    site_prep=excluded.site_prep,
                    request_key=excluded.request_key,
                    trial_owner=excluded.trial_owner,
                    block_name=excluded.block_name,
                    replicate_no=excluded.replicate_no
            """, (t["uuid"],t["user_id"], t["species"], t["seedlings"], t["seedlot"], t["spacing"],
                  t["lat"], t["lon"], t["elev"], t["timestamp"], t["growth_grid"], t["site_series"], t["smr"], t["snr"], t["soil_site_factors"], t["site_prep"], t["request_key"], t["trial_owner"], t["block_name"], t["replicate_no"]))         
                  
        conn.commit()
        conn.close()
        print(f"⬇️  Downloaded {len(remote_trials)} records")
    except Exception as e:
        print("⚠️ Download error:", e)

def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def update_trial(uuid, data): ## Question: should we record who updated the trial?
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print("Updating trial", uuid, "with data:", data)
    ts = utc_now_iso()
    cur.execute("""
        UPDATE trials
        SET species=?,
            seedlings=?,
            seedlot=?,
            spacing=?,
            request_key=?,
            site_series=?,
            smr=?,
            snr=?,
            site_fact=?,
            site_prep=?,
            timestamp=?,
            notes=?,
            synced=0
        WHERE uuid=?
    """, (data["species"], data["seedlings"], data["seedlot"], data["spacing"], data["request_key"],
          data["site_series"], data["smr"], data["snr"], data["site_factors"], data["site_prep"], ts, data["notes"], uuid))

    conn.commit()
    conn.close()
    return ts
    
def get_trial_row(uuid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT uuid, user_id, species, seedlings, seedlot, spacing, request_key, site_series, smr, snr, site_fact, site_prep, notes, trial_owner, block_name, replicate_no
        FROM trials
        WHERE uuid=?
    """, (uuid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    keys = ["uuid","user_id", "species","seedlings","seedlot","spacing", "request_key", "site_series", "smr", "snr", "site_factors", "site_prep", "notes", "trial_owner", "block_name", "replicate_no"]
    return dict(zip(keys, row))

def get_most_recent_trial():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT uuid, user_id, species, seedlings, seedlot, request_key, spacing, site_series, smr, snr, site_fact, site_prep, notes, trial_owner, block_name, replicate_no
        FROM trials
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()

    if not row:
        return dict()

    keys = ["uuid","user_id", "species","seedlings","seedlot","request_key","spacing", "site_series", "smr", "snr", "site_factors", "site_prep", "notes", "trial_owner", "block_name", "replicate_no"]
    return dict(zip(keys, row))
    
def get_photos_for_trial(trial_uuid):
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT path FROM trial_photos WHERE trial_uuid = ? ORDER BY photo_id",
            (trial_uuid,)
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()

def get_local_photos(trial_uuids):

    if not trial_uuids:
        return {}

    # Remove duplicates just in case
    trial_uuids = list(set(trial_uuids))

    placeholders = ",".join(["?"] * len(trial_uuids))

    query = f"""
        SELECT photo_uuid, sha256
        FROM trial_photos
        WHERE trial_uuid IN ({placeholders})
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(query, trial_uuids)
        rows = cursor.fetchall()

        # Build dict
        result = {
            row[0]: {"sha256": row[1]}
            for row in rows
        }

        return result

    finally:
        conn.close()

def db_append_photos(uuid, trial, path, sha, bytes_):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    INSERT INTO trial_photos(photo_uuid, trial_uuid, path, sha256, bytes, sync_status)
    VALUES (?,?,?,?,?,?)
                """,
                (uuid, trial, path, sha, bytes_, "uploaded"))
    conn.commit()
    conn.close()


##sync photos
def upload_photos():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT photo_uuid, trial_uuid, path, sha256, bytes
        FROM trial_photos
        WHERE sync_status IN ('pending','failed')
    """).fetchall()

    for row in rows:
        photo_uuid, trial_uuid, local_path, sha256, bytes_ = row

        # 1. INIT request
        init_resp = requests.post(
            f"{API_URL}/photos/init",
            json={
                "photo_uuid": photo_uuid,
                "trial_uuid": trial_uuid,
                "sha256": sha256,
                "bytes": bytes_,
            }
        ).json()
        
        logger.info(init_resp)

        if not init_resp.get("upload_required", True):
            conn.execute("""
                UPDATE trial_photos
                SET sync_status='uploaded'
                WHERE photo_uuid=?
            """, (photo_uuid,))
            continue

        # 2. UPLOAD
        upload_url = f"{API_URL}/photos/upload/{photo_uuid}"
        logger.info(f"Uploading photo: {photo_uuid}")
        params = {
            "trial_uuid": trial_uuid,
            "sha256": sha256,
            "bytes": bytes_,
        }
        
        try:
            with open(local_path, "rb") as f:
                files = {
                    "image": ("image.jpg", f, "image/jpeg")
                }
                r = requests.post(upload_url, params=params, files=files)
        except:
            logger.warning("Picture no longer exists. Skipping.")
            continue

        logger.info("STATUS: %d", r.status_code)
        logger.info("BODY: %s", r.text)
        try:
            upload_resp = r.json()
        except Exception:
            logger.exception("Failed to parse upload response JSON")
            return False

        if upload_resp.get("ok"):
            conn.execute("""
                UPDATE trial_photos
                SET sync_status='uploaded'
                WHERE photo_uuid=?
            """, (photo_uuid,))
        else:
            conn.execute("""
                UPDATE trial_photos
                SET sync_status='failed'
                WHERE photo_uuid=?
            """, (photo_uuid,))
    conn.close()

def get_trial_owners():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT contact_name
        FROM trial_owners
        ORDER BY input_order ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_trial_owner(company, contact_name, contact_email, objective):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO trial_owners (company_name, contact_name, contact_email, objective)
        VALUES (?, ?, ?, ?)
    """, (company, contact_name, contact_email, objective))
    conn.commit()
    conn.close()

def get_replicate_no(block_name, species_code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM trials
        WHERE block_name = ? AND species = ?   
    """, (block_name, species_code))
    count = cur.fetchone()[0]
    conn.close()
    return str(count + 1)
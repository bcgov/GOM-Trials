import sqlite3
from config import DB_PATH, API_URL
from db_users import get_active_user
import requests
from datetime import datetime, timezone
import json
import uuid

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
                INSERT INTO trials (uuid, user_id, species, seedlings, seedlot, spacing, lat, lon,
                                    timestamp, growth_grid, site_series, smr, snr, site_fact, site_prep, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(uuid) DO UPDATE SET
                    species=excluded.species,
                    seedlings=excluded.seedlings,
                    seedlot=excluded.seedlot,
                    spacing=excluded.spacing,
                    lat=excluded.lat,
                    lon=excluded.lon,
                    timestamp=excluded.timestamp,
                    synced=1,
                    growth_grid=excluded.growth_grid,
                    site_series=excluded.site_series,
                    smr=excluded.smr,
                    snr=excluded.snr,
                    site_fact=excluded.site_fact,
                    site_prep=excluded.site_prep
            """, (t["uuid"],t["user_id"], t["species"], t["seedlings"], t["seedlot"], t["spacing"],
                  t["lat"], t["lon"], t["timestamp"], t["growth_grid"], t["site_series"], t["smr"], t["snr"], t["soil_site_factors"], t["site_prep"]))
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

    ts = utc_now_iso()
    cur.execute("""
        UPDATE trials
        SET species=?,
            seedlings=?,
            seedlot=?,
            spacing=?,
            site_series=?,
            smr=?,
            snr=?,
            site_fact=?,
            site_prep=?,
            timestamp=?,
            synced=0
        WHERE uuid=?
    """, (data["species"], data["seedlings"], data["seedlot"], data["spacing"],  ts, uuid, data["site_series"], data["smr"], data["snr"], data["site_factors"], data["site_prep"]))

    conn.commit()
    conn.close()
    return ts
    
def get_trial_row(uuid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT uuid, user_id, species, seedlings, seedlot, spacing, site_series, smr, snr, site_fact, site_prep
        FROM trials
        WHERE uuid=?
    """, (uuid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    keys = ["uuid","user_id", "species","seedlings","seedlot","spacing", "site_series", "smr", "snr", "site_factors", "site_prep"]
    return dict(zip(keys, row))
    
def get_first_photo_for_trial(trial_uuid):
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT path FROM trial_photos WHERE trial_uuid = ? ORDER BY photo_id ASC LIMIT 1",
            (trial_uuid,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


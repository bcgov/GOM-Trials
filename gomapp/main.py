from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.dropdown import DropDown
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy_garden.mapview import MapView, MapMarker, MapMarkerPopup
from kivy_garden.mapview.mbtsource import MBTilesMapSource
from kivy_garden.mapview.downloader import Downloader
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.behaviors import DragBehavior
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy_garden.mapview.view import MarkerMapLayer
import os
import sys
from kivy.utils import platform
import numpy as np
from kivy.uix.image import Image
from kivy.graphics.texture import Texture
from kivy.uix.filechooser import FileChooserListView
import math
from kivy.uix.filechooser import FileChooserIconView
import sqlite3
import requests
import datetime
import json
import uuid
import os.path
from pathlib import Path
from kivy.clock import mainthread, Clock
from plyer import gps
from kivy.properties import StringProperty
from kivy.resources import resource_find
from tifffile import TiffFile
from kivy.uix.screenmanager import ScreenManager, Screen
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USER_RE  = re.compile(r"^[A-Za-z0-9_]{3,32}$")
DB_PATH = Path.home() / "Documents" / "gomapp_data.db"
API_URL = "http://178.128.233.227"

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
                INSERT INTO trials (uuid, species, seedlings, seedlot, lat, lon,
                                    timestamp, synced, growth_grid)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    species=excluded.species,
                    seedlings=excluded.seedlings,
                    seedlot=excluded.seedlot,
                    lat=excluded.lat,
                    lon=excluded.lon,
                    timestamp=excluded.timestamp,
                    synced=1,
                    growth_grid=excluded.growth_grid
            """, (t["uuid"], t["species"], t["seedlings"], t["seedlot"],
                  t["lat"], t["lon"], t["timestamp"], t["growth_grid"]))
        conn.commit()
        conn.close()
        print(f"⬇️  Downloaded {len(remote_trials)} records")
    except Exception as e:
        print("⚠️ Download error:", e)

R = 6378137.0  # Earth radius in meters
def webmercator_to_lonlat(x, y):
    """Convert x/y (meters) → lon/lat (degrees, EPSG:4326)."""
    lon = math.degrees(x / R)
    lat = math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)
    return lon, lat
    
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        scroll = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", spacing=dp(14), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        # Spacer to push content away from bottom/top when there is space
        form.add_widget(Widget(size_hint_y=None, height=dp(40)))

        form.add_widget(Label(
            text="Welcome to GOM!",
            font_size="24sp",
            size_hint_y=None,
            height=dp(34),
            halign="center",
            valign="middle"
        ))
        form.children[0].bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))

        form.add_widget(Label(
            text="Enter your details (saved on this device).",
            size_hint_y=None,
            height=dp(28),
            halign="center",
            valign="middle"
        ))
        form.children[0].bind(size=lambda inst, _: setattr(inst, "text_size", inst.size))

        self.name_in = TextInput(hint_text="Full name", multiline=False, size_hint_y=None, height=dp(48))
        self.email_in = TextInput(hint_text="Email (Optional)", multiline=False, size_hint_y=None, height=dp(48))
        self.user_in = TextInput(hint_text="Username (letters/numbers/_)", multiline=False, size_hint_y=None, height=dp(48))

        form.add_widget(self.name_in)
        form.add_widget(self.email_in)
        form.add_widget(self.user_in)

        self.err = Label(text="", color=(1, 0, 0, 1), size_hint_y=None, height=dp(24))
        form.add_widget(self.err)

        btn = Button(text="Continue", size_hint_y=None, height=dp(52))
        btn.bind(on_release=self.on_continue)
        form.add_widget(btn)

        # Bottom spacer so it doesn't feel cramped
        form.add_widget(Widget(size_hint_y=None, height=dp(60)))

        scroll.add_widget(form)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_continue(self, *_):
        name = self.name_in.text.strip()
        email = self.email_in.text.strip()
        username = self.user_in.text.strip()

        if len(name) < 2:
            self.err.text = "Please enter your name."
            return
        if not USER_RE.match(username):
            self.err.text = "Username must be 3–32 chars: letters/numbers/_"
            return

        app = App.get_running_app()
        profile = create_user_profile(name, email, username)
        app.user_profile = profile

        self.err.text = ""
        self.manager.current = "map"
    
class GrowthCell(Button):
    STATES = ["P", "M", "G"]

    def __init__(self, initial="P", **kwargs):
        super().__init__(**kwargs)
        self.index = GrowthCell.STATES.index(initial)
        self.text = GrowthCell.STATES[self.index]
        self.update_color()
        self.bind(on_release=self.next_state)

    def next_state(self, *args):
        self.index = (self.index + 1) % 3
        self.text = GrowthCell.STATES[self.index]
        self.update_color()

    def update_color(self):
        if self.text == "P":
            self.background_color = (0.3, 0.7, 1, 1)  # blue
        elif self.text == "M":
            self.background_color = (1, 0.8, 0.2, 1)  # yellow/orange
        else:  # "G"
            self.background_color = (0.3, 0.9, 0.3, 1)  # green

    def get_value(self):
        return GrowthCell.STATES[self.index]
        
class GrowthGrid(GridLayout):
    def __init__(self, existing=None, **kwargs):
        super().__init__(rows=5, cols=5, spacing=4, padding=4, **kwargs)
        self.cells = []

        for r in range(5):
            row = []
            for c in range(5):
                value = existing[r][c] if existing else "P"
                cell = GrowthCell(initial=value, size_hint=(1,1))
                row.append(cell)
                self.add_widget(cell)
            self.cells.append(row)

    def get_grid(self):
        return [[cell.get_value() for cell in row] for row in self.cells]

    
class LocationPopup(Popup):
    def __init__(self, default_lat, default_lon, on_confirm, **kwargs):
        super().__init__(**kwargs)
        self.title = "Set Trial Location"
        self.size_hint = (0.9, 0.5)
        self.on_confirm = on_confirm

        layout = BoxLayout(orientation="vertical", spacing=5, padding=5)

        self.lat_input = TextInput(text=str(default_lat), hint_text="Latitude", multiline=False)
        self.lon_input = TextInput(text=str(default_lon), hint_text="Longitude", multiline=False)

        layout.add_widget(Label(text="Latitude"))
        layout.add_widget(self.lat_input)
        layout.add_widget(Label(text="Longitude"))
        layout.add_widget(self.lon_input)

        btn = Button(text="Create", size_hint_y=None, height=100)
        btn.bind(on_release=self.confirm)
        layout.add_widget(btn)

        self.content = layout

    def confirm(self, instance):
        try:
            lat = float(self.lat_input.text)
            lon = float(self.lon_input.text)
        except ValueError:
            print("⚠️ Invalid coordinates")
            return
        self.on_confirm(lat, lon)
        self.dismiss()

## Class for popup
class TrialFormPopup(Popup):
    def __init__(self, lat, lon, on_submit, **kwargs):
        super().__init__(**kwargs)
        self.title = "Record New Trial"
        self.size_hint = (0.9, 0.6)
        self.lat, self.lon = lat, lon
        self.on_submit = on_submit

        layout = BoxLayout(orientation="vertical", spacing=8, padding=5)

        # Define form fields
        self.species = TextInput(hint_text="Species")
        self.seedlings = TextInput(hint_text="Number of Seedlings", input_filter="int")
        self.seedlot = TextInput(hint_text="Seedlot")
        self.spacing = TextInput(hint_text="Spacing (e.g. 3x3m)")

        layout.add_widget(Label(text="Species"))
        layout.add_widget(self.species)
        layout.add_widget(Label(text="Number of Seedlings"))
        layout.add_widget(self.seedlings)
        layout.add_widget(Label(text="Seedlot"))
        layout.add_widget(self.seedlot)
        layout.add_widget(Label(text="Spacing"))
        layout.add_widget(self.spacing)

        # Submit button
        submit_btn = Button(text="Submit", size_hint_y=None, height=100)
        submit_btn.bind(on_release=self.submit_form)
        layout.add_widget(submit_btn)

        self.content = layout

    def submit_form(self, instance):
        data = {
            "uuid": str(uuid.uuid4()),
            "species": self.species.text.strip(),
            "seedlings": self.seedlings.text.strip(),
            "seedlot": self.seedlot.text.strip(),
            "spacing": self.spacing.text.strip(),
            "lat": self.lat,
            "lon": self.lon,
        }
        self.on_submit(data)
        self.dismiss()

class SafeMBTilesSource(MBTilesMapSource):
    
    def __init__(self, filename, **kwargs):
        super().__init__(filename)
        # Ensure essential metadata exists
        conn = sqlite3.connect(filename)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT)")
        # Default metadata if missing
        for key, val in {
            "minzoom": "0",
            "maxzoom": "18",
            "center": "0,0,2",
            #"bounds": "-180,-90,180,90",  # default global bounds
        }.items():
            cur.execute("INSERT OR IGNORE INTO metadata (name, value) VALUES (?, ?)", (key, val))
        conn.commit()

        # Read metadata safely
        cur.execute("SELECT name, value FROM metadata")
        self.metadata = {name: value for name, value in cur.fetchall()}
        print(f"Metadata: {self.metadata}")
        conn.close()

        metadata = getattr(self, "metadata", {})

        # --- Safe bounds ---
        b = metadata.get("bounds", None)
        if b:
            try:
                parts = list(map(float, b.split(",")))
                if len(parts) == 4:
                    self._bounds = tuple(parts)
                else:
                    self._bounds = (-180, -85.05112878, 180, 85.05112878)
            except Exception:
                self._bounds = (-180, -85.05112878, 180, 85.05112878)
        else:
            self._bounds = (-180, -85.05112878, 180, 85.05112878)


        # Safe min/max zoom
        self.min_zoom = int(self.metadata.get("minzoom", 0))
        self.max_zoom = int(self.metadata.get("maxzoom", 18))
        self.default_zoom = int(self.metadata.get("defaultzoom", self.min_zoom))
# Patch MapView
#MapView.get_window_xy_from_mercator = get_window_xy_from_mercator

class DraggableButton(DragBehavior, Button):
    pass

class MapScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_widget = RootWidget()
        self.add_widget(self.root_widget)
        
    def on_pre_enter(self, *args):
        try:
            self.root_widget.refresh_active_user_label()
        except Exception:
            pass
            
class RootWidget(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.geotiff_overlay = None
        self.marker = None
        self.trial_markers = []
        self.mapview = MapView(zoom=11, lat=49.0, lon=-123.0)

        self.default_source = self.mapview.map_source
        self.mbtiles_source = None
        
        self.add_widget(self.mapview)
        
        self.active_user_lbl = Label(
            text="Active User: (none)",
            size_hint=(None, None),
            height=dp(28),
            width=dp(260),
            pos_hint={"x": 0.02, "top": 0.9},
            halign="left",
            valign="middle",
        )
        self.active_user_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        self.add_widget(self.active_user_lbl)

        self.refresh_active_user_label()
        
        # --- Dropdown menu setup ---
        self.dropdown = DropDown(width = 500)
        self.dropdown.auto_width = False
        #self.bind(size=lambda *_: setattr(self.dropdown, "width", self.width * 0.7))

        # Each button in dropdown
        def add_menu_item(label, callback):
            text_w = Label(text=label, font_size="18sp").texture_size[0]
            btn = Button(
                text=label,
                size_hint=(None, None),
                width=self.dropdown.width,
                height=75,
                font_size="18sp"
            )
            btn.bind(on_release=lambda btn: (self.dropdown.dismiss(), callback(btn)))
            self.dropdown.add_widget(btn)
            
        add_menu_item("Upload GeoTIFF", self.pick_geotiff)
        add_menu_item("Upload MBTiles", self.pick_mbtiles)
        add_menu_item("Remove GeoTIFF", self.remove_geotiff)
        add_menu_item("Remove MBTiles", self.remove_mbtiles)
        add_menu_item("Record New Trial", self.record_new_trial)
        add_menu_item("Sync with Server", self.sync_with_server)
        add_menu_item("Change user", self.change_user_popup)

        # --- Main menu button (top-right corner) ---
        self.menu_btn = DraggableButton(
            text="Options",
            size_hint = (0.16,0.08),
            pos_hint = {"right": 0.8, "top": 0.8}
        )

        self.menu_btn.bind(on_release=self.dropdown.open)
        self.add_widget(self.menu_btn)
        
    @mainthread
    def refresh_active_user_label(self, *_):
        try:
            prof = load_current_user_profile()  # your DB-backed helper
            if prof:
                self.active_user_lbl.text = f"Active User: {prof['username']}"
            else:
                self.active_user_lbl.text = "Active User: (none)"
        except Exception as e:
            print("⚠️ Could not refresh active user label:", e)
            self.active_user_lbl.text = "Active User: (error)"
        
    @mainthread
    def set_marker(self, lat, lon):
        self.lat, self.lon = lat, lon
        # 2) Create/update marker
        if self.marker is None:
            self.marker = MapMarker(lat=lat, lon=lon, source = "gps_purple.png")
            self.mapview.add_marker(self.marker)
            self.mapview.center_on(lat, lon)
        else:
            self.marker.lat, self.marker.lon = lat, lon
            
    def change_user_popup(self, instance=None):
        app = App.get_running_app()
        users = list_users()

        root = BoxLayout(orientation="vertical", spacing=10, padding=10)

        root.add_widget(Label(text="Select a user", size_hint_y=None, height=40))

        scroll = ScrollView()
        user_list = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        user_list.bind(minimum_height=user_list.setter("height"))

        popup = Popup(title="Change user", content=root, size_hint=(0.9, 0.9))

        def switch_to(user_uuid):
            set_current_user_uuid(user_uuid)
            prof = load_current_user_profile()
            app.user_profile = prof
            print(f"✅ Switched user to: {prof['username'] if prof else user_uuid}")
            self.refresh_active_user_label()
            popup.dismiss()

        for u in users:
            label = f"{u['username']}  —  {u['name']}"
            btn = Button(text=label, size_hint_y=None, height=60)
            btn.bind(on_release=lambda _btn, uid=u["user_uuid"]: switch_to(uid))
            user_list.add_widget(btn)

        scroll.add_widget(user_list)
        root.add_widget(scroll)

        btn_row = BoxLayout(size_hint_y=None, height=60, spacing=10)
        add_btn = Button(text="Add new user")
        close_btn = Button(text="Close")

        def add_new(_btn):
            popup.dismiss()
            TreeApp.instance.root.current = "login"
            
        add_btn.bind(on_release=add_new)
        close_btn.bind(on_release=lambda *_: popup.dismiss())

        btn_row.add_widget(add_btn)
        btn_row.add_widget(close_btn)
        root.add_widget(btn_row)

        popup.open()

#
    def remove_geotiff(self, instance=None):
        """Remove the GeoTIFF overlay from the map if it exists."""
        try:
            if self.geotiff_overlay.parent:
                self.geotiff_overlay.parent.remove_widget(self.geotiff_overlay)
            self.geotiff_overlay = None
            print("✅ GeoTIFF overlay removed.")
        except Exception as e:
            print(f"⚠️ Error removing overlay: {e}")

    def remove_mbtiles(self, instance=None):
        self.mapview.map_source = self.default_source
        self.mbtiles_source = None


    def pick_mbtiles(self, instance):
        chooser = FileChooserIconView(filters=["*.mbtiles"], rootpath = str(Path.home() / "Documents"))
        popup = Popup(title="Select an MBTiles file", content=chooser, size_hint=(0.9, 0.9))

        def load_selected_file(instance, selection, touch):
            if selection:
                popup.dismiss()
                self.load_mbtiles(selection[0])

        chooser.bind(on_submit=load_selected_file)
        popup.open()

    def load_mbtiles(self, path):
        print(f"Loading MBTiles: {path}")
        try:
            source = SafeMBTilesSource(path)
            #source.bounds = (-123, -48, -117, 63)
            source.bounds = False
            print(f"Bounds:{source.bounds}")
            #source._bounds = source.bounds
            self.mapview.map_source = source
            print(f"✅ Switched to MBTiles source: {path}")
        except Exception as e:
            print(f"❌ Error loading MBTiles: {e}")

    def pick_geotiff(self, instance):
        """Non-blocking file chooser popup for selecting a GeoTIFF."""

        # Popup layout
        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        filechooser = FileChooserListView(filters=['*.tif', '*.tiff'], rootpath = str(Path.home() / "Documents"))
        button_row = BoxLayout(size_hint_y=None, height='48dp', spacing=10)

        select_button = Button(text="Select", size_hint_x=0.5)
        cancel_button = Button(text="Cancel", size_hint_x=0.5)

        button_row.add_widget(select_button)
        button_row.add_widget(cancel_button)

        layout.add_widget(filechooser)
        layout.add_widget(button_row)

        popup = Popup(title="Select a GeoTIFF", content=layout, size_hint=(0.9, 0.9))

        # Handle file selection
        def select_file(_instance):
            if filechooser.selection:
                file_path = filechooser.selection[0]
                print(f"Loaded GeoTIFF: {file_path}")
                popup.dismiss()

                # ✅ Now call your existing overlay logic
                overlay = GeoTiffOverlay(file_path, self.mapview)
                self.mapview.add_widget(overlay)
                self.geotiff_overlay = overlay

        # Handle cancel
        def cancel_file(_instance):
            popup.dismiss()

        select_button.bind(on_release=select_file)
        cancel_button.bind(on_release=cancel_file)

        popup.open()
        
    def record_new_trial(self, instance):
        if self.lat is None or self.lon is None:
            print("⚠️ No GPS fix yet.")
            return
            
        popup = LocationPopup(self.lat, self.lon, self.create_trial_at)
        popup.open()

    def create_trial_at(self, lat, lon):
        print(f"Recording trial at {lat}, {lon}")

        # Create a marker with popup
        marker = MapMarkerPopup(lat=lat, lon=lon)
        label = Label(text="New Trial", size_hint=(None, None), size=(100, 40))
        marker.add_widget(label)
        self.mapview.add_marker(marker)

        # Open form popup
        popup = TrialFormPopup(lat, lon, self.save_trial)
        popup.open()
        
    def save_trial(self, data):
        """Save submitted trial data into the SQLite DB."""
        print("Saving trial:", data)
        app = App.get_running_app()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO trials (uuid, species, seedlings, seedlot, spacing, lat, lon, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (data["uuid"], data["species"], data["seedlings"], data["seedlot"],
              data["spacing"], data["lat"], data["lon"], app.user_profile["username"]))
        conn.commit()
        conn.close()
        print("✅ Trial saved.")
        
    @mainthread
    def load_trials(self):
        """Load all saved trials from SQLite and show them as markers."""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT uuid, id, species, seedlings, seedlot, spacing, lat, lon FROM trials")
            rows = c.fetchall()
            conn.close()

            print(f"📍 Loaded {len(rows)} trials from DB")

            for row in rows:
                uuid, trial_id, species, seedlings, seedlot, spacing, lat, lon = row
                if uuid not in self.trial_markers:
                    self.add_trial_marker(uuid, trial_id, species, seedlings, seedlot, spacing, lat, lon)
                    self.trial_markers.append(uuid)

        except Exception as e:
            print(f"⚠️ Error loading trials: {e}")
            
    def sync_with_server(self, instance):
        print("🔄 Starting sync...")
        upload_trials()
        download_trials()
        self.load_trials()   # refresh markers
        print("✅ Sync complete")

    
    def add_trial_marker(self, uuid, trial_id, species, seedlings, seedlot, spacing, lat, lon):
        """Create a marker for a trial and add it to the map."""
        marker = MapMarkerPopup(lat=lat, lon=lon)
        marker.trial_id = trial_id  # store id for deletion
        marker.uuid = uuid

        # --- Build popup content ---
        box = BoxLayout(orientation="vertical", spacing=4, padding=5, size_hint=(None, None))
        box.size = (600,600)
        
        with box.canvas.before:
            Color(0, 0, 0, 0.7)  # RGBA → black with 70% opacity
            box._bg_rect = Rectangle(pos=box.pos, size=box.size)

        # Keep background aligned when widget resizes
        def _update_bg(instance, value):
            box._bg_rect.pos = instance.pos
            box._bg_rect.size = instance.size

        box.bind(pos=_update_bg, size=_update_bg)

        info_text = (
            f"[b]Species:[/b] {species}\n"
            f"[b]Seedlings:[/b] {seedlings}\n"
            f"[b]Seedlot:[/b] {seedlot}\n"
            f"[b]Spacing:[/b] {spacing}\n"
        )

        info_label = Label(text=info_text, markup=True, halign="left", valign="middle")
        info_label.bind(size=lambda _, __: info_label.texture_update())
        box.add_widget(info_label)

        # --- Delete button ---
        delete_btn = Button(
            text="🗑️ Delete",
            size_hint_y=None,
            height=64,
            background_normal="",
            background_color=(0.8, 0.2, 0.2, 0.9),
        )
        delete_btn.bind(on_release=lambda instance: self.delete_trial(marker))
        box.add_widget(delete_btn)
        
        growth_button = Button(
            text="Add Assessment",
            size_hint_y=None,
            height=80,
            background_normal="",
            background_color=(0.8, 0.1, 0.8, 0.9),
        )
        growth_button.bind(on_release=lambda instance: self.open_growth_popup(marker))
        box.add_widget(growth_button)

        marker.add_widget(box)
        self.mapview.add_marker(marker)
        
        
    def open_growth_popup(self, marker):
        """Open the 5×5 assessment grid for this trial."""
        grid_data = self.load_growth_grid(marker)

        popup_box = BoxLayout(orientation="vertical", spacing=10, padding=10)

        # Create the grid widget
        self.growth_grid_widget = GrowthGrid(existing=grid_data)
        popup_box.add_widget(self.growth_grid_widget)

        save_btn = Button(
            text="Save Assessment",
            size_hint_y=None,
            height=60,
            background_normal="",
            background_color=(0.2, 0.6, 0.2, 1),
        )
        save_btn.bind(on_release=lambda *_: self.save_grid(marker))
        popup_box.add_widget(save_btn)

        self.assessment_popup = Popup(
            title="Tree Growth Assessment (5×5)",
            content=popup_box,
            size_hint=(0.9, 0.9),
        )
        self.assessment_popup.open()

    def save_grid(self, marker):
        grid = self.growth_grid_widget.get_grid()
        payload = json.dumps({"grid": grid})
        print("Grid data:", payload)

        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE trials
                SET growth_grid = ?
                WHERE uuid = ?
            """, (payload, marker.uuid))
            conn.commit()

        self.assessment_popup.dismiss()
        print(f"Saved growth grid for trial {marker.trial_id}")

        
    def load_growth_grid(self, marker):
        id = marker.uuid
        print(id)
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT growth_grid FROM trials WHERE uuid=?", (id,))
            row = cur.fetchone()
        print(row)
        if not row or row[0] is None:
            return None  # No grid stored yet

        try:
            data = json.loads(row[0])
            return data.get("grid")  # Should be a 5×5 list
        except Exception as e:
            print("Error parsing grid JSON:", e)
            return None
            
    def delete_trial(self, marker):
        trial_id = getattr(marker, "trial_id", None)
        if trial_id is None:
            print("⚠️ Marker missing trial_id")
            return

        # Remove from map
        try:
            self.mapview.remove_marker(marker)
        except Exception as e:
            print("⚠️ Could not remove marker:", e)

        # Remove from database
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM trials WHERE id = ?", (trial_id,))
            conn.commit()
            conn.close()
            print(f"🗑️ Deleted trial {trial_id}")
        except Exception as e:
            print("⚠️ Error deleting trial:", e)

    
class GeoTiffOverlay(Image):
    def __init__(self, geotiff_path, mapview: MapView, **kwargs):
        super().__init__(**kwargs)
        self.mapview = mapview

        with TiffFile(geotiff_path) as tif:
            img = tif.asarray()
            tags = tif.pages[0].tags

            # --- Extract approximate georeferencing ---
            model_tiepoint = tags.get("ModelTiepointTag")
            model_pixel_scale = tags.get("ModelPixelScaleTag")

            if model_tiepoint and model_pixel_scale:
                tiepoint = model_tiepoint.value
                scale = model_pixel_scale.value
                width = img.shape[-1]
                height = img.shape[-2]
                origin_x = tiepoint[3]
                origin_y = tiepoint[4]
                pixel_x = scale[0]
                pixel_y = scale[1]

                left = origin_x
                top = origin_y
                right = origin_x + width * pixel_x
                bottom = origin_y - height * pixel_y
                #self.merc_bounds = (left, bottom, right, top)
                
            print(f"Tiff shape: {img.shape}")
            if img.ndim == 3 and img.shape[2] >= 3:
                data = img[..., :3]
                data = np.nan_to_num(data).astype(np.uint8)
                print(f"Min val:{np.min(data)}; max val: {np.max(data)}")
                colorfmt = "rgb"
            else:
                data = img.astype(np.float32)
                data = 255 * (data - np.nanmin(data)) / (np.nanmax(data) - np.nanmin(data))
                data = np.nan_to_num(data).astype(np.uint8)
                colorfmt = "luminance"

            height, width = data.shape[:2]
            tex = Texture.create(size=(width, height), colorfmt=colorfmt)
            tex.blit_buffer(data.tobytes(), colorfmt=colorfmt, bufferfmt="ubyte")
            tex.flip_vertical()
            self.texture = tex
 

        # ✅ Convert bounds to WGS84 (lat/lon)
        
        ll_left, ll_bottom = webmercator_to_lonlat(left, bottom)
        ll_right, ll_top   = webmercator_to_lonlat(right, top)

        self.wgs_bounds = (ll_left, ll_bottom, ll_right, ll_top)
        print(f"File Bounds: {ll_left}, {ll_top}, {ll_right},{ll_bottom}")

        # Bind update on map movement
        self.mapview.bind(zoom=self.update_position, lat=self.update_position, lon=self.update_position)

    def update_position(self, *args):
        """Update overlay position and size relative to the map."""
        try:
            left, bottom, right, top = self.wgs_bounds  # in lon/lat order

            # MapView expects (lat, lon)
            x1, y1 = self.mapview.get_window_xy_from(top, left, self.mapview.zoom)      # top-left
            x2, y2 = self.mapview.get_window_xy_from(bottom, right, self.mapview.zoom)  # bottom-right

            self.pos = (x1, y2)
            self.size = (x2 - x1, y1 - y2)
            self.opacity = 0.6
            self.canvas.ask_update()

        except Exception as e:
            print("Error updating overlay position:", e)
            

class TreeApp(App):
    instance = None
    
    def build(self):
        TreeApp.instance = self
        self.user_profile = None

        init_db()

        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(MapScreen(name="map"))

        # Route based on whether profile exists
        prof = load_current_user_profile()
        if prof:
            self.user_profile = prof
            sm.current = "map"
        else:
            sm.current = "login"

        return sm  # Kivy assigns this to self.root
        
    def on_start(self):
        # Wait until root is built before starting GPS
        Clock.schedule_once(self.start_gps, 1.0)
        
        if self.root.current == "map":
            app = TreeApp.instance.get_root_widget().load_trials()
        
    def get_root_widget(self):
        """Convenience accessor for the existing RootWidget inside MapScreen."""
        map_screen = self.root.get_screen("map")
        return map_screen.root_widget
        
    def goto_login(self):
        if self.root:
            self.root.current = "login"
    
    def start_gps(self, dt):
        gps.configure(on_location=self.on_location)
        gps.start(minTime=1000, minDistance=1)
        
    def start(self, minTime, minDistance):
        gps.start(minTime, minDistance)

    def stop(self):
        gps.stop()

    @mainthread
    def on_location(self, **kwargs):
        lat, lon = kwargs.get("lat"), kwargs.get("lon")

        # If we're not on the map screen yet (user still on login), ignore GPS updates
        if not self.root or self.root.current != "map":
            return

        try:
            rw = self.get_root_widget()
            Clock.schedule_once(lambda dt: rw.set_marker(lat, lon))
        except Exception as e:
            print("⚠️ Could not set marker:", e)
        
    @mainthread
    def on_status(self, stype, status):
        self.gps_status = 'type={}\n{}'.format(stype, status)

    def on_pause(self):
        gps.stop()
        return True

    def on_resume(self):
        gps.start(1000, 0)
        pass

if __name__ == "__main__":
    TreeApp().run()

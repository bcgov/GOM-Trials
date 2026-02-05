from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.dropdown import DropDown
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy_garden.mapview import MapView, MapMarker, MapMarkerPopup
from kivy_garden.mapview.downloader import Downloader
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy_garden.mapview.view import MarkerMapLayer
from kivy.utils import platform
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.filechooser import FileChooserIconView
from kivy.clock import mainthread, Clock
from kivy.properties import StringProperty
from kivy.resources import resource_find
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.animation import Animation
from kivy.core.text import LabelBase
from kivy.uix.modalview import ModalView
from kivy.uix.spinner import Spinner
from pyobjus import autoclass, objc_str
from pyobjus.dylib_manager import load_framework

from threading import Thread
import time
import re
import os
import sys
import sqlite3
import requests
import datetime
import json
import uuid
import os.path
from plyer import gps

from assessment import GrowthCell, GrowthGrid
from config import DB_PATH, API_URL, USER_RE
from db_trials import upload_trials, download_trials, update_trial, get_trial_row, get_first_photo_for_trial
from db_users import init_db, list_users, get_current_user_uuid, set_current_user_uuid, load_current_user_profile, create_user_profile, get_active_user
from load_mbtiles import SafeMBTilesMapSource, OSMSource, GoogleHybridSource, GoogleTerrainSource
from load_tif import GeoTiffOverlay
from popups import LocationPopup, TrialFormPopup, DraggableButton, EditTrialPopup
from file_picker import pick_files
#from photos import IOSPhotoPicker

from kivy.properties import BooleanProperty
from kivy.graphics import Color, Rectangle
from kivy.uix.image import Image
    
class Scrim(Widget):
    active = BooleanProperty(False)

    def __init__(self, on_tap = None, **kwargs):
        super().__init__(**kwargs)
        self.on_tap = on_tap
        with self.canvas:
            self._color = Color(0, 0, 0, 0)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update, size=self._update, active=self._update_alpha)

    def _update(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _update_alpha(self, *args):
        self._color.a = 0.35 if self.active else 0

    def on_touch_down(self, touch):
        if self.active and self.collide_point(*touch.pos):
            if self.on_tap:
                self.on_tap()
            return True
        return super().on_touch_down(touch)
        
class BottomSafeZone(Widget):
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            return True  # swallow touches so map doesn't pan
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return super().on_touch_up(touch)

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
    
class RootWidget(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.geotiff_overlay = None
        self.marker = None
        self.trial_markers = []     # list of marker widgets
        self.trial_marker_uuids = set()   # fast duplicate check
        
        self.mapview = MapView(zoom=11, lat=49.0, lon=-123.0)
        self.default_source = self.mapview.map_source
        self.mbtiles_source = None
        
        self.add_widget(self.mapview)
        
        # --- Drawer config ---
        self.drawer_w = dp(280)
        self.drawer_open = False

        # --- Scrim (tap to close) ---
        self.scrim = Scrim(on_tap=self.close_drawer, size_hint=(1, 1))
        self.add_widget(self.scrim)

        # --- Drawer (starts off-screen to the left) ---
        self.drawer = BoxLayout(
            orientation="vertical",
            size_hint=(None, 1),
            width=self.drawer_w,
            x=-self.drawer_w,
            y=0,
            spacing=dp(10),
            padding=(dp(12), dp(20)),
        )
        self.add_widget(self.drawer)
        
        # Header row
        header = BoxLayout(size_hint=(1, None), height=dp(48))
        self.btn_close = Button(text="✕", size_hint=(None, 1), width=dp(48))
        self.btn_close.bind(on_release=self.close_drawer)
        header.add_widget(self.btn_close)

        header.add_widget(Label(text="Menu", halign="left", valign="middle"))
        self.drawer.add_widget(header)
        
        self.active_user_lbl = Label(
            text="Active User: (none)",
            size_hint=(None, None),
            height=dp(28),
            width=dp(260),
            halign="left",
            valign="middle",
        )
        self.active_user_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        self.drawer.add_widget(self.active_user_lbl)
        self.refresh_active_user_label()

        # Helper to add sidebar buttons
        def add_menu_item(label, callback):
            b = Button(
                text=label,
                size_hint=(1, None),
                height=dp(52),
                font_size="18sp",
            )
            b.bind(on_release=callback)
            self.drawer.add_widget(b)

        #add_menu_item("Upload GeoTIFF", self.pick_geotiff)
        add_menu_item("Record Trial", self.record_new_trial)
        add_menu_item("Sync with Server", self.sync_with_server)
        add_menu_item("Change user", self.change_user_popup)
        #add_menu_item("Upload MBTiles", self.pick_mbtiles)
        #add_menu_item("Remove GeoTIFF", self.remove_geotiff)
        #add_menu_item("Remove MBTiles", self.remove_mbtiles)
        
        self.map_style_spinner = Spinner(
            text="Map Type",
            values=[
                "OpenStreetMap",
                "Google Hybrid",
                "Google Terrain",
                "Custom MBTiles",
            ],
            size_hint=(1, None),
            height=dp(48),
        )

        self.map_style_spinner.bind(text=self.on_map_style_selected)
        self.drawer.add_widget(self.map_style_spinner)
        
        # Spacer to push things up
        self.drawer.add_widget(Widget())
        self.btn_open = Button(
            text="...",
            size_hint=(None, None),
            size=(dp(50), dp(50)),
            pos_hint={"x": 0.02, "top": 0.98},
        )
        self.btn_open.bind(on_release=self.open_drawer)
        self.add_widget(self.btn_open)
        self._set_scrim(False)
        
        self.safe_zone = BottomSafeZone(size_hint=(1, None), height=dp(28), pos_hint={"x": 0, "y": 0})
        self.add_widget(self.safe_zone)
        
    def on_map_style_selected(self, spinner, value):
        print(f"🌍 Switching to map style: {value}")

        if value == "OpenStreetMap":
            self.mapview.map_source = OSMSource()

        elif value == "Google Hybrid":
            self.mapview.map_source = GoogleHybridSource()

        elif value == "Google Terrain":
            self.mapview.map_source = GoogleTerrainSource()

        elif value == "Custom MBTiles":
            
            self.pick_mbtiles()

        
    def _set_scrim(self, open_):
        self.scrim.active = open_

    def open_drawer(self, *_):
        if self.drawer_open:
            return
        self.drawer_open = True
        self._set_scrim(True)
        Animation(x=0, d=0.18).start(self.drawer)

    def close_drawer(self, *_):
        if not self.drawer_open:
            return
        self.drawer_open = False
        self._set_scrim(False)
        Animation(x=-self.drawer_w, d=0.18).start(self.drawer)

 
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
            self.marker = MapMarker(lat=lat, lon=lon)
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

        popup = ModalView(size_hint=(0.9, 0.9))
        popup.add_widget(root)
        popup.bind(on_dismiss=lambda *_: self.on_user_switched())


        def switch_to(user_uuid):
                # Update stored user
                set_current_user_uuid(user_uuid)
                prof = load_current_user_profile()
                app.user_profile = prof
                print(f"✅ Switched user to: {prof['username'] if prof else user_uuid}")

                # Refresh sidebar label etc.
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

    def pick_mbtiles(self, *_):
        pick_files(exts=(".mbtiles",), callback=self._on_mbtiles_picked, subdir="mbtiles")

    def _on_mbtiles_picked(self, selection):
        print(f"In {selection}")
        if not selection:
            return
        path = selection[0]
        print(path)
        self.load_mbtiles(path)

    def load_mbtiles(self, path):
        print(f"Loading MBTiles: {path}")
        try:
            source = SafeMBTilesMapSource(path)
            #source.bounds = (-123, -48, -117, 63)
            source.bounds = False
            print(f"Bounds:{source.bounds}")
            #source._bounds = source.bounds
            self.mapview.map_source = source
            print(f"✅ Switched to MBTiles source: {path}")
        except Exception as e:
            print(f"❌ Error loading MBTiles: {e}")

    def pick_geotiff(self, *_):
        pick_files(exts=(".tif", ".tiff"), callback=self._on_tif_picked, subdir="geotiff")

    def _on_tif_picked(self, selection):
        if not selection:
            return
        path = selection[0]
        # Use your existing GeoTIFF loader / overlay
        overlay = GeoTiffOverlay(path, self.mapview)
        self.mapview.add_widget(overlay)
        self.geotiff_overlay = overlay
        
    def record_new_trial(self, instance):
        if self.lat is None or self.lon is None:
            print("⚠️ No GPS fix yet.")
            return
            
        popup = LocationPopup(self.lat, self.lon, self.create_trial_at)
        popup.open()

    def create_trial_at(self, lat, lon):
        print(f"Recording trial at {lat}, {lon}")

        # Open form popup
        popup = TrialFormPopup(lat, lon, self.save_trial)
        popup.open()
        
    def save_trial(self, data):
        """Save submitted trial data into the SQLite DB."""
        print("Saving trial:", data)
        #app = App.get_running_app()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO trials (uuid, species, seedlings, seedlot, spacing, lat, lon, user_id, site_series, smr, snr, site_fact, site_prep)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data["uuid"], data["species"], data["seedlings"], data["seedlot"],
              data["spacing"], data["lat"], data["lon"], get_active_user()["username"], data["site_series"], data["smr"], data["snr"], data["site_factors"], data["site_prep"]))
            
        #save photo paths
        for p in data.get("photo_paths", []):
            c.execute("INSERT INTO trial_photos (trial_uuid, path) VALUES (?, ?)", (data["uuid"], p))

        conn.commit()
        conn.close()
        print("✅ Trial saved.")
        
        self.add_trial_marker(
            uuid=data["uuid"],
            user_id=get_active_user()["username"],
            trial_id=c.lastrowid,
            species=data["species"],
            seedlings=data["seedlings"],
            seedlot=data["seedlot"],
            spacing=data["spacing"],
            lat=data["lat"],
            lon=data["lon"],
        )
        
        
    def clear_all_trial_markers(self):
        print("🧹 Clearing all trial markers")

        # Remove markers from the map
        for m in self.trial_markers:
            try:
                self.mapview.remove_widget(m)
            except Exception as e:
                print("⚠️ Error removing marker:", e)

        # Reset tracking
        self.trial_markers.clear()
        self.trial_marker_uuids.clear()
        
    # Async stuff
    def _load_trials_in_background(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT uuid, user_id, id, species, seedlings, seedlot, spacing, lat, lon FROM trials")
            rows = c.fetchall()
            conn.close()

            print(f"📥 Background loaded {len(rows)} trials")

            # schedule adding them gradually
            Clock.schedule_once(lambda dt: self._add_trial_markers_generator(rows))
        except Exception as e:
            print(f"⚠️ Background trial load error: {e}")
            
    def _add_trial_markers_generator(self, rows, batch_size=50):
        """
        Add markers in small batches so UI stays responsive.
        """
        total = len(rows)
        idx = 0

        def add_next_batch(dt):
            nonlocal idx
            end = min(idx + batch_size, total)

            for i in range(idx, end):
                uuid, user_id, trial_id, species, seedlings, seedlot, spacing, lat, lon = rows[i]
                if uuid not in self.trial_marker_uuids:
                    self.add_trial_marker(uuid, user_id, trial_id, species, seedlings, seedlot, spacing, lat, lon)

            idx = end
            #print(f"📍 Added {end} / {total}")

            if idx < total:
                # schedule next batch
                Clock.schedule_once(add_next_batch, 0)
            else:
                print("✅ All markers added")

        Clock.schedule_once(add_next_batch, 0)


    def on_user_switched(self):
        print("🧹 Clearing all trial markers")
        self.clear_all_trial_markers()

        # Load all rows in background
        Thread(target=self._load_trials_in_background, daemon=True).start()


    def load_trials(self):
        """Load all saved trials from SQLite and show them as markers."""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT uuid, user_id, id, species, seedlings, seedlot, spacing, lat, lon FROM trials")
            rows = c.fetchall()
            conn.close()

            print(f"📍 Loaded {len(rows)} trials from DB")

            for row in rows:
                uuid, user_id, trial_id, species, seedlings, seedlot, spacing, lat, lon = row
                if uuid not in self.trial_marker_uuids:
                    self.add_trial_marker(uuid, user_id, trial_id, species, seedlings, seedlot, spacing, lat, lon)
                    

        except Exception as e:
            print(f"⚠️ Error loading trials: {e}")
            
    def sync_with_server(self, instance):
        print("🔄 Starting sync...")
        download_trials()
        upload_trials()
        self.load_trials()   # refresh markers
        print("✅ Sync complete")

    
    def add_trial_marker(self, uuid, user_id, trial_id, species, seedlings, seedlot, spacing, lat, lon):
        """Create a lightweight marker which builds its popup only on tap."""
        is_mine = (get_active_user()["username"] == user_id)
        icon = "user_icon.png" if is_mine else "gps_purple.png"

        marker = MapMarkerPopup(lat=lat, lon=lon, source=icon)
        marker.uuid = uuid
        marker.trial_id = trial_id

        # Store only the bare data needed to build the popup later
        marker.trial_data = {
            "uuid": uuid,
            "user_id": user_id,
            "species": species,
            "seedlings": seedlings,
            "seedlot": seedlot,
            "spacing": spacing,
            "lat": lat,
            "lon": lon,
        }

        # Build popup lazily on tap
        marker.bind(on_release=lambda instance: self.open_trial_popup(instance))

        self.mapview.add_marker(marker)
        self.trial_markers.append(marker)
        self.trial_marker_uuids.add(uuid)
        
        
    def open_trial_popup(self, marker):
        """Builds a popup that looks like the old one (600x600 w/ translucent bg)."""

        d = marker.trial_data

        # Main container with explicit size
        box = BoxLayout(
            orientation="vertical",
            spacing=4,
            padding=5,
            size_hint=(None, None),
            width=600,
            height=600,
        )

        # --- Background rectangle (shared texture, no per-marker memory bloat) ---
        with box.canvas.before:
            Color(0, 0, 0, 0.7)  # translucent black
            bg = Rectangle(pos=box.pos, size=box.size)

        def _update_bg(*_):
            bg.pos = box.pos
            bg.size = box.size

        box.bind(pos=_update_bg, size=_update_bg)

        # --- Info text ---
        info_text = (
            f"[b]User:[/b] {d['user_id']}\n"
            f"[b]Species:[/b] {d['species']}\n"
            f"[b]Seedlings:[/b] {d['seedlings']}\n"
            f"[b]Seedlot:[/b] {d['seedlot']}\n"
            f"[b]Spacing:[/b] {d['spacing']}\n"
        )

        info_label = Label(
            text=info_text,
            markup=True,
            halign="left",
            valign="top",
            size_hint=(1, None),
        )
        info_label.bind(
            texture_size=lambda lbl, _: setattr(lbl, "height", lbl.texture_size[1])
        )
        box.add_widget(info_label)
        
        photo_path = get_first_photo_for_trial(marker.uuid)
        if photo_path:
            view_btn = Button(
                text="View Photo",
                size_hint_y=None,
                height=64,
                background_normal="",
                background_color=(0.2, 0.8, 0, 0.9),
            )
            view_btn.bind(
                on_release=lambda *_: self.open_photo_popup(photo_path)
            )
            box.add_widget(view_btn)

        # --- Delete button ---
        delete_btn = Button(
            text="Delete",
            size_hint_y=None,
            height=64,
            background_normal="",
            background_color=(0.8, 0.2, 0.2, 0.9),
        )
        delete_btn.bind(
            on_release=lambda *_: (popup.dismiss(), self.delete_trial(marker))
        )
        box.add_widget(delete_btn)

        # --- Edit Trial ---
        edit_btn = Button(
            text="Edit Trial",
            size_hint_y=None,
            height=64,
            background_normal="",
            background_color=(0.2, 0.4, 0.9, 0.9),
        )
        edit_btn.bind(
            on_release=lambda *_: (popup.dismiss(), self.open_edit_trial(marker))
        )
        box.add_widget(edit_btn)

        # --- Assessment ---
        growth_button = Button(
            text="Add Assessment",
            size_hint_y=None,
            height=80,
            background_normal="",
            background_color=(0.8, 0.1, 0.8, 0.9),
        )
        growth_button.bind(
            on_release=lambda *_: (popup.dismiss(), self.open_growth_popup(marker))
        )
        box.add_widget(growth_button)

        # --- Popup wrapper ---
        popup = Popup(
            title=" ",
            content=box,
            size_hint=(None, None),
            size=(660, 660),     # slightly larger container so 600px fits comfortably
            auto_dismiss=True,
        )

        popup.open()
        
    def open_photo_popup(self, path):
        # Full-size image widget
        img = Image(
            source=path,
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(1, 1),
        )

        popup = Popup(
            title="Trial Photo",
            content=img,
            size_hint=(0.8, 0.8),
            auto_dismiss=True,
        )
        popup.open()

        
    def open_edit_trial(self, marker):
        uuid = marker.uuid
        trial = get_trial_row(uuid)
        if not trial:
            print("⚠️ Trial not found:", uuid)
            return

        def _on_save(edited):
            update_trial(
                uuid=uuid,
                data=edited
            )
            print("✅ Trial updated locally, marked for sync")

            # Optional: refresh markers/popup UI
            # self.refresh_trial_marker(uuid)

        EditTrialPopup(trial_row=trial, on_save=_on_save).open()
        
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

class TreeApp(App):
    instance = None
    picker_delegate = None
    
    def build(self):
        
        TreeApp.instance = self
        self.user_profile = None
        #Window.softinput_mode = "pan"
        #LabelBase.register(name="SF", fn_regular="System Font")
        
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
        
#            
#    def test_pick_image(self):
#        print("Opening photo picker…")
#
#        picker = UIImagePickerController.alloc().init()
#        picker.sourceType = 1  # Photo Library
#
#        delegate = ImagePickerDelegate.alloc().init()
#        self.picker_delegate = delegate
#
#        picker.delegate = delegate
#
#        # Present picker
#        app = UIApplication.sharedApplication()
#        root = app.keyWindow.rootViewController()
#        root.presentViewController_animated_completion_(picker, True, None)
#
#        # Start polling for result
#        self._picker_poll_ev = Clock.schedule_interval(self.check_picker_result, 0.25)
#        
#    def check_picker_result(self, dt):
#        docs = self.get_ios_documents_dir()
#        ipc_dir = os.path.join(docs, "gomapp_ipc")
#        result_file = os.path.join(ipc_dir, "picker_result.txt")
#
#        # Small, readable debug
#        print("IPC dir:", ipc_dir)
#        try:
#            print("IPC listing:", os.listdir(ipc_dir))
#        except FileNotFoundError:
#            print("IPC dir missing")
#            return
#
#        if not os.path.exists(result_file):
#            return  # keep polling
#
#        with open(result_file, "r") as f:
#            result = f.read().strip()
#        os.remove(result_file)
#
#        print("Picked image result:", result)
#        if getattr(self, "_picker_poll_ev", None) is not None:
#            self._picker_poll_ev.cancel()
#            self._picker_poll_ev = None
#        
#        if result != "__cancelled__":
#            self.show_picked_image(result)
#            
#    def show_picked_image(self, img_path: str):
#        # Create once
#        if getattr(self, "picked_image_widget", None) is None:
#            self.picked_image_widget = Image(
#                source=img_path,
#                allow_stretch=True,
#                keep_ratio=True,
#                size_hint=(1, None),
#                height=dp(260),   # tweak as you like
#            )
#            # Add it wherever makes sense (root layout / a specific panel)
#            self.root.current_screen.add_widget(self.picked_image_widget)
#        else:
#            self.picked_image_widget.source = img_path
#
#        # Force refresh (important on iOS)
#        self.picked_image_widget.reload()


if __name__ == "__main__":
    TreeApp().run()

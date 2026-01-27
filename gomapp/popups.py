from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.behaviors import DragBehavior
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.uix.spinner import Spinner
from kivy.uix.togglebutton import ToggleButton
from kivy.animation import Animation


import uuid

SMR_OPTIONS = ["(Select)", "VX", "X", "SX", "SM", "M", "SHG","HG","SHD","HD"]
SNR_OPTIONS = ["(Select)", "Very Poor", "Poor", "Medium", "Rich", "Very Rich"]
SITE_FACTORS_OPTIONS = ["(Select)", "Compated morainal material", "Strongly cemented horizon", "Lithic contact","Excessive moisture","Permafrost","Fragmental","Snow Accumulation","Wind","Salt spray", "Frost", "Insolation", "Cold air drainage"]
SITE_PREP_OPTIONS = ["(Select)", "Spot Burn", "Mechanical & Spot Burn", "Mechanical", "Grass Seeded", "Chemical", "Broadcast Burn"]


class LocationPopup(Popup):
    def __init__(self, default_lat, default_lon, on_confirm, **kwargs):
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)
        self.title = "Set Trial Location"
        self.size_hint = (0.92, 0.75)  # <- a bit taller helps a lot
        self.on_confirm = on_confirm

        root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        scroll = ScrollView(size_hint=(1, 1))
        form = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        self.lat_input = TextInput(text=str(default_lat), hint_text="Latitude",
                                   multiline=False, size_hint_y=None, height=dp(44))
        self.lon_input = TextInput(text=str(default_lon), hint_text="Longitude",
                                   multiline=False, size_hint_y=None, height=dp(44))
                                   
#        def ensure_visible(ti):
#            def _on_focus(_inst, focused):
#                if focused:
#                    Clock.schedule_once(lambda dt: scroll.scroll_to(ti, padding=dp(20)), 0)
#            ti.bind(focus=_on_focus)
#
#        ensure_visible(self.lat_input)
#        ensure_visible(self.lon_input)

        form.add_widget(Label(text="Latitude", size_hint_y=None, height=dp(20)))
        form.add_widget(self.lat_input)
        form.add_widget(Label(text="Longitude", size_hint_y=None, height=dp(20)))
        form.add_widget(self.lon_input)

        # ✅ Spacer so fields can scroll above the button row + keyboard
        form.add_widget(Widget(size_hint_y=None, height=dp(120)))

        scroll.add_widget(form)
        root.add_widget(scroll)

        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        btn_cancel = Button(text="Cancel")
        btn_create = Button(text="Create")
        btn_cancel.bind(on_release=lambda *_: self.dismiss())
        btn_create.bind(on_release=self.confirm)
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_create)
        root.add_widget(btn_row)

        self.content = root
        
    def confirm(self, *_):
        try:
            lat = float(self.lat_input.text)
            lon = float(self.lon_input.text)
        except ValueError:
            print("⚠️ Invalid coordinates")
            return
        self.on_confirm(lat, lon)
        self.dismiss()


class TrialFormPopup(Popup):
    def __init__(self, lat, lon, on_submit, **kwargs):
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)
        self.title = "Record New Trial"
        self.size_hint = (0.92, 0.8)
        self.lat, self.lon = lat, lon
        self.on_submit = on_submit

        root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        scroll = ScrollView(size_hint=(1, 1))
        form = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        def add_field(label, ti):
            form.add_widget(Label(text=label, size_hint_y=None, height=dp(20), halign="left", valign="middle"))
            form.add_widget(ti)

        self.species = TextInput(hint_text="Species", multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        self.seedlings = TextInput(hint_text="Number of Seedlings", input_filter="int",
                                   multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        self.seedlot = TextInput(hint_text="Seedlot", multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        self.spacing = TextInput(hint_text="Spacing (e.g. 3x3m)", multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        
                # Fields inside site_box
        self.site_series = TextInput(
            hint_text="e.g., CWHvm1/01 (optional)",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )

        self.smr = Spinner(
            text="",
            values=SMR_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )
        self.snr = Spinner(
            text="",
            values=SNR_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )
        self.site_factors = Spinner(
            text="",
            values=SITE_FACTORS_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )
        self.site_prep = Spinner(
            text="",
            values=SITE_PREP_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )

        add_field("Species", self.species)
        add_field("Number of Seedlings", self.seedlings)
        add_field("Seedlot", self.seedlot)
        add_field("Spacing", self.spacing)
        add_field("Site series", self.site_series)
        add_field("SMR", self.smr)
        add_field("SNR", self.snr)
        add_field("Site/Soil Factors", self.site_factors)
        add_field("Site Prep", self.site_prep)

        # Give some scroll padding so last fields aren't under button row/keyboard
        form.add_widget(Widget(size_hint_y=None, height=dp(140)))

        scroll.add_widget(form)
        root.add_widget(scroll)

        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        btn_cancel = Button(text="Cancel")
        btn_submit = Button(text="Submit")
        btn_cancel.bind(on_release=lambda *_: self.dismiss())
        btn_submit.bind(on_release=self.submit_form)
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_submit)
        root.add_widget(btn_row)

        self.content = root
        

    def submit_form(self, *_):
        data = {
            "uuid": str(uuid.uuid4()),
            "species": self.species.text.strip(),
            "seedlings": self.seedlings.text.strip(),
            "seedlot": self.seedlot.text.strip(),
            "spacing": self.spacing.text.strip(),
            "lat": self.lat,
            "lon": self.lon,
            
            "site_series": self.site_series.text.strip(),
            "smr": "" if self.smr.text == "(select)" else self.smr.text,
            "snr": "" if self.snr.text == "(select)" else self.snr.text,
            "site_factors": "" if self.site_factors.text == "(select)" else self.site_factors.text,
            "site_prep": "" if self.site_prep.text == "(select)" else self.site_prep.text,
        }
        self.on_submit(data)
        self.dismiss()


class DraggableButton(DragBehavior, Button):
    pass

class EditTrialPopup(Popup):
    def __init__(self, trial_row: dict, on_save, **kwargs):
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)
        self.title = "View/Edit Trial"
        self.size_hint = (0.92, 0.85)

        self.trial = trial_row
        self.on_save = on_save

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

        scroll = ScrollView(size_hint=(1, 1))
        form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        # --- inputs (same as you already have) ---
        self.species_in = TextInput(text=trial_row.get("species", "") or "", multiline=False, size_hint_y=None, height=dp(44))
        self.seedlings_in = TextInput(text=str(trial_row.get("seedlings", "") or ""), multiline=False, input_filter="int",
                                      size_hint_y=None, height=dp(44))
        self.seedlot_in = TextInput(text=trial_row.get("seedlot", "") or "", multiline=False, size_hint_y=None, height=dp(44))
        self.spacing_in = TextInput(text=trial_row.get("spacing", "") or "", multiline=False, size_hint_y=None, height=dp(44))
        self.site_series = TextInput(text=trial_row.get("site_series", "") or "", multiline=False, size_hint_y=None, height=dp(44))

        self.smr = Spinner(text=trial_row.get("smr", "(Select)") or "(Select)", values=SMR_OPTIONS, size_hint_y=None, height=dp(44))
        self.snr = Spinner(text=trial_row.get("snr", "(Select)") or "(Select)", values=SNR_OPTIONS, size_hint_y=None, height=dp(44))
        self.site_factors = Spinner(text=trial_row.get("site_factors", "(Select)") or "(Select)", values=SITE_FACTORS_OPTIONS, size_hint_y=None, height=dp(44))
        self.site_prep = Spinner(text=trial_row.get("site_prep", "(Select)") or "(Select)", values=SITE_PREP_OPTIONS, size_hint_y=None, height=dp(44))

        def add_field(label, widget):
            form.add_widget(Label(text=label, size_hint_y=None, height=dp(18), halign="left", valign="middle"))
            form.add_widget(widget)

        add_field("Species", self.species_in)
        add_field("Seedlings", self.seedlings_in)
        add_field("Seedlot", self.seedlot_in)
        add_field("Spacing", self.spacing_in)
        add_field("Site series", self.site_series)
        add_field("SMR", self.smr)
        add_field("SNR", self.snr)
        add_field("Site Factors", self.site_factors)
        add_field("Site Prep", self.site_prep)

        # Spacer so last field can scroll above the fixed buttons
        form.add_widget(Widget(size_hint_y=None, height=dp(140)))

        scroll.add_widget(form)
        root.add_widget(scroll)

        # Fixed button row (not scrollable)
        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
        btn_cancel = Button(text="Cancel")
        btn_save = Button(text="Save")
        btn_cancel.bind(on_release=lambda *_: self.dismiss())
        btn_save.bind(on_release=self._save)
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_save)
        root.add_widget(btn_row)

        self.content = root


    def _save(self, *_):
        data = {
            "species": self.species_in.text.strip(),
            "seedlings": int(self.seedlings_in.text) if self.seedlings_in.text.strip() else None,
            "seedlot": self.seedlot_in.text.strip(),
            "spacing": self.spacing_in.text.strip(),
            
            "site_series": self.site_series.text.strip(),
            "smr": "" if self.smr.text == "(select)" else self.smr.text,
            "snr": "" if self.snr.text == "(select)" else self.snr.text,
            "site_factors": "" if self.site_factors.text == "(select)" else self.site_factors.text,
            "site_prep": "" if self.site_prep.text == "(select)" else self.site_prep.text,
        }
        self.on_save(data)
        self.dismiss()

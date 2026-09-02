import uuid
import copy
import datetime
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
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
from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from photos import IOSPhotoPicker
from db_users import download_trial_owners
from gom_logger import logger
from utils import RoundedButton
from assessment import AssessmentPanel, GrowthGrid, AssessmentNavigator
from assessment_db import get_trial_assessment_uuids, load_assessment, create_assessment, get_grid_direction
from db_trials import get_most_recent_trial, add_trial_owner, get_replicate_no, get_trial_owners, get_trial_year_range
from db_users import load_current_user_profile, get_active_user, set_app_state, get_app_state
from numeric_entry import NativeNumericField

SMR_OPTIONS = ["(Select)", "0 - Very Xeric", "1 - Xeric", "2 - Subxeric", "3 - Submesic", "4 - Mesic", "5 - Subhygric", "6 - Hygric", "7 - Subhydric", "8 - Hydric"]
SNR_OPTIONS = ["(Select)", "A - Very Poor", "B - Poor", "C - Medium", "D - Rich", "E - Very Rich", "F - Saline/Alkaline"]
SITE_FACTORS_OPTIONS = ["(Select)", "Compated morainal material", "Strongly cemented horizon", "Lithic contact","Excessive moisture","Permafrost","Fragmental","Snow Accumulation","Wind","Salt spray", "Frost", "Insolation", "Cold air drainage"]
SITE_PREP_OPTIONS = ["(Select)", "Spot Burn", "Mechanical & Spot Burn", "Mechanical", "Grass Seeded", "Chemical", "Broadcast Burn"]
SPECIES = {'Fdc': 'Douglas-fir (coastal)', 
           'Fdi': 'Douglas-fir (inland)', 
           'Lw': 'Western larch', 
           'Pw': 'Western white pine', 
           'Cw': 'Western redcedar', 
           'Hw': 'Western hemlock', 
           'Bg': 'Grand fir', 
           'Py': 'Ponderosa pine',
           'Ba': 'amabilis fir', 
           'Bl': 'subalpine fir', 
           'Fd': 'Douglas-fir', 
           'Hm': 'mountain hemlock', 
           'La': 'subalpine larch', 
           'Lt': 'tamarack larch', 
           'Pa': 'whitebark pine', 
           'Pf': 'limber pine', 
           'Pj': 'jack pine', 
           'Pl': 'lodgepole pine', 
           'Plc': 'shore pine', 
           'Pli': 'interior lodgepole pine', 
           'Pxj': 'Murraybanks\' pine', 
           'Pyi': 'Rocky Mountain ponderosa pine', 
           'Sb': 'black spruce', 
           'Se': 'Engelmann spruce', 
           'Ss': 'Sitka spruce', 
           'Sw': 'white spruce', 
           'Sx': 'spruce hybrid', 
           'Sxl': 'Lutz\' spruce', 
           'Sxs': 'Sitka x unknown spruce hybrid', 
           'Sxw': 'interior spruce', 
           'Tw': 'Pacific yew', 
           'Yc': 'yellow-cedar', 
           'A': 'poplars', 
           'Acb': 'balsam poplar', 
           'Act': 'black cottonwood', 
           'At': 'trembling aspen', 
           'Dr': 'red alder', 
           'Ep': 'paper birch', 
           'Mb': 'bigleaf maple', 
           'Qg': 'Garry oak', 
           'Ra': 'Pacific arbutus', 
           'Ld': 'Dahurian larch', 
           'Ls': 'Siberian larch', 
           'Pr': 'red pine', 
           'Pz': 'Scots pine', 
           'Sn': 'Norway spruce', 
           'Ax': 'poplar hybrids', 
           'Bb': 'balsam fir', 
           'Bc': 'white fir',
           'Bm': 'red fir', 
           'Bm': 'Shasta red fir', 
           'Bp': 'noble fir', 
           'Oa': 'incense cedar', 
           'Ob': 'giant sequoia', 
           'Oc': 'coast redwood', 
           'Ps': 'sugar pine', 
           'Pyc': 'Columbia ponderosa pine', 
           'Yp': 'Port Orford-cedar', 
           'Og': 'Oregon ash', 
           'Oh': 'white ash'
 }
SEEDLOTS = {
    "Py": ["54134"],
    "Pw": ["64040"],
    "Lw": ["63375"],
    "Cw": ["54074"],
    "Fdi": ["47996"],
    "Bg": ["44017"]
}

REQUESTS = {
    "Py": ["2025DKA0016"],
    "Pw": ["2025DSE0018"],
    "Lw": ["2025DND0069"],
    "Cw": ["2025DSE0024", "2025DSE0102"],
    "Fdi": ["2025DPG0061"],
    "Bg": ["2025DSE0076"]
}

PHOTO_PICKER = IOSPhotoPicker()


class LocationPopup(Popup):
    def __init__(self, gps_fix, gps_status, on_confirm, **kwargs):
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)

        if not gps_status["valid"]:
            popup = Popup(title="GPS Error", content=Label(text="No valid GPS fix available. Please try again."), size_hint=(0.8, 0.4))
            return popup
        
        self.title = "Set Trial Location"
        self.size_hint = (0.92, 0.75)  # <- a bit taller helps a lot
        self.on_confirm = on_confirm
        self.owner = None

        root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        scroll = ScrollView(size_hint=(1, 1))
        form = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        prev_trial = get_most_recent_trial() or dict()  # avoid None if no trials yet

        self.lat_input = TextInput(text=str(gps_fix["lat"]), hint_text="Latitude",
                                   multiline=False, size_hint_y=None, height=dp(44))
        self.lon_input = TextInput(text=str(gps_fix["lon"]), hint_text="Longitude",
                                   multiline=False, size_hint_y=None, height=dp(44))
        self.elev_input = TextInput(text=str(gps_fix["elev"]), hint_text="Elevation (m)",
                                    multiline=False, size_hint_y=None, height=dp(44))
        self.block_input = TextInput(text=get_app_state("current_block") or "", hint_text="Block name",
                                    multiline=False, size_hint_y=None, height=dp(44))
                                   

        form.add_widget(Label(text=(
                            f"GPS: {gps_status['accuracy']:.0f} m • "
                            f"{gps_status['age']:.0f} s"
                        ), size_hint_y=None, height=dp(25)))
        form.add_widget(Label(text="Latitude", size_hint_y=None, height=dp(20)))
        form.add_widget(self.lat_input)
        form.add_widget(Label(text="Longitude", size_hint_y=None, height=dp(20)))
        form.add_widget(self.lon_input)
        form.add_widget(Label(text="Elevation", size_hint_y=None, height=dp(20)))
        form.add_widget(self.elev_input)
        form.add_widget(Label(text="Block name *", size_hint_y=None, height=dp(20)))
        form.add_widget(self.block_input)

        # need to collect trial_owner info here; we'll have a spinner with existing trial companies from database table, and an "Other" option that shows text inputs for company name and contact info (email or phone)
        
        try:
            download_trial_owners()
        except Exception as e:
            print(f"⚠️ Error downloading trial owners: {e}")

        owner_list = get_trial_owners()
        self.owner_spinner = Spinner(text=get_app_state("trial_owner") or "Select Trial Owner", values=[x for x in owner_list] + ["Other"], size_hint_y=None, height=dp(44))
        form.add_widget(Label(text="Trial owner", size_hint_y=None, height=dp(20)))
        form.add_widget(self.owner_spinner)

        self.other_inputs_layout = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.other_inputs_layout.bind(minimum_height=self.other_inputs_layout.setter("height"))
        self.company_name_input = TextInput(hint_text="Company name", multiline=False, size_hint_y=None, height=dp(44))
        self.contact_name_input = TextInput(hint_text="Owner name", multiline=False, size_hint_y=None, height=dp(44))
        self.contact_email_input = TextInput(hint_text="Contact email", multiline=False, size_hint_y=None, height=dp(44))
        self.objective_input = TextInput(hint_text="Objective", multiline=False, size_hint_y=None, height=dp(44))
        self.owner_create_btn = Button(text="Create owner", size_hint_y=None, height=dp(44))
        self.other_inputs_layout.add_widget(Label(text="Owner name", size_hint_y=None, height=dp(20)))
        self.other_inputs_layout.add_widget(self.contact_name_input)
        self.other_inputs_layout.add_widget(Label(text="Company name", size_hint_y=None, height=dp(20)))
        self.other_inputs_layout.add_widget(self.company_name_input)
        self.other_inputs_layout.add_widget(Label(text="Contact email", size_hint_y=None, height=dp(20)))
        self.other_inputs_layout.add_widget(self.contact_email_input)
        self.other_inputs_layout.add_widget(Label(text="Objective", size_hint_y=None, height=dp(20)))
        self.other_inputs_layout.add_widget(self.objective_input)
        self.other_inputs_layout.add_widget(self.owner_create_btn)
        

        owner_popup = Popup(title="Add trial owner", content=self.other_inputs_layout, size_hint=(0.9, None), height=dp(400), auto_dismiss=True)

        def confirm_owner(_):
            company = self.company_name_input.text.strip()
            contact_name = self.contact_name_input.text.strip()
            contact_email = self.contact_email_input.text.strip()
            objective = self.objective_input.text.strip()

            if not contact_name:
                print("Owner name required")
                return

            owner_list = get_trial_owners()
            if contact_name in owner_list:
                print("Owner already exists")
                return

            add_trial_owner(company, contact_name, contact_email, objective)
            set_app_state("trial_owner", contact_name)
            self.owner = contact_name
            self.owner_spinner.values = [contact_name] + self.owner_spinner.values[:-1]  # add new owner to spinner, before "Other"
            owner_popup.dismiss()

        self.owner_create_btn.bind(on_release=confirm_owner) 


        def on_spinner_select(spinner, text):
            if text == "Other":
                owner_popup.open()
            else:                
                self.owner = text
                set_app_state("trial_owner", self.owner)
   
        self.owner_spinner.bind(text=on_spinner_select)

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
            elev = float(self.elev_input.text)
            block_name = self.block_input.text.strip()
            owner = self.owner
            set_app_state("current_block", block_name)
        except ValueError:
            print("⚠️ Invalid coordinates or elevation")
            return
        self.on_confirm(lat, lon, elev, owner, block_name)
        self.dismiss()


class TrialFormPopup(Popup):
    def __init__(self, lat, lon, elev, owner, block_name, on_submit, **kwargs):
        kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)
        self.title = "Record New Trial"
        self.size_hint = (0.92, 0.8)
        self.lat, self.lon, self.elev = lat, lon, elev
        self.owner = owner
        self.block_name = block_name
        self.on_submit = on_submit
        self.bind(on_dismiss=self.destroy)

        root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        scroll = ScrollView(size_hint=(1, 1))
        form = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))
        
        # --- Photos ---
        self.photo_paths = []

        # Preview (for now: show last selected photo, full-res)
        self.photo_preview = Image(
            size_hint_y=None,
            height=dp(220),
            allow_stretch=True,
            keep_ratio=True,
        )
        self.prev_trial = get_most_recent_trial() or dict()  # avoid None if no trials yet
        print("Most recent trial:", self.prev_trial)

        def add_field(label, ti):
            form.add_widget(Label(text=label, size_hint_y=None, height=dp(20), halign="left", valign="middle"))
            form.add_widget(ti)

        self.species = Spinner(text="Species", values=[f"{k} - {v}" for k,v in SPECIES.items()], size_hint_y=None, height=dp(44))
        self.species.bind(is_open=self._hide_fields)
        self.replicate_no = NativeNumericField(decimal=False, size_hint=(1, None), height=dp(44))
        self.replicate_no.text = "1"

        self.seedlings = NativeNumericField(
                    decimal=False,
                    size_hint=(1, None),
                    height=dp(44),
                )
        self.seedlot = TextInput(text = self.prev_trial.get("seedlot", "") if self.prev_trial.get("seedlot") is not None else "", multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        self.spacing = NativeNumericField(decimal = True, size_hint_y=None, height=dp(44))
        self.spacing.placeholder = "Spacing (m)"
        self.request_key = TextInput(text = self.prev_trial.get("request_key", "") if self.prev_trial.get("request_key") is not None else "", multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        self.notes = TextInput(text="", hint_text="Notes (optional)", multiline=True, size_hint_y=None, height=dp(80))

                # Fields inside site_box
        self.site_series = TextInput(
            hint_text="e.g., CWHvm1/01 (optional)",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
        )

        self.smr = Spinner(
            text="(Select)",
            values=SMR_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )
        self.snr = Spinner(
            text="(Select)",
            values=SNR_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )
        self.site_factors = Spinner(
            text="(Select)",
            values=SITE_FACTORS_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )
        self.site_prep = Spinner(
            text="(Select)",
            values=SITE_PREP_OPTIONS,
            size_hint_y=None,
            height=dp(44),
        )

        add_field("Species *", self.species)
        self.species.bind(text=self.validate_form)
        self.species.bind(text=self.update_replicate_no)
        self.species.bind(text=self.update_spp_fields)
        add_field("Replicate number *", self.replicate_no)
        add_field("Number of Seedlings *", self.seedlings)
        self.seedlings.bind(text=self.validate_form)
        add_field("Seedlot *", self.seedlot)
        self.seedlot.bind(text=self.validate_form)
        add_field("Spacing *", self.spacing)
        self.spacing.bind(text=self.validate_form)
        add_field("Request key *", self.request_key)
        self.request_key.bind(text=self.validate_form)
        add_field("Site series", self.site_series)
        add_field("SMR", self.smr)
        add_field("SNR", self.snr)
        add_field("Site/Soil Factors", self.site_factors)
        add_field("Site Prep", self.site_prep)
        add_field("Notes", self.notes)

        form.add_widget(Label(text="Add photo(s) *", size_hint_y=None, height=dp(20), halign="left", valign="middle"))
        form.add_widget(self.photo_preview)

        # Give some scroll padding so last fields aren't under button row/keyboard
        form.add_widget(Widget(size_hint_y=None, height=dp(140)))

        scroll.add_widget(form)
        root.add_widget(scroll)
        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))

        self.btn_attach = Button(text="Attach photo")
        self.btn_cancel = Button(text="Cancel")
        self.btn_submit = Button(text="Submit",
                            disabled=True,
                            background_normal="",
                            background_color=(0.6, 0.6, 0.6, 1))

        self.btn_attach.bind(on_release=lambda *_: self.open_attach_photo_menu())
        self.btn_cancel.bind(on_release=lambda *_: self.dismiss())
        self.btn_submit.bind(on_release=self.submit_form)

        btn_row.add_widget(self.btn_attach)
        btn_row.add_widget(self.btn_cancel)
        btn_row.add_widget(self.btn_submit)

        root.add_widget(btn_row)

        self.content = root

    def destroy(self, *_):
        self.seedlings.destroy()
        self.replicate_no.destroy()
        self.spacing.destroy()

    def _hide_fields(self, spinner, is_open):
        if is_open:
            self.seedlings.hide_native()
            self.replicate_no.hide_native()
            self.spacing.hide_native()
        else:
            self.seedlings.show_native()
            self.replicate_no.show_native()
            self.spacing.show_native()

    def update_spp_fields(self, *_):
        spp_code = self.species.text.split(" - ")[0] if self.species.text != "Species" else None
        if spp_code:
            seedlots = SEEDLOTS.get(spp_code, None)
            requests = REQUESTS.get(spp_code, None)
            self.seedlot.text = seedlots[0] if seedlots else self.prev_trial.get("seedlot", "") if self.prev_trial.get("seedlot") is not None else ""
            self.request_key.text = requests[0] if requests else self.prev_trial.get("request_key", "") if self.prev_trial.get("request_key") is not None else ""
        else:
            self.seedlot.text = ""
            self.request_key.text = ""

    def update_replicate_no(self, *_):
        species_code = self.species.text.split(" - ")[0] if self.species.text != "Species" else None
        if species_code and self.block_name:
            self.replicate_no.text = get_replicate_no(self.block_name, species_code)
        else:
            self.replicate_no.text = "1"

    def validate_form(self, *_):
        required_fields = [
            self.species,
            self.seedlings,
            self.seedlot,
            self.spacing,
            self.request_key
        ]
        valid = all(field.text.strip() for field in required_fields)
        is_photo = len(self.photo_paths) > 0
        valid = valid and is_photo  # require at least one photo
        self.btn_submit.disabled = not valid
        if valid:
            # enabled style
            self.btn_submit.background_color = (0.2, 0.6, 0.2, 1)
        else:
            # greyed out
            self.btn_submit.background_color = (0.6, 0.6, 0.6, 1)
        
    def open_attach_photo_menu(self):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        btns = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))

        b_camera = Button(text="Camera")
        b_library = Button(text="Photo library")
        btns.add_widget(b_camera)
        btns.add_widget(b_library)
        box.add_widget(btns)

        p = Popup(title="Attach photo", content=box, size_hint=(0.9, None), height=dp(180), auto_dismiss=True)

        def pick(source):
            p.dismiss()
            self.start_photo_pick(source)

        b_camera.bind(on_release=lambda *_: pick("camera"))
        b_library.bind(on_release=lambda *_: pick("library"))

        p.open()

    def start_photo_pick(self, source: str):
        PHOTO_PICKER.pick(source, on_done=self.on_photo_picked)

    def on_photo_picked(self, path: str | None):
        if not path:
            return  # cancelled

        self.photo_paths.append(path)
        self.validate_form()  # re-validate form now that we have a photo``

        # Show last selected image (full-res for now)
        self.photo_preview.source = path
        self.photo_preview.reload()


    def submit_form(self, *_):
        data = {
            "uuid": str(uuid.uuid4()),
            "species": self.species.text.split(" - ")[0],  # extract code from "CODE - Name"
            "replicate_no": int(self.replicate_no.text) if self.replicate_no.text.strip() else 1,
            "seedlings": self.seedlings.text.strip(),
            "seedlot": self.seedlot.text.strip(),
            "spacing": self.spacing.text.strip(),
            "lat": self.lat,
            "lon": self.lon,
            "elev": self.elev,
            "block_name": self.block_name,
            "owner": self.owner,
            "request_key": self.request_key.text.strip(),
            "site_series": self.site_series.text.strip(),
            "smr": "" if self.smr.text == "(select)" else self.smr.text,
            "snr": "" if self.snr.text == "(select)" else self.snr.text,
            "site_factors": "" if self.site_factors.text == "(select)" else self.site_factors.text,
            "site_prep": "" if self.site_prep.text == "(select)" else self.site_prep.text,
            "notes": self.notes.text.strip(),
            "photo_paths": list(self.photo_paths)
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
        self.species_in = Spinner(text=f"{trial_row.get('species', '')} - {SPECIES.get(trial_row.get('species', ''), '')}", values=[f"{k} - {v}" for k, v in SPECIES.items()], size_hint_y=None, height=dp(44))
        self.seedlings_in = TextInput(text=str(trial_row.get("seedlings", "") or ""), multiline=False, input_filter="int",
                                      size_hint_y=None, height=dp(44))
        self.seedlot_in = TextInput(text=trial_row.get("seedlot", "") or "", multiline=False, size_hint_y=None, height=dp(44))
        self.spacing_in = TextInput(text=str(trial_row.get("spacing", "") or ""), multiline=False, size_hint_y=None, height=dp(44))
        self.site_series = TextInput(text=trial_row.get("site_series", "") or "", multiline=False, size_hint_y=None, height=dp(44))
        self.request_key = TextInput(text=trial_row.get("request_key", "") if trial_row.get("request_key") is not None else "", multiline=False, size_hint_y=None, height=dp(44))
        self.smr = Spinner(text=trial_row.get("smr", "(Select)") or "(Select)", values=SMR_OPTIONS, size_hint_y=None, height=dp(44))
        self.snr = Spinner(text=trial_row.get("snr", "(Select)") or "(Select)", values=SNR_OPTIONS, size_hint_y=None, height=dp(44))
        self.site_factors = Spinner(text=trial_row.get("site_factors", "(Select)") or "(Select)", values=SITE_FACTORS_OPTIONS, size_hint_y=None, height=dp(44))
        self.site_prep = Spinner(text=trial_row.get("site_prep", "(Select)") or "(Select)", values=SITE_PREP_OPTIONS, size_hint_y=None, height=dp(44))
        self.notes = TextInput(text=trial_row.get("notes", "") or "", hint_text="Notes (optional)", multiline=True, size_hint_y=None, height=dp(80))
        def add_field(label, widget):
            form.add_widget(Label(text=label, size_hint_y=None, height=dp(18), halign="left", valign="middle"))
            form.add_widget(widget)

        add_field("Species", self.species_in)
        add_field("Seedlings", self.seedlings_in)
        add_field("Seedlot", self.seedlot_in)
        add_field("Spacing", self.spacing_in)
        add_field("Site series", self.site_series)
        add_field("Request Key", self.request_key)
        add_field("SMR", self.smr)
        add_field("SNR", self.snr)
        add_field("Site Factors", self.site_factors)
        add_field("Site Prep", self.site_prep)
        add_field("Notes", self.notes)
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
            "species": self.species_in.text.split(" - ")[0] if self.species_in.text != "Species" else "",
            "seedlings": int(self.seedlings_in.text) if self.seedlings_in.text.strip() else None,
            "seedlot": self.seedlot_in.text.strip(),
            "spacing": self.spacing_in.text.strip(),
            "request_key": self.request_key.text.strip(),
            "site_series": self.site_series.text.strip(),
            "smr": "" if self.smr.text == "(select)" else self.smr.text,
            "snr": "" if self.snr.text == "(select)" else self.snr.text,
            "site_factors": "" if self.site_factors.text == "(select)" else self.site_factors.text,
            "site_prep": "" if self.site_prep.text == "(select)" else self.site_prep.text,
            "notes": self.notes.text.strip(),
        }
        self.on_save(data)
        self.dismiss()

class EditLocationPopup(Popup):
    def __init__(self, trial_row: dict, on_save, get_current_gps, **kwargs):
        #kwargs.setdefault("auto_dismiss", False)
        super().__init__(**kwargs)
        self.title = "Edit Trial Location"
        self.size_hint = (0.92, 0.85)

        self.trial = trial_row
        self.on_save = on_save
        self.get_current_gps = get_current_gps

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        self.lat_input = TextInput(text=str(trial_row["lat"]), hint_text="Latitude",
                                   multiline=False, size_hint_y=None, height=dp(44))
        self.lon_input = TextInput(text=str(trial_row["lon"]), hint_text="Longitude",
                                   multiline=False, size_hint_y=None, height=dp(44))
        gps_butt = RoundedButton(text = "Use Current Location", size_hint=(None, None), size = (dp(200), dp(44)))
        gps_butt.bind(on_release = self.update_location)
        root.add_widget(self.lat_input)
        root.add_widget(self.lon_input)
        root.add_widget(gps_butt)
        root.add_widget(Widget())

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

    def update_location(self, *_):
        gps_fix = self.get_current_gps()
        self.lat_input.text = str(gps_fix["lat"])
        self.lon_input.text = str(gps_fix["lon"])

    def _save(self, *_):
        data = {
            "lat": self.lat_input.text.strip(),
            "lon": self.lon_input.text.strip(),
        }
        self.on_save(data)
        self.dismiss()
 

class TrialFilterPopup(Popup):
    def __init__(self, year_range, owners, callback, **kwargs):
        super().__init__(**kwargs)

        self.min_year, self.max_year = year_range
        self.owners = owners
        self.callback = callback
        

        years = [str(y) for y in range(self.min_year, self.max_year + 1)]

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(15),
        )

        # ----------------------------
        # Year filter
        # ----------------------------

        year_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(10),
        )

        self.year_cb = CheckBox(
            active=True,
            size_hint=(None, None),
            size=(dp(36), dp(36))
        )
        year_row.add_widget(self.year_cb)
        year_row.add_widget(Label(
            text="Show all planting years",
            halign="left",
            valign="middle"
        ))

        root.add_widget(year_row)

        year_panel = GridLayout(
            cols=2,
            spacing=dp(10),
            size_hint_y=None,
            height=dp(100),
        )

        year_panel.add_widget(Label(text="From"))

        self.from_spinner = Spinner(
            text=str(self.min_year),
            values=years,
            height=dp(40)
        )
        year_panel.add_widget(self.from_spinner)

        year_panel.add_widget(Label(text="To"))

        self.to_spinner = Spinner(
            text=str(self.max_year),
            values=years,
            height=dp(40)
        )
        year_panel.add_widget(self.to_spinner)

        year_panel.disabled = True
        year_panel.opacity = 0

        root.add_widget(year_panel)

        # ----------------------------
        # Owner filter
        # ----------------------------

        owner_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            spacing=dp(10),
        )

        self.owner_cb = CheckBox(
            active=True,
            size_hint=(None, None),
            size=(dp(36), dp(36))
        )
        owner_row.add_widget(self.owner_cb)
        owner_row.add_widget(Label(
            text="Show all trial owners",
            halign="left",
            valign="middle"
        ))

        root.add_widget(owner_row)

        self.owner_spinner = Spinner(
            text=owners[0] if owners else "",
            values=owners,
            size_hint_y=None,
            height=dp(40)
        )

        self.owner_spinner.disabled = True
        self.owner_spinner.opacity = 0

        root.add_widget(self.owner_spinner)

        # ----------------------------
        # Enable / disable callbacks
        # ----------------------------

        def update_year_panel(*args):
            enabled = not self.year_cb.active
            year_panel.disabled = not enabled
            year_panel.opacity = 1 if enabled else 0

        self.year_cb.bind(active=update_year_panel)

        def update_owner_spinner(*args):
            enabled = not self.owner_cb.active
            self.owner_spinner.disabled = not enabled
            self.owner_spinner.opacity = 1 if enabled else 0

        self.owner_cb.bind(active=update_owner_spinner)

        # ----------------------------
        # Buttons
        # ----------------------------

        button_row = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))

        apply_btn = Button(text="Apply", size_hint_y=None, height=dp(44))
        apply_btn.bind(on_release=self.apply_trial_filters)

        cancel_btn = Button(text="Cancel", size_hint_y=None, height=dp(44))
        cancel_btn.bind(on_release=lambda x: self.dismiss())

        button_row.add_widget(cancel_btn)
        button_row.add_widget(apply_btn)

        root.add_widget(button_row)

        self.title = "Filter Trials"
        self.content = root
        self.size_hint = (0.92, 0.8)
        self.auto_dismiss = False
    
    def apply_trial_filters(self, *_):
        filters = {
            "all_years": self.year_cb.active,
            "year_from": int(self.from_spinner.text),
            "year_to": int(self.to_spinner.text),
            "all_owners": self.owner_cb.active,
            "owner": self.owner_spinner.text
        }
        self.callback(filters)
        self.dismiss()

class SaveTrackPopup(Popup):

    def __init__(self, track, on_save, on_cancel, on_delete, **kwargs):
        super().__init__(**kwargs)

        self.track = track
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.on_delete = on_delete

        self.title = "Save Track"
        self.size_hint = (0.9, 0.85)
        self.auto_dismiss = False

        root = BoxLayout(
            orientation="vertical",
            padding=dp(20),
            spacing=dp(16)
        )

        # ----------------------------------------------------------
        # Track summary
        # ----------------------------------------------------------

        summary = GridLayout(
            cols=2,
            spacing=dp(8),
            row_force_default=True,
            row_default_height=dp(32),
            size_hint_y=None
        )
        summary.bind(minimum_height=summary.setter("height"))

        summary.add_widget(Label(text="Distance:", halign="left"))
        summary.add_widget(Label(
            text=f"{track['distance']:.0f} m",
            halign="left"))

        summary.add_widget(Label(text="Points:", halign="left"))
        summary.add_widget(Label(
            text=str(track["point_count"]),
            halign="left"))

        root.add_widget(summary)

        # ----------------------------------------------------------
        # Name input
        # ----------------------------------------------------------

        root.add_widget(Label(
            text="Track name:",
            size_hint_y=None,
            height=dp(30)
        ))

        self.name_input = TextInput(
            multiline=False,
            write_tab=False,
            size_hint_y=None,
            height=dp(44)
        )

        root.add_widget(self.name_input)
        root.add_widget(Widget())
        # ----------------------------------------------------------
        # Buttons
        # ----------------------------------------------------------

        buttons = BoxLayout(
            spacing=dp(12),
            size_hint_y=None,
            height=dp(44)
        )

        cancel_btn = Button(text="Cancel")
        delete_btn = Button(text = "Delete")
        save_btn = Button(text="Save")

        cancel_btn.bind(on_release=self.cancel)
        save_btn.bind(on_release=self.save)
        delete_btn.bind(on_release=self.delete)

        buttons.add_widget(cancel_btn)
        buttons.add_widget(save_btn)
        buttons.add_widget(delete_btn)

        root.add_widget(buttons)

        self.content = root

    # --------------------------------------------------------------

    def delete(self, *args):
        self.dismiss()
        self.on_delete()

    def save(self, *args):

        name = self.name_input.text.strip()

        if not name:
            name = "Untitled Track"

        self.dismiss()

        if self.on_save:
            self.on_save(self.track, name)

    # --------------------------------------------------------------

    def cancel(self, *args):

        self.dismiss()

        if self.on_cancel:
            self.on_cancel(self.track)

    # --------------------------------------------------------------

    @staticmethod
    def format_duration(seconds):

        seconds = int(round(seconds))

        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)

        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        else:
            return f"{m:d}:{s:02d}"
        

class TrackManagerPopup(Popup):

    def __init__(self,
                 tracks,
                 on_draw=None,
                 on_export=None,
                 on_delete=None,
                 **kwargs):

        super().__init__(**kwargs)

        self.tracks = tracks
        self.on_draw = on_draw
        self.on_export = on_export
        self.on_delete = on_delete

        self.title = "Saved Tracks"
        self.size_hint = (0.9, 0.9)
        self.auto_dismiss = True

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(20)
        )

        scroll = ScrollView()

        self.grid = GridLayout(
            cols=1,
            spacing=dp(8),
            size_hint_y=None
        )
        self.grid.bind(minimum_height=self.grid.setter("height"))

        scroll.add_widget(self.grid)
        root.add_widget(scroll)

        close = Button(
            text="Close",
            size_hint_y=None,
            height=dp(44)
        )
        close.bind(on_release=lambda *_: self.dismiss())

        root.add_widget(close)

        self.content = root

        self.populate()

    def populate(self):
        self.grid.clear_widgets()
        if not self.tracks:
            self.grid.add_widget(
                Label(
                    text="No saved tracks.",
                    size_hint_y=None,
                    height=dp(60)
                )
            )
            return
        for track in sorted(
                self.tracks,
                key=lambda t: t["created"],
                reverse=True):
            btn = Button(
                text=self.format_track(track),
                markup=True,
                halign="left",
                valign="middle",
                text_size=(None, None),
                size_hint_y=None,
                height=dp(72)
            )
            btn.track = track
            btn.bind(on_release=self.track_selected)

            self.grid.add_widget(btn)
    
    def format_track(self, track):
        created = track["created"]
        if isinstance(created, str):
            created = datetime.fromisoformat(created)

        if track["distance"] >= 1000:
            distance = f"{track['distance']/1000:.2f} km"
        else:
            distance = f"{track['distance']:.0f} m"

        return (
            f"[b]{track['name']}[/b]\n"
            f"{created:%d %b %Y %H:%M}    "
            f"{distance}    "
        )
        
    def track_selected(self, button):

        TrackActionPopup(
            button.track,
            on_draw=self.on_draw,
            on_export=self.on_export,
            on_delete=self.on_delete
        ).open()

class TrackActionPopup(Popup):

    def __init__(self,
                 track,
                 on_draw=None,
                 on_export=None,
                 on_delete=None,
                 **kwargs):

        super().__init__(**kwargs)

        self.track = track

        self.title = track["name"]
        self.size_hint = (0.8, 0.6)

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(20)
        )

        for text, callback in [
            ("Draw", on_draw),
            ("Export GPX", on_export),
            ("Delete", on_delete),
            ("Cancel", None)
        ]:

            btn = Button(
                text=text,
                size_hint_y=None,
                height=dp(44)
            )

            if callback is None:
                btn.bind(on_release=lambda *_: self.dismiss())
            else:
                btn.bind(
                    on_release=lambda _, cb=callback:
                    self.run_callback(cb)
                )

            root.add_widget(btn)

        self.content = root

    def run_callback(self, callback):
        self.dismiss()
        if callback:
            callback(self.track)



class AssessmentPopup(Popup):

    def __init__(self,
                 marker,
                 existing=None,
                 damage_agents=None,
                 save_callback=None,
                 **kwargs):

        super().__init__(**kwargs)

        self.marker = marker
        self.save_callback = save_callback
        self.title = ""
        self.title_size = 0
        self.separator_height = 0

        self.assessment_uuids = get_trial_assessment_uuids(
            self.marker['uuid']
        )

        self.grid_corner_direction = get_grid_direction(
            self.marker['uuid']
        )

        self.page_index = None
        self.current_assessment_uuid = None

        # Holds unsaved new-assessment work
        self.new_assessment_data = None

        self.size_hint = (0.95, 0.95)
        self.auto_dismiss = False
        self.bind(on_dismiss=self._on_dismiss)

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(10)
        )
        self.navigator = AssessmentNavigator(
            previous_callback=self.previous_assessment,
            next_callback=self.next_assessment
        )

        root.add_widget(self.navigator)

        # ------------------------------------------------------
        # Growth grid
        # ------------------------------------------------------
        self.grid_area = FloatLayout(
            size_hint=(1, None),
            height=dp(330)
        )

        self.grid = GrowthGrid(
            existing=existing,
            callback=self.tree_selected,
            size_hint=(1, None),
            height=dp(320),
            pos_hint={
                "center_x": 0.5,
                "top": 1
            }
        )
        self.grid_area.add_widget(self.grid)
        self.direction_spinner = Spinner(
            text="Direction",
            values=[
                "N", "NE", "E", "SE",
                "S", "SW", "W", "NW"
            ],
            size_hint=(None, None),
            size=(dp(70), dp(36))
        )

        if self.grid_corner_direction:
            self.direction_spinner.text = self.grid_corner_direction
            self.direction_spinner.disabled = True

        self.grid.bind(
            pos=self.update_direction_position,
            size=self.update_direction_position
        )
        self.grid_area.add_widget(
            self.direction_spinner
        )

        self.copy_previous_btn = RoundedButton(
            text="Copy Previous",
            size_hint=(None, None),
            size=(dp(130), dp(36))
        )

        self.grid_area.add_widget(
            self.copy_previous_btn
        )

        self.copy_previous_btn.bind(
            on_release=self.copy_previous_assessment
        )
        root.add_widget(self.grid_area)

        # ------------------------------------------------------
        # Assessment panel
        # ------------------------------------------------------

        self.panel = AssessmentPanel(
            damage_agents=damage_agents,
            previous_callback=self.previous_tree,
            next_callback=self.next_tree,
            change_callback=self.assessment_changed
        )

        self.panel_scroll = ScrollView(
            do_scroll_x=False,
            size_hint=(1, 1),
        )

        self.panel_scroll.add_widget(self.panel)

        self.panel_container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=0,
        )

        self.panel_container.add_widget(self.panel_scroll)

        root.add_widget(self.panel_container)

        # ------------------------------------------------------
        # Buttons
        # ------------------------------------------------------

        self.button_row = BoxLayout(
            spacing=dp(10),
            size_hint_y=None,
            height=dp(44)
        )

        self.cancel_btn = Button(text="Cancel")
        self.cancel_btn.bind(on_release=lambda *_: self.dismiss())

        self.save_btn = Button(
            text="Save Assessment",
            background_normal="",
            background_color=(0.2, 0.6, 0.2, 1)
        )

        self.save_btn.bind(on_release=self.save)

        self.close_btn = Button(text="Close")
        self.close_btn.bind(on_release=lambda *_: self.dismiss())

        root.add_widget(self.button_row)

        self.content = root

        ## choose initial page
        if self.assessment_uuids:
            # Most recent saved assessment
            initial_page = len(self.assessment_uuids) - 1
        else:
            # No assessments: New Assessment page
            initial_page = 0

        self.load_page(initial_page)

    def load_page(self, index):

        n_saved = len(self.assessment_uuids)


        if index < 0 or index > n_saved:
            return

        # --------------------------------------------------
        # Preserve unsaved new-assessment work
        # --------------------------------------------------

        if self.page_index == n_saved:
            self.new_assessment_data = copy.deepcopy(
                self.grid.data
            )

        # --------------------------------------------------
        # Reset UI
        # --------------------------------------------------
        self.hide_panel()

        self.page_index = index

        # --------------------------------------------------
        # Historical assessment
        # --------------------------------------------------

        if index < n_saved:

            assessment_uuid = self.assessment_uuids[index]
            self.copy_previous_btn.disabled = True
            assessment = load_assessment(
                assessment_uuid
            )
            self.navigator.load_page(
                index=index,
                n_saved=n_saved,
                assessment_date=assessment["assessment_date"],
                assessor=assessment["username"]
            )

            self.current_assessment_uuid = assessment_uuid

            self.grid.load_data(
                assessment["trees"]
            )
            self.panel.set_read_only(True)
            self.update_buttons(read_only=True)


        # --------------------------------------------------
        # New assessment
        # --------------------------------------------------

        else:

            self.current_assessment_uuid = None
            prof = load_current_user_profile()
            self.copy_previous_btn.disabled = (n_saved == 0)

            if self.new_assessment_data is None:
                self.new_assessment_data = (
                    self.make_new_assessment_data()
                )

            self.navigator.load_page(
                index=index,
                n_saved=n_saved,
                assessor=prof["username"]
            )

            self.grid.load_data(
                self.new_assessment_data
            )
            self.panel.set_read_only(False)
            self.update_buttons(read_only=False)

    def update_direction_position(self, *_):
        self.direction_spinner.pos = (
            self.grid.x,
            self.grid.y - dp(40)
        )
        self.copy_previous_btn.pos = (
            self.grid.right - self.copy_previous_btn.width,
            self.grid.y - dp(40)
        )
        self.grid_area.height = (
            self.grid.height + dp(40)
        )

    def update_buttons(self, read_only):
        self.button_row.clear_widgets()
        if read_only:
            # Historical assessment
            self.button_row.add_widget(
                self.close_btn
            )

        else:
            # New assessment
            self.button_row.add_widget(
                self.cancel_btn
            )
            self.button_row.add_widget(
                self.save_btn
            )

    def copy_previous_assessment(self, *_):
        if not self.assessment_uuids:
            return

        latest_uuid = self.assessment_uuids[-1]

        previous = load_assessment(
            latest_uuid
        )

        if previous is None:
            return

        self.new_assessment_data = copy.deepcopy(
            previous["trees"]
        )

        self.grid.load_data(
            self.new_assessment_data
        )

        #self.grid.clear_selection()
        #self.hide_panel(animate=False)

    def make_new_assessment_data(self):
        data = self.make_empty_growth_grid()

        if not self.assessment_uuids:
            return data

        latest_uuid = self.assessment_uuids[-1]

        previous = load_assessment(
            latest_uuid
        )["trees"]

        for row in range(5):
            for col in range(5):

                data[row][col]["rating"] = (
                    previous[row][col]["rating"]
                )

        return data

    def make_empty_growth_grid(self, rows=5, cols=5):
        """
        Create a fresh growth-assessment data structure.
        """

        return [
            [
                {
                    "rating": "-",
                    "damage": [],
                    "height": None,
                    "diameter": None
                }
                for col in range(cols)
            ]
            for row in range(rows)
        ]

    def show_panel(self):
        if self.panel_container.height > 0:
            return

        self.panel.show_native()
        button_height = dp(44)
        spacing = dp(30)      # padding + spacing

        target_grid = (
            self.height
            - button_height
            - spacing
            - dp(500)
        )

        target_grid = max(target_grid, dp(180))
        
        Animation(
            height=dp(380),
            d=0.25,
            t="out_quad"
        ).start(self.panel_container)

        Animation(
            height=target_grid,
            width=target_grid,
            d=0.25,
            t="out_quad"
        ).start(self.grid)

    # ==========================================================
    # Grid callbacks
    # ==========================================================

    def tree_selected(self, *_):
        self.show_panel()
        self.grid.load_selected_into(self.panel)

    # ==========================================================
    # Panel callbacks
    # ==========================================================

    def assessment_changed(self):
        self.grid.update_selected()

    def previous_tree(self):
        self.grid.previous_cell()

    def next_tree(self):
        self.grid.next_cell()

    # ==========================================================
    # Save
    # ==========================================================

    def save(self, *_):
        print("AssessmentPopup grid data: ", self.grid.data)
        direction = self.direction_spinner.text
        if self.save_callback:
            self.save_callback(
                self.marker,
                self.grid.data,
                direction
            )

        self.dismiss()

    def _on_dismiss(self, *_):
        self.panel.destroy()

    # ==========================================================
    # Gesture handling
    # ==========================================================
    def on_touch_down(self, touch):
        if self.grid.collide_point(*touch.pos):
            touch.ud["assessment_swipe_x"] = touch.x
            touch.ud["assessment_swipe_y"] = touch.y

        return super().on_touch_down(touch)
    
    def on_touch_up(self, touch):
        if "assessment_swipe_x" in touch.ud:

            dx = touch.x - touch.ud["assessment_swipe_x"]
            dy = touch.y - touch.ud["assessment_swipe_y"]

            # Horizontal gesture rather than vertical scroll
            if abs(dx) > dp(60) and abs(dx) > abs(dy) * 1.5:

                if dx < 0:
                    self.next_assessment()
                else:
                    self.previous_assessment()

                return True

        return super().on_touch_up(touch)
    
    def next_assessment(self):
        max_index = len(self.assessment_uuids)
        if self.page_index < max_index:
            self.load_page(
                self.page_index + 1
            )

    def previous_assessment(self):
        if self.page_index > 0:
            self.load_page(
                self.page_index - 1
            )

    def hide_panel(self, animate=True):

        # # Dismiss native numeric fields / keyboard
        # self.panel.height_input.bridge.resignFirstResponderField()
        # self.panel.diameter_input.bridge.resignFirstResponderField()

        # Restore grid size
        target_grid = dp(320)
        self.panel.hide_native()
        if animate:

            Animation(
                height=0,
                d=0.20,
                t="out_quad"
            ).start(self.panel_container)

            Animation(
                height=target_grid,
                width=target_grid,
                d=0.20,
                t="out_quad"
            ).start(self.grid)

        else:

            Animation.cancel_all(self.panel_container)
            Animation.cancel_all(self.grid)

            self.panel_container.height = 0
            self.grid.height = target_grid
            self.grid.width = target_grid


class TrialAssessmentPopup(Popup):

    RATINGS = {"Excellent": "E",
               "Good": "G",
               "Fair": "F",
               "Poor": "P",
               "Dead": "D",
               "Missing": "M",
               }

    def __init__(
        self,
        data,
        existing=None,
        save_callback=None,
        **kwargs
    ):

        super().__init__(**kwargs)
        self.data = data
        self.save_callback = save_callback
        self.direction = None
        self.tree_data = None

        self.title = "Trial Assessment"
        self.size_hint = (0.9, 0.75)
        self.auto_dismiss = False

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(12)
        )

        # --------------------------------------------------
        # Overall rating
        # --------------------------------------------------

        root.add_widget(
            Label(
                text="Overall Trial Rating",
                size_hint_y=None,
                height=dp(28)
            )
        )
        self.rating_spinner = Spinner(
            text="General Vigour",
            values=self.RATINGS.keys(),
            size_hint_y=None,
            height=dp(44)
        )
        root.add_widget(
            self.rating_spinner
        )

        # --------------------------------------------------
        # Notes
        # --------------------------------------------------

        root.add_widget(
            Label(
                text="Notes",
                size_hint_y=None,
                height=dp(28)
            )
        )

        self.notes_input = TextInput(
            multiline=True,
            hint_text="Optional notes..."
        )

        root.add_widget(
            self.notes_input
        )

        # --------------------------------------------------
        # Tree assessment
        # --------------------------------------------------

        self.tree_assessment_btn = RoundedButton(
            text="Open Tree Assessment",
            size_hint_y=None,
            height=dp(48)
        )

        self.tree_assessment_btn.bind(
            on_release=self.open_tree_assessment
        )

        root.add_widget(
            self.tree_assessment_btn
        )

        # --------------------------------------------------
        # Buttons
        # --------------------------------------------------

        button_row = BoxLayout(
            spacing=dp(10),
            size_hint_y=None,
            height=dp(44)
        )

        cancel_btn = Button(
            text="Cancel"
        )

        cancel_btn.bind(
            on_release=lambda *_:
                self.dismiss()
        )

        save_btn = Button(
            text="Save Assessment",
            background_normal="",
            background_color=(0.2, 0.6, 0.2, 1)
        )

        save_btn.bind(
            on_release=self.save_trial
        )

        button_row.add_widget(
            cancel_btn
        )

        button_row.add_widget(
            save_btn
        )

        root.add_widget(
            button_row
        )

        self.content = root

        # --------------------------------------------------
        # Existing values
        # --------------------------------------------------

        if existing is not None:
            self.load(existing)


    def open_tree_assessment(self, *_):

        popup = AssessmentPopup(
            marker=self.data,
            existing=None,
            save_callback=self.save_from_tree_ass
        )
        popup.open()

    def save_from_tree_ass(self, marker, grid_data, direction):
        #print("TrialAssessmentPopup grid data: ", grid_data)
        self.tree_data = grid_data
        self.direction = direction
        self.save_all()

    def save_trial(self, *_):
        self.save_all()

    def save_all(self, *_):
        rating = self.rating_spinner.text
        notes = self.notes_input.text.strip()
        ass = {
            "trial_rating": None,
            "notes": None
        }
        if rating != "General Vigour":
            ass["trial_rating"] = rating
        if notes != "":
            ass["notes"] = notes


        if self.save_callback:
            self.save_callback(
                self.data,
                ass,
                self.tree_data,
                self.direction,
            )

        self.dismiss()
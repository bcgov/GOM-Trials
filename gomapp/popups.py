from db_trials import get_most_recent_trial, add_trial_owner, get_replicate_no, get_trial_owners
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
from kivy.app import App
from kivy.uix.image import Image
from photos import IOSPhotoPicker
from db_users import download_trial_owners
from gom_logger import logger


import uuid

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
        self.block_input = TextInput(text=prev_trial.get("block_name", "") or "", hint_text="Block name",
                                    multiline=False, size_hint_y=None, height=dp(44))
                                   
#        def ensure_visible(ti):
#            def _on_focus(_inst, focused):
#                if focused:
#                    Clock.schedule_once(lambda dt: scroll.scroll_to(ti, padding=dp(20)), 0)
#            ti.bind(focus=_on_focus)
#
#        ensure_visible(self.lat_input)
#        ensure_visible(self.lon_input)
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
        self.owner_spinner = Spinner(text=prev_trial.get("trial_owner", "Select trial owner") or "Select trial owner", values=[x for x in owner_list if x not in ["Other", prev_trial.get("trial_owner")]] + ["Other"], size_hint_y=None, height=dp(44))
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
            self.owner = contact_name
            self.owner_spinner.values = [contact_name] + self.owner_spinner.values[:-1]  # add new owner to spinner, before "Other"
            owner_popup.dismiss()

        self.owner_create_btn.bind(on_release=confirm_owner) 


        def on_spinner_select(spinner, text):
            if text == "Other":
                owner_popup.open()
            else:                
                self.owner = text
   
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
        self.replicate_no = TextInput(text = "1",hint_text="Replicate number", multiline=False, input_filter="int", size_hint_y=None, height=dp(44))
        self.seedlings = TextInput(hint_text="Number of Seedlings", input_filter="int",
                                   multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        self.seedlot = TextInput(text = self.prev_trial.get("seedlot", "") if self.prev_trial.get("seedlot") is not None else "", multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
        self.spacing = TextInput(hint_text="Spacing (e.g. 2.0)", multiline=False, text_validate_unfocus = False, size_hint_y=None, height=dp(44))
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

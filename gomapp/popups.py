from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.button import Button

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

# class DraggableButton(DragBehavior, Button):
#     pass

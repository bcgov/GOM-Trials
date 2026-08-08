from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock

from utils import SectionHeader
from config import damage_dict
from numeric_entry import NativeNumericField

class GrowthCell(Button):

    COLOURS = {
        "Mis": (0.8, 0.8, 0.8, 1), # light gray
        "D": (0,0,0, 1),   # black
        "P": (0.72, 0.28, 0.28, 1.0),   # red
        "F": (0.96, 0.78, 0.30, 1.0),   # orange
        "G": (0.42, 0.78, 0.42, 1.0),   # green
        "E": (0.16, 0.50, 0.20, 1.0),   # dark green
    }

    def __init__(self, data, row, col, callback=None, **kwargs):

        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))

        super().__init__(**kwargs)

        self.data = data
        self.row = row
        self.col = col
        self.callback = callback

        with self.canvas.before:

            self.bg_colour = Color(1, 1, 1, 1)

            self.bg = RoundedRectangle(
                radius=[dp(6)]
            )

        with self.canvas.after:
            self.sel_colour = Color(0.0, 0.35, 0.9, 0.0)

            self.sel_line = Line(
                rounded_rectangle=(0,0,0,0,dp(6)),
                width=dp(3.5)
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            on_release=self.on_pressed
        )

        self.update_cell()

    # --------------------------------------------------------

    def _update_canvas(self, *args):

        self.bg.pos = self.pos
        self.bg.size = self.size

        self.sel_line.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp(6)
        )

    # --------------------------------------------------------

    def on_pressed(self, *args):

        if self.callback:
            self.callback(self.row, self.col)

    # --------------------------------------------------------

    def update_cell(self):

        rating = self.data["rating"]
        damage_summary = ""
        value_summary = ""

        if len(self.data["damage"]) > 0:
            damage_summary =  "".join(
                                f"{damage_dict[d['agent']]}{d['severity']}"
                                for d in self.data["damage"]
                                )

        if self.data["height"] is not None:
            value_summary = f" {self.data['height']:.1f}"

        self.markup = True

        self.text = (
            f"[size={int(sp(16))}]{rating}[/size]\n"
            f"[size={int(sp(12))}]{damage_summary}[/size] "
            f"[size={int(sp(12))}]{value_summary}[/size]"
        )

        self.bg_colour.rgba = self.COLOURS.get(
            rating,
            (0.8, 0.8, 0.8, 1)
        )

    # --------------------------------------------------------

    def set_selected(self, selected):
        self.sel_colour.a = 1.0 if selected else 0.0

class GrowthGrid(GridLayout):
    def __init__(self, existing=None, callback=None, **kwargs):
        super().__init__(rows=5, cols=5, spacing=4, padding=4, **kwargs)
        self.callback = callback
        self.data = [
            [
                {
                    "rating": existing[r][c] if existing else "Mis",
                    "damage": list(),
                    "height": None,
                    "diameter": None
                }
                for c in range(5)
            ]
            for r in range(5)
        ]
        self.selected_row = 0
        self.selected_col = 0

        self.cells = []
        for r in range(5):
            row = []
            for c in range(5):

                cell = GrowthCell(
                    self.data[r][c],
                    row=r,
                    col=c,
                    callback=self.select,
                    size_hint=(1,1)
                )

                row.append(cell)
                self.add_widget(cell)

            self.cells.append(row)
        
    def select(self, row, col):
        print(f"Selected cell: ({row}, {col})")
        print(f"Previous selected cell: ({self.selected_row}, {self.selected_col})")
        self.cells[self.selected_row][self.selected_col].set_selected(False)

        self.selected_row = row
        self.selected_col = col

        # Highlight new cell
        self.cells[row][col].set_selected(True)

        # Notify whoever owns the panel
        if self.callback:
            self.callback(row, col)

    def get_selected(self):
        return self.data[self.selected_row][self.selected_col]
    
    def get_cell(self, row, col):
        return self.data[row][col]
    
    def get_selected_position(self):
        return self.selected_row, self.selected_col
    
    def update_selected(self):
        self.cells[self.selected_row][self.selected_col].update_cell()

    def update_cell(self, row, col):
        self.cells[row][col].update_cell()

    def next_cell(self):
        index = self.selected_row * 5 + self.selected_col
        if index < 24:
            index += 1

        self.select(index // 5, index % 5)

    def previous_cell(self):

        index = self.selected_row * 5 + self.selected_col

        if index > 0:
            index -= 1

        self.select(index // 5, index % 5)

    def load_selected_into(self, panel):
        row, col = self.get_selected_position()

        panel.load(
            self.get_selected(),
            row,
            col
        )


class AssessmentPanel(BoxLayout):

    RATINGS = ["Mis","D","P","F","G","E"]

    def __init__(self,
                 damage_agents=None,
                 previous_callback=None,
                 next_callback=None,
                 change_callback=None,
                 **kwargs):

        super().__init__(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            **kwargs
        )

        self.bind(minimum_height=self.setter("height"))

        self.tree = None

        self.previous_callback = previous_callback
        self.next_callback = next_callback
        self.change_callback = change_callback

        if damage_agents is None:
            damage_agents = damage_dict.keys()

        # -------------------------------------------------------
        # NAV
        # -------------------------------------------------------

        nav = BoxLayout(
            spacing=dp(10),
            size_hint_y=None,
            height=dp(44)
        )

        prev_btn = Button(text="<- Previous")
        prev_btn.bind(
            on_release=lambda *_:
            self.previous_callback()
            if self.previous_callback else None
        )

        next_btn = Button(text="Next ->")
        next_btn.bind(
            on_release=lambda *_:
            self.next_callback()
            if self.next_callback else None
        )

        nav.add_widget(prev_btn)
        nav.add_widget(next_btn)
        self.add_widget(nav)

        # =======================================================
        # Rating card
        # =======================================================

        rating_card = self.make_card("Qualitative Rating")

        rating_row = BoxLayout(
            spacing=dp(8),
            size_hint_y=None,
            height=dp(44)
        )

        self.rating_buttons = {}

        for rating in self.RATINGS:

            btn = ToggleButton(
                text=rating,
                group="rating",
                allow_no_selection=False
            )

            btn.bind(on_release=self.on_rating)

            self.rating_buttons[rating] = btn
            rating_row.add_widget(btn)

        rating_card.add_widget(rating_row)

        self.add_widget(rating_card)


        # =======================================================
        # Measurements card
        # =======================================================

        measure_card = self.make_card("Measurements")

        measure_grid = GridLayout(
            cols=2,
            spacing=dp(10),
            size_hint_y=None,
            rows=2,
            row_force_default=True,
            row_default_height=dp(42)
        )

        measure_grid.bind(
            minimum_height=measure_grid.setter("height")
        )

        measure_grid.add_widget(Label(text="Height (cm)"))
        measure_grid.add_widget(Label(text="DBH (cm)"))

        self.height_input = NativeNumericField(
            decimal=True,
            size_hint=(1, None),
            height=dp(42),
        )

        self.height_input.bind(focused=self.on_height)

        measure_grid.add_widget(self.height_input)

        self.diameter_input = NativeNumericField(
            decimal=True,
            size_hint=(1, None),
            height=dp(42),
        )

        self.diameter_input.bind(focused=self.on_diameter)

        measure_grid.add_widget(self.diameter_input)

        measure_card.add_widget(measure_grid)
        self.add_widget(measure_card)

        # =======================================================
        # Damage card
        # =======================================================

        damage_card = self.make_card("Damage Agents")

        self.damage_section = DamageSection(
            agents=damage_agents,
            change_callback=self.notify_change,
            size_hint_y=None
        )

        self.damage_section.bind(
            minimum_height=self.damage_section.setter("height")
        )

        damage_card.add_widget(self.damage_section)

        self.add_widget(damage_card)

        

    # ==========================================================
    # Loading
    # ==========================================================

    def load(self, tree, row, col):

        self.tree = tree

        # Rating

        for rating, btn in self.rating_buttons.items():
            btn.state = (
                "down"
                if rating == tree["rating"]
                else "normal"
            )

        # Damage

        self.damage_section.load(tree["damage"])

        # Height

        self.height_input.text = (
            ""
            if tree["height"] is None
            else str(tree["height"])
        )

        # Diameter

        self.diameter_input.text = (
            ""
            if tree["diameter"] is None
            else str(tree["diameter"])
        )

    # ==========================================================
    # Event handlers
    # ==========================================================

    def on_rating(self, button):

        if self.tree is None:
            return

        if button.state != "down":
            return

        self.tree["rating"] = button.text

        self.notify_change()

    def on_height(self, widget, focused):
        print(
            f"on_height fired: focused={focused}, "
            f"tree_is_none={self.tree is None}, "
        )

        if focused or self.tree is None:
            return

        text = widget.text.strip()
        print(f"Text input for height: '{text}'")

        if text == "":
            self.tree["height"] = None
        else:
            try:
                self.tree["height"] = float(text)
            except ValueError:
                widget.text = ""
                self.tree["height"] = None

        self.notify_change()

    def on_diameter(self, widget, focused):

        if focused or self.tree is None:
            return

        text = widget.text.strip()

        if text == "":
            self.tree["diameter"] = None
        else:
            try:
                self.tree["diameter"] = float(text)
            except ValueError:
                widget.text = ""
                self.tree["diameter"] = None

        self.notify_change()

    # ==========================================================
    # Notification
    # ==========================================================

    def notify_change(self):

        if self.change_callback:
            self.change_callback()

    def destroy(self):
        self.height_input.destroy()
        self.diameter_input.destroy()

    def make_card(self, title):

        card = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=dp(10),
            size_hint_y=None
        )

        card.bind(minimum_height=card.setter("height"))

        with card.canvas.before:
            Color(0.6, 0.6, 0.6, 1)
            card.bg = RoundedRectangle(radius=[dp(8)])

        def update_bg(*_):
            card.bg.pos = card.pos
            card.bg.size = card.size

        card.bind(pos=update_bg, size=update_bg)

        card.add_widget(
            SectionHeader(
                text=title,
                height=dp(32)
            )
        )

        return card



class DamageRow(BoxLayout):

    def __init__(self,
                 damage,
                 remove_callback=None,
                 change_callback=None,
                 **kwargs):

        super().__init__(
            orientation="horizontal",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(40),
            **kwargs
        )

        self.damage = damage
        self.remove_callback = remove_callback
        self.change_callback = change_callback

        self.add_widget(
            Label(
                text=damage["agent"],
                size_hint_x=0.55,
                halign="left",
                valign="middle"
            )
        )

        self.buttons = {}

        group = f"severity_{id(self)}"

        for severity in (1, 2, 3):

            btn = ToggleButton(
                text=str(severity),
                group=group,
                allow_no_selection=False,
                size_hint_x=None,
                width=dp(40)
            )

            if severity == damage["severity"]:
                btn.state = "down"

            btn.bind(on_release=self.set_severity)

            self.buttons[severity] = btn

            self.add_widget(btn)

        delete_btn = Button(
            text="DEL",
            size_hint_x=None,
            width=dp(40)
        )

        delete_btn.bind(on_release=self.remove)

        self.add_widget(delete_btn)

    def set_severity(self, button):

        if button.state != "down":
            return

        self.damage["severity"] = int(button.text)

        if self.change_callback:
            self.change_callback()

    def remove(self, *_):

        if self.remove_callback:
            self.remove_callback(self)


class DamageSection(BoxLayout):

    def __init__(self,
                 agents,
                 change_callback=None,
                 **kwargs):

        super().__init__(
            orientation="vertical",
            spacing=dp(5),
            **kwargs
        )

        self.change_callback = change_callback

        self.damage = []

        self.rows = []

        self.spinner = Spinner(
            text="Add damage agent...",
            values=agents,
            size_hint_y=None,
            height=dp(44)
        )

        self.spinner.bind(text=self.add_damage)

        self.add_widget(self.spinner)

    def load(self, damage):

        self.damage = damage

        for row in self.rows:
            self.remove_widget(row)

        self.rows.clear()

        for d in self.damage:
            self._add_row(d)

    def add_damage(self, spinner, value):

        if value == "Add damage agent...":
            return

        damage = {
            "agent": value,
            "severity": 2
        }

        self.damage.append(damage)

        self._add_row(damage)

        self.spinner.text = "Add damage agent..."

        if self.change_callback:
            self.change_callback()

    def _add_row(self, damage):

        row = DamageRow(
            damage,
            remove_callback=self.remove_row,
            change_callback=self.change_callback
        )

        self.rows.append(row)

        self.add_widget(row, index = 1)

    def remove_row(self, row):

        self.damage.remove(row.damage)

        self.rows.remove(row)

        self.remove_widget(row)

        if self.change_callback:
            self.change_callback()
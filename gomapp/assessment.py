from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button

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

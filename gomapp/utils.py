from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.button import Button

class SectionHeader(Label):

    def __init__(
        self,
        text,
        bg_color=(0.18, 0.32, 0.18, 0.8),   # Default: semi-transparent forest green
        text_color=(1, 1, 1, 1),
        radius=6,
        **kwargs
    ):

        super().__init__(**kwargs)

        self.text = f"[b]{text}[/b]"
        self.markup = True

        self.color = text_color

        self.size_hint_y = None
        self.height = dp(32)

        self.padding = (dp(10), 0)

        self.halign = "left"
        self.valign = "middle"

        self.bind(size=self._update_text)
        self.bind(pos=self._update_rect,
                  size=self._update_rect)

        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(
                radius=[dp(radius)]
            )

    def _update_text(self, *args):
        self.text_size = self.size

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class RoundedButton(Button):

    def __init__(
        self,
        bg_color=(0.18, 0.32, 0.18, 0.85),
        radius=10,
        **kwargs
    ):

        # Remove the default button background
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))

        super().__init__(**kwargs)

        with self.canvas.before:
            self.bg = Color(*bg_color)
            self.rect = RoundedRectangle(radius=[dp(radius)])

        self.bind(pos=self._update_rect,
                  size=self._update_rect)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
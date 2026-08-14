from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty
from kivy.clock import Clock
import uuid

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


class DragHandle(Widget):

    def __init__(self,
                 start_callback=None,
                 drag_callback=None,
                 end_callback=None,
                 **kwargs):

        super().__init__(
            size_hint_y=None,
            height=dp(24),
            **kwargs
        )

        self.start_callback = start_callback
        self.drag_callback = drag_callback
        self.end_callback = end_callback

        self._start_y = None

        with self.canvas:

            # Transparent background so the whole handle area
            # is easy to grab.
            Color(0, 0, 0, 0)
            self.bg = RoundedRectangle()

            # The visible "grab bar"
            self.bar_colour = Color(0.65, 0.65, 0.65, 1)

            self.bar = RoundedRectangle(
                radius=[dp(3)]
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas
        )

    # ---------------------------------------------------------

    def _update_canvas(self, *_):

        self.bg.pos = self.pos
        self.bg.size = self.size

        w = dp(48)
        h = dp(6)

        self.bar.pos = (
            self.center_x - w / 2,
            self.center_y - h / 2
        )

        self.bar.size = (w, h)

    # ---------------------------------------------------------

    def on_touch_down(self, touch):

        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        self._start_y = touch.y

        touch.grab(self)

        if self.start_callback:
            self.start_callback()

        return True

    # ---------------------------------------------------------

    def on_touch_move(self, touch):

        if touch.grab_current is not self:
            return super().on_touch_move(touch)

        dy = touch.y - self._start_y
        self._start_y = touch.y

        if self.drag_callback:
            self.drag_callback(dy)

        return True

    # ---------------------------------------------------------

    def on_touch_up(self, touch):

        if touch.grab_current is not self:
            return super().on_touch_up(touch)

        touch.ungrab(self)

        dy = touch.y - self._start_y

        if self.end_callback:
            self.end_callback(dy)

        return True


GOM_USER_NAMESPACE = uuid.UUID(
    "deed0c7c-2899-4a65-97bd-3076028e86ba"
)

def user_uuid(username):
    """
    Generate a UUID for a given username using a fixed namespace.
    This ensures that the same username always produces the same UUID.
    """

    # Use a fixed namespace UUID for consistency
    namespace = GOM_USER_NAMESPACE
    return str(uuid.uuid5(namespace, username.strip().lower()))


class PageDots(Widget):

    page_count = NumericProperty(1)
    current_page = NumericProperty(0)

    def __init__(
        self,
        dot_size=dp(7),
        spacing=dp(8),
        **kwargs
    ):
        super().__init__(**kwargs)

        self.dot_size = dot_size
        self.spacing = spacing

        self.size_hint_y = None
        self.height = dp(18)

        self.bind(
            pos=self._redraw,
            size=self._redraw,
            page_count=self._redraw,
            current_page=self._redraw
        )

        Clock.schedule_once(
            self._redraw,
            0
        )

    def _redraw(self, *_):

        self.canvas.clear()

        if self.page_count <= 0:
            return

        total_width = (
            self.page_count * self.dot_size
            + (self.page_count - 1) * self.spacing
        )

        start_x = (
            self.center_x
            - total_width / 2
        )

        y = (
            self.center_y
            - self.dot_size / 2
        )

        with self.canvas:

            for i in range(self.page_count):

                if i == self.current_page:
                    Color(1, 1, 1, 1)
                else:
                    Color(1, 1, 1, 0.3)

                x = start_x + i * (
                    self.dot_size + self.spacing
                )

                Ellipse(
                    pos=(x, y),
                    size=(
                        self.dot_size,
                        self.dot_size
                    )
                )
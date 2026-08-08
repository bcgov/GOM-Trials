from pyobjus import autoclass, objc_str

from kivy.clock import Clock
from kivy.properties import (
    StringProperty,
    BooleanProperty
)
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.graphics import Color, Line

NumericFieldBridge = autoclass("NumericFieldBridge")
#UIScreen = autoclass("UIScreen")

class NativeNumericField(Widget):

    text = StringProperty("")
    placeholder = StringProperty("")
    focused = BooleanProperty(False)

    def __init__(self,
                 decimal=True,
                 poll_rate=50,
                 **kwargs):

        super().__init__(**kwargs)

        self._last_text = ""
        self.bridge = (
            NumericFieldBridge
            .alloc()
            .initDecimal_(decimal)
        )

        self._last_text = ""

        with self.canvas.after:
            Color(1, 0, 0)
            self._outline = Line(width=2)


        self.bind(
            pos=self._update_frame,
            size=self._update_frame,
            text=self._update_text,
            placeholder=self._update_placeholder,
        )
        Window.bind(
            on_resize=lambda *_: self._update_frame()
        )

        self.bridge.show()

        self._event = Clock.schedule_interval(
            self._poll,
            1 / poll_rate
        )

    def _poll(self, dt):
        self._update_frame()
        # --------------------------------------------------
        # Focus
        # --------------------------------------------------

        focused = bool(
            self.bridge.isFirstResponder()
        )

        if focused != self.focused:
            print(
                f"Native focus changed: "
                f"{self.focused} -> {focused}"
            )
            self.focused = focused
        # --------------------------------------------------
        # Text
        # --------------------------------------------------

        objc_text = self.bridge.text()

        if objc_text is None:
            text = ""
        else:
            text = objc_text.UTF8String()

            if isinstance(text, bytes):
                text = text.decode("utf-8")

        if text != self._last_text:

            self._last_text = text

            self.text = text

    def _update_text(self, *_):
        self._last_text = self.text
        self.bridge.setText_(
            objc_str(self.text)
        )

    def _update_placeholder(self, *_):
        self.bridge.setPlaceholder_(
            self.placeholder
        )

    def _update_frame(self, *_):
        matrix = self.get_window_matrix()
        new_x, new_y, _ = matrix.transform_point(0, 0, 0)

        self.bridge.setKivyFrameX_y_width_height_(
            new_x,
            new_y,
            self.width,
            self.height
        )

    def destroy(self):
        """Remove the native control and stop synchronization."""

        if getattr(self, "_destroyed", False):
            return

        self._destroyed = True

        # Dismiss keyboard if this field currently has focus
        self.bridge.resignFirstResponder()

        # Remove native UIView
        self.bridge.hide()

        # Stop polling
        if self._event is not None:
            self._event.cancel()
            self._event = None

        # Remove Window callback
        if hasattr(self, "_resize_callback"):
            Window.unbind(on_resize=self._resize_callback)

    def focus(self):
        self.bridge.becomeFirstResponder()

    def blur(self):
        self.bridge.resignFirstResponder()

    def on_parent(self, instance, parent):
        if parent is None:
            self.destroy()
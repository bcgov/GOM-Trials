from kivy.event import EventDispatcher
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    StringProperty,
)
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.animation import Animation


class SyncStatusBar(BoxLayout):

    COLOURS = {
        "synced": (0.22, 0.48, 0.30, 1),
        "pending": (0.78, 0.50, 0.10, 1),
        "syncing": (0.15, 0.42, 0.68, 1),
        "offline": (0.35, 0.35, 0.35, 1),
        "error": (0.65, 0.18, 0.18, 1),
    }

    def __init__(
        self,
        status,
        sync_callback=None,
        **kwargs
    ):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(42),
            padding=(dp(10), 0),
            spacing=dp(8),
            **kwargs
        )

        self.status = status
        self.sync_callback = sync_callback
        self._expanded_height = dp(42)
        self._is_visible = True

        with self.canvas.before:
            self._background_colour = Color(
                *self.COLOURS["synced"]
            )
            self._background = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(6)],
            )

        self.bind(
            pos=self._update_background,
            size=self._update_background,
        )

        self.status_label = Label(
            text="",
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
        )

        self.status_label.bind(
            size=self._update_label_text_size
        )

        self.sync_button = Button(
            text="Sync now",
            size_hint_x=None,
            width=dp(90),
        )

        self.sync_button.bind(
            on_release=self._on_sync_pressed
        )

        self.add_widget(self.status_label)
        self.add_widget(self.sync_button)

        status.bind(
            pending_trials=self._update_display,
            pending_assessments=self._update_display,
            is_syncing=self._update_display,
        )

        self._update_display()

    def _update_background(self, *_):
        self._background.pos = self.pos
        self._background.size = self.size

    def _update_label_text_size(self, label, size):
        label.text_size = size

    def _on_sync_pressed(self, instance):
        if (
            self.sync_callback
            and not self.status.is_syncing
        ):
            self.sync_callback(instance)

    def _update_display(self, *_):
        status = self.status

        if status.is_syncing:
            text = "Syncing…"
            colour = self.COLOURS["syncing"]
            button_text = "Syncing…"

        elif status.pending_total:
            text = self._pending_text()
            colour = self.COLOURS["pending"]
            button_text = "Sync now"

        else:
            text = "Up to date"
            colour = self.COLOURS["synced"]
            button_text = "Sync now"

        self.status_label.text = text
        self._background_colour.rgba = colour
        self.sync_button.text = button_text
        should_show = (
            status.pending_total > 0
            or status.is_syncing
        )
        self._set_visible(should_show)

    def _pending_text(self):
        parts = []

        if self.status.pending_trials:
            count = self.status.pending_trials
            noun = "trial" if count == 1 else "trials"
            parts.append(f"{count} {noun}")

        if self.status.pending_assessments:
            count = self.status.pending_assessments
            noun = (
                "assessment"
                if count == 1
                else "assessments"
            )
            parts.append(f"{count} {noun}")

        return f"{' and '.join(parts)} waiting to sync"

    def _set_visible(self, visible):
        if visible == self._is_visible:
            return

        self._is_visible = visible

        Animation.cancel_all(
            self,
            "height",
            "opacity",
        )

        if visible:
            self.disabled = False

            animation = Animation(
                height=self._expanded_height,
                opacity=1,
                duration=0.2,
            )
            animation.start(self)

        else:
            # Stop intercepting map touches as soon as hiding begins.
            self.disabled = True
            animation = Animation(
                height=0,
                opacity=0,
                duration=0.2,
            )
            animation.start(self)

class SyncStatus(EventDispatcher):
    pending_trials = NumericProperty(0)
    pending_assessments = NumericProperty(0)
    is_syncing = BooleanProperty(False)

    @property
    def pending_total(self):
        return (
            self.pending_trials
            + self.pending_assessments
        )

    def update_counts(self, trial_count, assessment_count):
        self.pending_trials = trial_count
        self.pending_assessments = assessment_count
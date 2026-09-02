from kivy.graphics import Color, Ellipse, Rectangle, Line
from kivy.metrics import dp
from kivy_garden.mapview import MapLayer
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel


from config import ASSESSMENT_COLOURS


class TrialMarkerLayer(MapLayer):

    def __init__(self, mapview, trial_callback=None, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("size", mapview.size)
        kwargs.setdefault("pos", mapview.pos)

        super().__init__(**kwargs)

        self._trigger_redraw = Clock.create_trigger(
            self._redraw_now,
            0,
        )
        self._species_texture_cache = {}
        self.mapview = mapview
        self.trial_callback = trial_callback
        self.trials = []
        self.visible_markers = []

        mapview.bind(
            size=self._sync_geometry,
            pos=self._sync_geometry,
        )

    def _get_species_texture(self, species_code):
        code = str(species_code or "?")

        texture = self._species_texture_cache.get(code)
        if texture is not None:
            return texture

        label = CoreLabel(
            text=code,
            font_size=dp(14),
            bold=True,

            # Black text
            color=(0, 0, 0, 1),

            # White outline
            outline_width=dp(2),
            outline_color=(1, 1, 1, 1),
        )
        label.refresh()

        texture = label.texture
        self._species_texture_cache[code] = texture
        return texture

    def _sync_geometry(self, *_):
        self.pos = self.mapview.pos
        self.size = self.mapview.size
        self._trigger_redraw()

    def reposition(self):
        # MapView calls this whenever its viewport changes.
        self._trigger_redraw()

    def set_trials(self, trials):
        self.trials = trials
        self._trigger_redraw()

    def get_trials_in_bounds(self, bbox):
        min_lat, min_lon, max_lat, max_lon = bbox

        return [
            trial["uuid"]
            for trial in self.trials
            if (
                min_lat <= trial["lat"] <= max_lat
                and min_lon <= trial["lon"] <= max_lon
            )
        ]

    def add_trial(self, new_trial):
        self.trials.append(new_trial)
        self._trigger_redraw()

    def delete_trial(self, trial_uuid):
        original_count = len(self.trials)

        self.trials = [
            trial
            for trial in self.trials
            if trial["uuid"] != trial_uuid
        ]

        if len(self.trials) == original_count:
            return False

        self._trigger_redraw()
        return True

    def _redraw_now(self, *_):
        self.canvas.clear()
        self.visible_markers.clear()

        zoom = self.mapview.zoom

        if zoom <= 7:
            diameter = dp(10)
        elif zoom <= 10:
            diameter = dp(12)
        else:
            diameter = dp(14)

        radius = diameter / 2
        bbox = self.mapview.get_bbox(diameter)

        with self.canvas:
            for trial in self.trials:
                if not bbox.collide(float(trial["lat"]), float(trial["lon"])):
                    continue

                x, y = self.mapview.get_window_xy_from(
                    float(trial["lat"]),
                    float(trial["lon"]),
                    zoom,
                )

                # x/y are absolute coordinates, so compare them
                # with absolute widget boundaries.
                if (
                    x < self.x - diameter
                    or y < self.y - diameter
                    or x > self.right + diameter
                    or y > self.top + diameter
                ):
                    continue

                colour = ASSESSMENT_COLOURS.get(
                    trial.get("performance"),
                    (0.35, 0.35, 0.35, 1),
                )

                if zoom < 12:
                    # Low and medium zoom: simple lightweight dot.
                    Color(*colour)

                    Ellipse(
                        pos=(x - radius, y - radius),
                        size=(diameter, diameter),
                    )

                    hit_radius = max(radius, dp(10))

                else:
                    # High zoom: icon resembling the original PNG.
                    icon_size = dp(34)
                    icon_radius = icon_size/2
                    border = dp(2)

                    left = x - icon_size / 2
                    bottom = y - icon_size / 2

                    # Performance-coloured outer border.
                    Color(*colour)

                    Line(
                        circle=(
                            x,
                            y,
                            icon_radius - border / 2,
                        ),
                        width=border,
                    )

                    # Cached orange species label.
                    texture = self._get_species_texture(
                        trial.get("species")
                    )

                    text_width, text_height = texture.size

                    Color(1, 1, 1, 1)

                    Rectangle(
                        texture=texture,
                        pos=(
                            x - text_width / 2,
                            y - text_height / 2,
                        ),
                        size=texture.size,
                    )

                    hit_radius = icon_size / 2

                self.visible_markers.append({
                    "trial": trial,
                    "x": x,
                    "y": y,
                    "radius": hit_radius,
                })

    def on_touch_down(self, touch):

        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        best = None
        best_dist2 = None

        for marker in self.visible_markers:

            dx = touch.x - marker["x"]
            dy = touch.y - marker["y"]

            dist2 = dx * dx + dy * dy

            if dist2 <= marker["radius"] ** 2:

                if (
                    best is None
                    or dist2 < best_dist2
                ):
                    best = marker
                    best_dist2 = dist2

        if best is not None:

            if self.trial_callback:
                self.trial_callback(
                    best["trial"]
                )

            return True

        return super().on_touch_down(touch)
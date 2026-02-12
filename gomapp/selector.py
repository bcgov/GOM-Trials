from kivy.uix.widget import Widget
from kivy.properties import ObjectProperty, BooleanProperty
from kivy.graphics import Color, Line

class RectSelectOverlay(Widget):
    """
    Transparent overlay that lets the user drag a rectangle and returns a bbox:
      bbox = (lat_min, lon_min, lat_max, lon_max)
    """
    enabled = BooleanProperty(False)

    def __init__(self, callback, mapview, **kwargs):
        super().__init__(**kwargs)
        self.on_bbox = callback
        self._touch = None
        self._p0 = None  # start (x,y) in mapview-local coords
        self._p1 = None  # end   (x,y) in mapview-local coords
        self._rect_line = None
        self.mapview = mapview

    def _clear_graphics(self):
        if self._rect_line is None:
            return
        self.canvas.after.remove(self._rect_line)
        self._rect_line = None

    def _draw_rect(self, x0, y0, x1, y1):
        # Keep it as a polyline rectangle
        left, right = sorted([x0, x1])
        bottom, top = sorted([y0, y1])

        self._clear_graphics()
        with self.canvas.after:
            Color(1, 1, 1, 0.9)  # border
            self._rect_line = Line(
                points=[left, bottom, right, bottom, right, top, left, top, left, bottom],
                width=1.5,
            )
            # If you want a translucent fill too, use a Rectangle with Color(..., alpha)
            # (keeping it simple here: border only)

    def _touch_to_map_local(self, touch):
        """
        touch.pos is in window coordinates.
        Convert to mapview-local widget coords (what get_latlon_at expects). :contentReference[oaicite:1]{index=1}
        """
        if not self.mapview:
            return None

        # Convert window coords to coordinates relative to the mapview widget
        x_mv, y_mv = self.mapview.to_widget(*touch.pos, relative=False)
        return (x_mv, y_mv)

    def on_touch_down(self, touch):
        if not self.enabled or not self.mapview:
            return super().on_touch_down(touch)

        # Only start selection if touch begins inside the mapview area
        if not self.mapview.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        self._touch = touch
        self._p0 = self._touch_to_map_local(touch)
        self._p1 = self._p0
        self._draw_rect(*self._p0, *self._p1)
        return True  # swallow: prevents map panning while selecting

    def on_touch_move(self, touch):
        if not self.enabled or touch is not self._touch:
            return super().on_touch_move(touch)

        self._p1 = self._touch_to_map_local(touch)
        self._draw_rect(*self._p0, *self._p1)
        return True

    def on_touch_up(self, touch):
        if not self.enabled or touch is not self._touch:
            return super().on_touch_up(touch)

        self._p1 = self._touch_to_map_local(touch)
        self._draw_rect(*self._p0, *self._p1)

        # Convert rectangle corners to lat/lon using MapView.get_latlon_at :contentReference[oaicite:2]{index=2}
        x0, y0 = self._p0
        x1, y1 = self._p1
        left, right = sorted([x0, x1])
        bottom, top = sorted([y0, y1])

        # Note: get_latlon_at returns a Coordinate (lon, lat) namedtuple in docs. :contentReference[oaicite:3]{index=3}
        c_bl = self.mapview.get_latlon_at(left, bottom)  # bottom-left
        c_tr = self.mapview.get_latlon_at(right, top)    # top-right

        lat_min = min(c_bl.lat, c_tr.lat)
        lat_max = max(c_bl.lat, c_tr.lat)
        lon_min = min(c_bl.lon, c_tr.lon)
        lon_max = max(c_bl.lon, c_tr.lon)

        bbox = (lat_min, lon_min, lat_max, lon_max)
        print("Bounding Box:",bbox)

        # Cleanup state
        self._touch = None
        self._p0 = None
        self._p1 = None
        self._clear_graphics()

        self.on_bbox(bbox)

        return True


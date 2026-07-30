import datetime

from kivy.graphics import Color, Line
from kivy_garden.mapview import MapLayer
import math
import time
from gom_logger import logger
from copy import deepcopy



class TrackLayer(MapLayer):
    """
    Displays one or more GPS tracks on a MapView.

    self.tracks is a list of track segments:
        [
            [(lat, lon), (lat, lon), ...],
            [(lat, lon), (lat, lon), ...],
            ...
        ]
    """

    def __init__(self,
                 color=(1, 0, 0, 0.8),
                 line_width=3,
                 **kwargs):
        super().__init__(**kwargs)

        self.tracks = []

        self.color = color
        self.line_width = line_width

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def clear(self):
        """Remove all tracks."""
        self.tracks.clear()
        self.reposition()

    def set_tracks(self, tracks):
        """Replace all tracks."""
        self.tracks = tracks
        self.reposition()

    def new_track(self):
        """Begin a new disconnected track."""
        self.tracks.append([])

    def add_point(self, lat, lon):
        """Append a point to the current track."""
        if not self.tracks:
            self.new_track()

        self.tracks[-1].append((lat, lon))
        self.reposition()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def reposition(self):
        """Redraw whenever the map moves or zooms."""

        self.canvas.clear()

        if not self.parent:
            return

        with self.canvas:

            Color(*self.color)

            for track in self.tracks:

                if len(track) < 2:
                    continue

                pts = []

                for lat, lon in track:

                    x, y = self.parent.get_window_xy_from(
                        lat,
                        lon,
                        self.parent.zoom
                    )

                    pts.extend((x, y))
                logger.info(f"[TRACK LAYER] Drawing track with {len(track)} points")
                Line(
                    points=pts,
                    width=self.line_width,
                    cap="round",
                    joint="round"
                )

class TrackRecorder:

    def __init__(self,
                 track_layer=None,
                 max_accuracy=20.0,
                 min_distance=3.0,
                 min_interval=2.0,
                 gps_timeout=30.0):

        self.track_layer = track_layer

        self.max_accuracy = max_accuracy
        self.min_distance = min_distance
        self.min_interval = min_interval
        self.gps_timeout = gps_timeout

        self.last_fix = None          # Most recent GPS fix
        self.last_saved = None        # Last accepted point

        self.total_distance = 0.0      # metres
        self.point_count = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_fix(self, fix):
        """
        Process a raw GPS fix.

        Returns True if the point was accepted.
        """

        self.last_fix = fix

        # --------------------------------------------------------------
        # Accuracy filter
        # --------------------------------------------------------------

        accuracy = fix.get("accuracy")
        if accuracy is None:
            return False

        if accuracy > self.max_accuracy:
            return False

        # --------------------------------------------------------------
        # First point
        # --------------------------------------------------------------

        if self.last_saved is None:
            self.accept_fix(fix)
            return True

        # --------------------------------------------------------------
        # Time since last accepted point
        # --------------------------------------------------------------

        timestamp = fix.get("timestamp")
        dt = timestamp - self.last_saved["timestamp"]

        # GPS dropout -> start a new segment
        # if dt > self.gps_timeout and self.track_layer is not None:
        #     self.track_layer.new_track()

        # --------------------------------------------------------------
        # Distance filter
        # --------------------------------------------------------------

        dist = self.distance(
            self.last_saved["lat"],
            self.last_saved["lon"],
            fix["lat"],
            fix["lon"]
        )

        # Adaptive movement threshold
        movement_threshold = max(
            self.min_distance,
            accuracy
        )

        if dist < movement_threshold:
            return False

        # --------------------------------------------------------------
        # Time filter
        # --------------------------------------------------------------

        if dt < self.min_interval:
            return False

        # --------------------------------------------------------------
        # Accept
        # --------------------------------------------------------------

        self.accept_fix(fix)

        return True

    # ------------------------------------------------------------------
    # Accept a point
    # ------------------------------------------------------------------

    def accept_fix(self, fix):
        if self.last_saved is not None:
            self.total_distance += self.distance(
                self.last_saved["lat"],
                self.last_saved["lon"],
                fix["lat"],
                fix["lon"]
            )
        self.point_count += 1
        self.last_saved = fix

        if self.track_layer is not None:
            self.track_layer.add_point(
                fix["lat"],
                fix["lon"]
            )

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def clear(self):

        self.last_fix = None
        self.last_saved = None
        self.total_distance = 0.0
        self.point_count = 0

        if self.track_layer is not None:
            self.track_layer.clear()


    def finish(self):
        """
        Finish the current track and return a dictionary containing
        the completed track and associated metadata.

        Returns None if no track has been recorded.
        """

        if self.point_count == 0:
            return None

        track = {
            "distance": self.total_distance,
            "point_count": self.point_count,
            "tracks": deepcopy(self.track_layer.tracks)
        }

        # Ready for the next recording
        self.clear()

        return track

    # ------------------------------------------------------------------
    # Great-circle distance (metres)
    # ------------------------------------------------------------------

    @staticmethod
    def distance(lat1, lon1, lat2, lon2):

        R = 6371000.0

        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)

        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1) *
            math.cos(lat2) *
            math.sin(dlon / 2) ** 2
        )

        c = 2 * math.atan2(
            math.sqrt(a),
            math.sqrt(1 - a)
        )

        return R * c
# coding=utf-8
"""
A hardened MBTiles provider for MapView.
Compatible with Kivy Garden MapView but safe on iOS.
"""

__all__ = ["MBTilesMapSource"]

import io
import sqlite3
import threading

from kivy.core.image import Image as CoreImage
from kivy_garden.mapview.downloader import Downloader
from kivy_garden.mapview.source import MapSource


class SafeMBTilesMapSource(MapSource):
    """
    SAFER version of the MapView MBTiles loader:
      • Opens MBTiles in read-only mode
      • Handles missing metadata keys gracefully
      • Provides fallback defaults for minzoom, maxzoom, bounds, center, projection
      • Supports iOS File Provider read-only files
      • Never crashes if metadata is incomplete
    """

    def __init__(self, filename, **kwargs):
        self.filename = filename

        # -----------------------------------------
        # 1. Load metadata FIRST (safe read-only)
        # -----------------------------------------
        meta = self._load_metadata_safely(filename)

        # Fallbacks (never missing)
        min_zoom = int(meta.get("minzoom", 0))
        max_zoom = int(meta.get("maxzoom", 18))
        bounds = meta.get("bounds", "-180,-85.0511,180,85.0511")
        center = meta.get("center", None)
        projection = meta.get("projection", "")
        attribution = meta.get("attribution", "")
        print(f"Min zoom: {min_zoom}")

        # Process bounds
        try:
            bx = list(map(float, bounds.split(",")))
            if len(bx) == 4:
                parsed_bounds = tuple(bx)
            else:
                raise ValueError
        except Exception:
            parsed_bounds = (-180, -85.0511, 180, 85.0511)

        # Process center
        if center:
            try:
                cx, cy, cz = list(map(float, center.split(",")))
            except Exception:
                cx, cy, cz = 0, 0, min_zoom
        else:
            # fallback: derive from bounds
            cx = (parsed_bounds[0] + parsed_bounds[2]) / 2
            cy = (parsed_bounds[1] + parsed_bounds[3]) / 2
            cz = min_zoom

        # Save attributes BEFORE parent call
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.bounds = parsed_bounds
        self.default_lon = cx
        self.default_lat = cy
        self.default_zoom = int(cz)
        self.attribution = attribution
        self.projection = projection
        self.is_xy = (projection == "xy")

        # -----------------------------------------
        # 2. Call MapSource constructor AFTER safe metadata
        # -----------------------------------------
        super().__init__(min_zoom=min_zoom, max_zoom=max_zoom, **kwargs)

    # ----------------------------------------------------------------------
    # SAFE METADATA LOADING
    # ----------------------------------------------------------------------
    def _load_metadata_safely(self, filename):
        meta = {}

        try:
            db = sqlite3.connect(f"file:{filename}?mode=ro", uri=True)
        except Exception:
            # Attempt normal open (may work for local files)
            try:
                db = sqlite3.connect(filename)
            except Exception as e:
                raise RuntimeError(f"Unable to open MBTiles file: {e}")

        c = db.cursor()

        # Load metadata if exists
        try:
            c.execute("SELECT name, value FROM metadata")
            meta = {k.lower(): v for k, v in c.fetchall()}
        except Exception:
            # No metadata table → use empty dict
            print("⚠ MBTiles has no metadata table, using defaults.")

        db.close()
        return meta

    # ----------------------------------------------------------------------
    # TILE LOADING (unchanged except safe DB handling)
    # ----------------------------------------------------------------------
    def fill_tile(self, tile):
        if tile.state == "done":
            return
        Downloader.instance(self.cache_dir).submit(self._load_tile, tile)

    def _load_tile(self, tile):
        # Each thread gets its own SQLite context
        ctx = threading.local()
        if not hasattr(ctx, "db"):
            try:
                ctx.db = sqlite3.connect(f"file:{self.filename}?mode=ro", uri=True)
            except Exception:
                ctx.db = sqlite3.connect(self.filename)

        c = ctx.db.cursor()
        c.execute(
            (
                "SELECT tile_data FROM tiles WHERE "
                "zoom_level=? AND tile_column=? AND tile_row=?"
            ),
            (tile.zoom, tile.tile_x, tile.tile_y),
        )
        row = c.fetchone()

        if not row:
            tile.state = "done"
            return

        # Load bytes into an image
        try:
            data = io.BytesIO(row[0])
        except Exception:
            data = io.BytesIO(bytes(row[0]))

        im = CoreImage(
            data, ext="png",
            filename=f"{tile.zoom}.{tile.tile_x}.{tile.tile_y}.png"
        )

        if im is None:
            tile.state = "done"
            return

        return self._load_tile_done, (tile, im,)

    def _load_tile_done(self, tile, im):
        tile.texture = im.texture
        tile.state = "need-animation"

    # Coordinate system overrides
    def get_x(self, zoom, lon):
        return lon if self.is_xy else super().get_x(zoom, lon)

    def get_y(self, zoom, lat):
        return lat if self.is_xy else super().get_y(zoom, lat)

    def get_lon(self, zoom, x):
        return x if self.is_xy else super().get_lon(zoom, x)

    def get_lat(self, zoom, y):
        return y if self.is_xy else super().get_lat(zoom, y)

class GoogleHybridSource(MapSource):
    def __init__(self, **kwargs):
        super().__init__(
            url="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attribution="Google Hybrid",
            max_zoom=20,
            min_zoom=1,
            **kwargs
        )

class GoogleTerrainSource(MapSource):
    def __init__(self, **kwargs):
        super().__init__(
            url="https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
            attribution="Google Terrain",
            max_zoom=18,
            min_zoom=1,
            **kwargs
        )

class OSMSource(MapSource):
    def __init__(self, **kwargs):
        super().__init__(
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution="© OpenStreetMap",
            max_zoom=19,
            **kwargs
        )

class BGCSource(MapSource):
    def __init__(self, **kwargs):
        super().__init__(
            url="https://tileserver.thebeczone.ca/data/BGC_Tiled_GOM/{z}/{x}/{y}.png",
            attribution="© BGC Map",
            max_zoom=19,
            **kwargs
        )
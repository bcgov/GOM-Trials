import numpy as np
import math
from kivy.uix.image import Image
from kivy_garden.mapview import MapView, MapMarker, MapMarkerPopup
from tifffile import TiffFile
import numpy as np
from kivy.graphics.texture import Texture

def webmercator_to_lonlat(x, y):
    """Convert x/y (meters) → lon/lat (degrees, EPSG:4326)."""
    lon = math.degrees(x / R)
    lat = math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)
    return lon, lat

class GeoTiffOverlay(Image):
    def __init__(self, geotiff_path, mapview: MapView, **kwargs):
        super().__init__(**kwargs)
        self.mapview = mapview

        with TiffFile(geotiff_path) as tif:
            img = tif.asarray()
            tags = tif.pages[0].tags

            # --- Extract approximate georeferencing ---
            model_tiepoint = tags.get("ModelTiepointTag")
            model_pixel_scale = tags.get("ModelPixelScaleTag")

            if model_tiepoint and model_pixel_scale:
                tiepoint = model_tiepoint.value
                scale = model_pixel_scale.value
                width = img.shape[-1]
                height = img.shape[-2]
                origin_x = tiepoint[3]
                origin_y = tiepoint[4]
                pixel_x = scale[0]
                pixel_y = scale[1]

                left = origin_x
                top = origin_y
                right = origin_x + width * pixel_x
                bottom = origin_y - height * pixel_y
                #self.merc_bounds = (left, bottom, right, top)
                
            print(f"Tiff shape: {img.shape}")
            if img.ndim == 3 and img.shape[2] >= 3:
                data = img[..., :3]
                data = np.nan_to_num(data).astype(np.uint8)
                print(f"Min val:{np.min(data)}; max val: {np.max(data)}")
                colorfmt = "rgb"
            else:
                data = img.astype(np.float32)
                data = 255 * (data - np.nanmin(data)) / (np.nanmax(data) - np.nanmin(data))
                data = np.nan_to_num(data).astype(np.uint8)
                colorfmt = "luminance"

            height, width = data.shape[:2]
            tex = Texture.create(size=(width, height), colorfmt=colorfmt)
            tex.blit_buffer(data.tobytes(), colorfmt=colorfmt, bufferfmt="ubyte")
            tex.flip_vertical()
            self.texture = tex
 

        # ✅ Convert bounds to WGS84 (lat/lon)
        
        ll_left, ll_bottom = webmercator_to_lonlat(left, bottom)
        ll_right, ll_top   = webmercator_to_lonlat(right, top)

        self.wgs_bounds = (ll_left, ll_bottom, ll_right, ll_top)
        print(f"File Bounds: {ll_left}, {ll_top}, {ll_right},{ll_bottom}")

        # Bind update on map movement
        self.mapview.bind(zoom=self.update_position, lat=self.update_position, lon=self.update_position)

    def update_position(self, *args):
        """Update overlay position and size relative to the map."""
        try:
            left, bottom, right, top = self.wgs_bounds  # in lon/lat order

            # MapView expects (lat, lon)
            x1, y1 = self.mapview.get_window_xy_from(top, left, self.mapview.zoom)      # top-left
            x2, y2 = self.mapview.get_window_xy_from(bottom, right, self.mapview.zoom)  # bottom-right

            self.pos = (x1, y2)
            self.size = (x2 - x1, y1 - y2)
            self.opacity = 0.6
            self.canvas.ask_update()

        except Exception as e:
            print("Error updating overlay position:", e)

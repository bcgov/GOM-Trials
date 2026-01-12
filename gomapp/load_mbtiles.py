from kivy_garden.mapview.mbtsource import MBTilesMapSource
import sqlite3

class SafeMBTilesSource(MBTilesMapSource):
    
    def __init__(self, filename, **kwargs):
        super().__init__(filename)
        # Ensure essential metadata exists
        conn = sqlite3.connect(filename)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT)")
        # Default metadata if missing
        for key, val in {
            "minzoom": "0",
            "maxzoom": "18",
            "center": "0,0,2",
            #"bounds": "-180,-90,180,90",  # default global bounds
        }.items():
            cur.execute("INSERT OR IGNORE INTO metadata (name, value) VALUES (?, ?)", (key, val))
        conn.commit()

        # Read metadata safely
        cur.execute("SELECT name, value FROM metadata")
        self.metadata = {name: value for name, value in cur.fetchall()}
        print(f"Metadata: {self.metadata}")
        conn.close()

        metadata = getattr(self, "metadata", {})

        # --- Safe bounds ---
        b = metadata.get("bounds", None)
        if b:
            try:
                parts = list(map(float, b.split(",")))
                if len(parts) == 4:
                    self._bounds = tuple(parts)
                else:
                    self._bounds = (-180, -85.05112878, 180, 85.05112878)
            except Exception:
                self._bounds = (-180, -85.05112878, 180, 85.05112878)
        else:
            self._bounds = (-180, -85.05112878, 180, 85.05112878)


        # Safe min/max zoom
        self.min_zoom = int(self.metadata.get("minzoom", 0))
        self.max_zoom = int(self.metadata.get("maxzoom", 18))
        self.default_zoom = int(self.metadata.get("defaultzoom", self.min_zoom))

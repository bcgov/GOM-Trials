from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USER_RE  = re.compile(r"^[A-Za-z0-9_]{3,32}$")
DB_PATH = Path.home() / "Documents" / "gomapp_data.db"
API_URL = "http://178.128.233.227"
R = 6378137.0  # Earth radius in meters

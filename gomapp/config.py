from pathlib import Path
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USER_RE  = re.compile(r"^[A-Za-z0-9_]{2,32}$")
DB_PATH = Path.home() / "Documents" / "gomapp_data.db"
API_URL = "http://178.128.233.227"
R = 6378137.0  # Earth radius in meters

icon_dict = {
    "fd": "Fd_icon32.png",
    "fdi": "Fd_icon32.png",
    "fdc": "Fd_icon32.png",
    "cw": "Cw_icon32.png",
    "pw": "Pw_icon32.png",
    "py": "Py_icon32.png",
    "lw": "Lw_icon32.png",
}
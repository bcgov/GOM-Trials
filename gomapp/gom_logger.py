import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
import sys

# Kivy redirects stderr into logging. If a console stream becomes unavailable
# after an iOS background/resume transition, reporting a handler failure to
# stderr recursively logs the same failure. Keep logging errors from escaping
# through that path (normal messages and application tracebacks still log).
logging.raiseExceptions = False

log_dir = Path.home() / "Documents"
log_dir.mkdir(exist_ok=True)

log_file = log_dir / "gom_log.txt"

logger = logging.getLogger("gom")
logger.setLevel(logging.INFO)
# Our rotating file is the destination; don't also send each message through
# Kivy/root console handlers, which may have an invalid stream after resume.
logger.propagate = False

# Prevent duplicate handlers
if not logger.handlers:

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8"
    )

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

logger.info("=== Logging initialized ===")

def handle_exception(exc_type, exc_value, exc_traceback):
    logger.exception(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

sys.excepthook = handle_exception

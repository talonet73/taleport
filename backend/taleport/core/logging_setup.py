"""Application logging: rotating file in the data folder, plus console when one exists."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from taleport.core.paths import logs_dir

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        logs_dir() / "taleport.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # A windowed (frozen) build has no console.
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

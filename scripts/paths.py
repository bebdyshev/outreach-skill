"""Where the reachout skill keeps user data (profile, leads, drafts)."""
import os
from pathlib import Path


def data_dir() -> Path:
    """Return ~/.reachout (or $REACHOUT_HOME), creating it and drafts/ if needed."""
    home = Path(os.environ.get("REACHOUT_HOME") or Path.home() / ".reachout")
    (home / "drafts").mkdir(parents=True, exist_ok=True)
    return home

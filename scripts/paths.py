"""Where the outreach skill keeps user data (profile, leads, drafts)."""
import os
from pathlib import Path


def data_dir() -> Path:
    """Return ~/.outreach (or $OUTREACH_HOME), creating it and drafts/ if needed."""
    home = Path(os.environ.get("OUTREACH_HOME") or Path.home() / ".outreach")
    (home / "drafts").mkdir(parents=True, exist_ok=True)
    return home

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture(autouse=True)
def outreach_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTREACH_HOME", str(tmp_path))
    return tmp_path

"""The exe entry script runs as a top-level __main__ under PyInstaller, so it must not use relative imports."""

import runpy
from pathlib import Path

from orm_packer import gui


def test_entry_script_runs_as_top_level_script(monkeypatch):
    calls = []
    monkeypatch.setattr(gui, "main", lambda: calls.append("ran"))
    runpy.run_path(str(Path("orm_packer") / "__main__.py"), run_name="__main__")
    assert calls == ["ran"]

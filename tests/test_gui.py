"""Scripted version of the plan's manual GUI checklist. Drives real Tk widgets with dialogs patched out."""

import tkinter as tk
from pathlib import Path

import pytest
from PIL import Image

from orm_packer import gui


@pytest.fixture
def app():
    try:
        window = gui.App()
    except tk.TclError as exc:  # no display
        pytest.skip(f"Tk unavailable: {exc}")
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def errors(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, msg: seen.append(msg))
    return seen


def test_pack_without_output_errors(app, errors):
    app.do_pack()
    assert errors == ["Choose an output file first."]


def test_size_dialog_cancel_writes_nothing(app, errors, tmp_path, monkeypatch):
    app.output.set(str(tmp_path / "orm.tga"))
    monkeypatch.setattr(app, "ask_size", lambda: None)
    app.do_pack()
    assert errors == []
    assert not (tmp_path / "orm.tga").exists()


def test_pack_single_file_writes_and_reports(app, errors, tmp_path, make_grey):
    app.rows[0].path = make_grey("ao.png", 10)
    app.output.set(str(tmp_path / "orm.tga"))
    app.do_pack()
    assert errors == []
    assert (tmp_path / "orm.tga").exists()
    assert app.status.get().startswith("Wrote ")
    assert "4×4" in app.status.get()


def test_format_overrides_output_extension(app, errors, tmp_path, make_grey):
    app.rows[0].path = make_grey("ao.png", 10)
    app.output.set(str(tmp_path / "orm.tga"))
    app.format.set("PNG")
    app.do_pack()
    assert errors == []
    assert (tmp_path / "orm.png").exists()
    assert not (tmp_path / "orm.tga").exists()


def test_size_mismatch_reported_and_nothing_written(app, errors, tmp_path, make_grey):
    app.rows[0].path = make_grey("ao.png", 1, size=(4, 4))
    app.rows[1].path = make_grey("rough.png", 2, size=(8, 4))
    app.output.set(str(tmp_path / "orm.tga"))
    app.do_pack()
    assert len(errors) == 1
    assert "ao.png" in errors[0] and "rough.png" in errors[0]
    assert not (tmp_path / "orm.tga").exists()


def test_bad_levels_reported(app, errors, tmp_path, make_grey):
    app.rows[0].path = make_grey("ao.png", 1)
    app.rows[0].black.set(200)
    app.rows[0].white.set(100)
    app.output.set(str(tmp_path / "orm.tga"))
    app.do_pack()
    assert len(errors) == 1
    assert "levels" in errors[0]


def test_non_numeric_levels_reported(app, errors, tmp_path, make_grey):
    app.rows[0].path = make_grey("ao.png", 1)
    app.output.set(str(tmp_path / "orm.tga"))
    # Simulate typing text into the spinbox: the underlying Tcl variable holds a string.
    app.tk.globalsetvar(str(app.rows[0].black), "abc")
    app.do_pack()
    assert errors == ["Levels must be whole numbers from 0 to 255."]


def test_flat_value_lands_in_channel(app, errors, tmp_path, make_grey):
    app.rows[0].path = make_grey("ao.png", 10)
    app.rows[2].use_flat.set(True)
    app.rows[2].flat.set(50)
    app.output.set(str(tmp_path / "orm.png"))
    app.format.set("PNG")
    app.do_pack()
    assert errors == []
    with Image.open(tmp_path / "orm.png") as out:
        assert out.getpixel((0, 0)) == (10, 0, 128)


def test_clear_resets_row(app):
    row = app.rows[1]
    row.path = Path("x.png")
    row.file_label.set("x.png")
    row.clear()
    assert row.path is None
    assert row.file_label.get() == "no file"
    assert row.slot().path is None

from pathlib import Path

import pytest
from PIL import Image

from orm_packer.pipeline import SizeMismatch, Slot, needs_size, pack


def rgb(image: Image.Image) -> tuple[int, int, int]:
    return image.getpixel((0, 0))


def test_channel_mapping(make_grey):
    ao = make_grey("ao.tga", 10)
    rough = make_grey("rough.tga", 20)
    metal = make_grey("metal.tga", 30)
    out = pack(Slot(path=ao), Slot(path=rough), Slot(path=metal))
    assert out.mode == "RGB"
    assert out.size == (4, 4)
    assert rgb(out) == (10, 20, 30)


def test_missing_slot_is_black(make_grey):
    ao = make_grey("ao.tga", 10)
    out = pack(Slot(path=ao), Slot(), Slot())
    assert rgb(out) == (10, 0, 0)


def test_flat_value_overrides_file(make_grey):
    ao = make_grey("ao.tga", 10)
    out = pack(Slot(path=ao), Slot(path=ao, flat_value=50), Slot(flat_value=100))
    assert rgb(out) == (10, 128, 255)


def test_channel_pick_per_slot(tmp_path, make_grey):
    rgba = tmp_path / "packed.png"
    Image.new("RGBA", (4, 4), (1, 2, 3, 4)).save(rgba)
    ao = make_grey("ao.tga", 10)
    out = pack(Slot(path=ao), Slot(path=rgba, channel="B"), Slot(path=rgba, channel="A"))
    assert rgb(out) == (10, 3, 4)


def test_tweaks_apply_per_slot(make_grey):
    ao = make_grey("ao.tga", 64)
    rough = make_grey("rough.tga", 100)
    out = pack(
        Slot(path=ao, black_point=64, white_point=192),
        Slot(path=rough, invert=True),
        Slot(invert=True),
    )
    assert rgb(out) == (0, 155, 255)


def test_size_mismatch_raises(make_grey):
    ao = make_grey("ao.tga", 1, size=(4, 4))
    rough = make_grey("rough.tga", 2, size=(8, 4))
    with pytest.raises(SizeMismatch) as info:
        pack(Slot(path=ao), Slot(path=rough), Slot())
    assert "ao.tga" in str(info.value)
    assert "rough.tga" in str(info.value)


def test_non_square_keeps_orientation(make_grey):
    ao = make_grey("ao.tga", 1, size=(8, 2))
    out = pack(Slot(path=ao), Slot(), Slot())
    assert out.size == (8, 2)


def test_no_files_requires_size():
    with pytest.raises(ValueError, match="size"):
        pack(Slot(), Slot(flat_value=10), Slot())


def test_no_files_with_size_gives_black_and_flat():
    out = pack(Slot(), Slot(flat_value=10), Slot(), size=(16, 8))
    assert out.size == (16, 8)
    assert rgb(out) == (0, 26, 0)


def test_size_argument_ignored_when_files_present(make_grey):
    ao = make_grey("ao.tga", 1, size=(4, 4))
    out = pack(Slot(path=ao), Slot(), Slot(), size=(99, 99))
    assert out.size == (4, 4)


def test_needs_size():
    assert needs_size(Slot(), Slot(), Slot()) is True
    assert needs_size(Slot(flat_value=1), Slot(), Slot()) is True
    assert needs_size(Slot(path=Path("x.tga"), flat_value=1), Slot(), Slot()) is True
    assert needs_size(Slot(path=Path("x.tga")), Slot(), Slot()) is False


def test_bad_file_propagates(tmp_path):
    bad = tmp_path / "bad.tga"
    bad.write_bytes(b"nope")
    with pytest.raises(OSError):
        pack(Slot(path=bad), Slot(), Slot())

import pytest
from PIL import Image

from orm_packer.pipeline import black_plane, flat_plane, load_plane


def test_flat_plane_maps_percent_to_byte():
    assert flat_plane(0, (2, 2)).getpixel((0, 0)) == 0
    assert flat_plane(50, (2, 2)).getpixel((0, 0)) == 128
    assert flat_plane(100, (2, 2)).getpixel((0, 0)) == 255


def test_flat_plane_has_requested_size_and_mode():
    plane = flat_plane(10, (3, 5))
    assert plane.size == (3, 5)
    assert plane.mode == "L"


@pytest.mark.parametrize("value", [-1, 101])
def test_flat_plane_rejects_out_of_range(value):
    with pytest.raises(ValueError):
        flat_plane(value, (2, 2))


def test_black_plane():
    plane = black_plane((4, 2))
    assert plane.size == (4, 2)
    assert plane.mode == "L"
    assert plane.getextrema() == (0, 0)


def test_load_grey_from_l_file(make_grey):
    path = make_grey("ao.tga", 77)
    plane = load_plane(path, "Grey")
    assert plane.mode == "L"
    assert plane.getpixel((0, 0)) == 77


def test_load_named_channels_from_rgba(tmp_path):
    path = tmp_path / "rgba.png"
    Image.new("RGBA", (2, 2), (10, 20, 30, 40)).save(path)
    assert load_plane(path, "R").getpixel((0, 0)) == 10
    assert load_plane(path, "G").getpixel((0, 0)) == 20
    assert load_plane(path, "B").getpixel((0, 0)) == 30
    assert load_plane(path, "A").getpixel((0, 0)) == 40


def test_load_missing_band_raises(make_grey):
    path = make_grey("ao.png", 5)
    with pytest.raises(ValueError, match="no A channel"):
        load_plane(path, "A")


def test_load_unknown_channel_raises(make_grey):
    path = make_grey("ao.png", 5)
    with pytest.raises(ValueError):
        load_plane(path, "X")


def test_load_grey_from_rgb_with_equal_channels_is_lossless(tmp_path):
    path = tmp_path / "rgb.png"
    Image.new("RGB", (2, 2), (90, 90, 90)).save(path)
    assert load_plane(path, "Grey").getpixel((0, 0)) == 90


def test_load_16bit_scales_to_8bit(tmp_path):
    path = tmp_path / "deep.png"
    Image.new("I;16", (2, 2), 65535).save(path)
    assert load_plane(path, "Grey").getpixel((0, 0)) == 255
    half = tmp_path / "half.png"
    Image.new("I;16", (2, 2), 32768).save(half)
    assert load_plane(half, "Grey").getpixel((0, 0)) in (127, 128)


def test_load_palette_and_la_inputs(tmp_path):
    pal = tmp_path / "pal.png"
    Image.new("RGB", (2, 2), (60, 70, 80)).convert("P", palette=Image.Palette.ADAPTIVE).save(pal)
    assert load_plane(pal, "R").getpixel((0, 0)) == 60
    assert load_plane(pal, "Grey").mode == "L"
    la = tmp_path / "la.png"
    Image.new("LA", (2, 2), (33, 200)).save(la)
    assert load_plane(la, "Grey").getpixel((0, 0)) == 33
    assert load_plane(la, "A").getpixel((0, 0)) == 200


def test_load_unreadable_file_raises(tmp_path):
    bad = tmp_path / "bad.tga"
    bad.write_bytes(b"not an image")
    with pytest.raises(OSError):
        load_plane(bad, "Grey")

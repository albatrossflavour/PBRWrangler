import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from orm_packer.pipeline import FORMATS, Slot, pack, resolve_output_path, save


def test_formats_listed():
    assert list(FORMATS) == ["TGA", "PNG"]


def test_resolve_output_path_rewrites_extension():
    assert resolve_output_path(Path("out/orm.png"), "TGA") == Path("out/orm.tga")
    assert resolve_output_path(Path("out/orm"), "PNG") == Path("out/orm.png")
    assert resolve_output_path(Path("out/orm.TGA"), "TGA") == Path("out/orm.tga")


def test_resolve_output_path_unknown_format():
    with pytest.raises(ValueError):
        resolve_output_path(Path("x"), "BMP")


@pytest.mark.parametrize("fmt", ["TGA", "PNG"])
def test_round_trip_preserves_values(tmp_path, make_grey, fmt):
    ao = make_grey("ao.tga", 10)
    rough = make_grey("rough.tga", 20)
    metal = make_grey("metal.tga", 30)
    image = pack(Slot(path=ao), Slot(path=rough), Slot(path=metal))
    out = resolve_output_path(tmp_path / "orm.whatever", fmt)
    save(image, out)
    with Image.open(out) as back:
        back.load()
        assert back.mode == "RGB"
        assert back.getpixel((0, 0)) == (10, 20, 30)


def test_tga_is_uncompressed(tmp_path, make_grey):
    ao = make_grey("ao.tga", 10, size=(64, 64))
    image = pack(Slot(path=ao), Slot(), Slot())
    out = tmp_path / "orm.tga"
    save(image, out)
    # 18-byte header + 64*64*3 bytes of pixels, plus optional footer. RLE would be far smaller for a flat image.
    assert out.stat().st_size >= 18 + 64 * 64 * 3


def test_save_failure_raises(tmp_path, make_grey):
    ao = make_grey("ao.tga", 10)
    image = pack(Slot(path=ao), Slot(), Slot())
    with pytest.raises(OSError):
        save(image, tmp_path / "missing_dir" / "orm.tga")


@pytest.mark.skipif(shutil.which("magick") is None, reason="ImageMagick not installed")
def test_matches_imagemagick_combine(tmp_path):
    def gradient(name: str, offset: int) -> Path:
        img = Image.new("L", (16, 16))
        img.putdata([(x + y * 16 + offset) % 256 for y in range(16) for x in range(16)])
        path = tmp_path / name
        img.save(path)
        return path

    ao = gradient("ao.tga", 0)
    rough = gradient("rough.tga", 50)
    metal = gradient("metal.tga", 100)
    magick_out = tmp_path / "magick.tga"
    subprocess.run(
        ["magick", str(ao), str(rough), str(metal), "-set", "colorspace", "sRGB", "-combine", str(magick_out)],
        check=True,
    )
    ours = pack(Slot(path=ao), Slot(path=rough), Slot(path=metal))
    with Image.open(magick_out) as theirs:
        theirs.load()
        assert theirs.convert("RGB").tobytes() == ours.tobytes()

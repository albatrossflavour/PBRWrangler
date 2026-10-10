# ORM Packer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Windows desktop app that packs three greyscale PBR maps into the R, G, and B channels of one ORM texture, with black fallback, channel pick, invert, levels, and flat value per slot.

**Architecture:** A pure pipeline module (`orm_packer/pipeline.py`) does all image work with Pillow and knows nothing about Tk. A thin Tk window (`orm_packer/gui.py`) collects the form into `Slot` values, calls `pack`, saves the result, and turns exceptions into message boxes. Pytest covers the pipeline; the GUI is tested by hand.

**Tech Stack:** Python 3.12+, Pillow, tkinter (stdlib), pytest, PyInstaller (Windows only).

**Spec:** `docs/superpowers/specs/2026-10-10-orm-packer-design.md`

## Global Constraints

- Python 3.12 or later.
- Runtime dependency is Pillow only. No numpy, no PySide.
- No colour space conversion anywhere. Pixel values are copied unchanged.
- Channel order is fixed: AO to R, roughness to G, metallic to B.
- Per slot order of operations: source plane (flat, black, or file channel), then levels, then invert.
- Flat value is 0 to 100 and maps to `round(value * 255 / 100)`.
- Levels: `out = clamp((in - black) * 255 / (white - black), 0, 255)`, white must be greater than black.
- No silent resize. Mismatched input sizes raise `SizeMismatch`.
- Output has no alpha channel. TGA is written uncompressed.
- Every pipeline failure is an exception; the GUI shows it in a message box and leaves the form untouched.

## Review Focus

- Palette (`P`) or `LA` inputs with Grey selected must still yield a clean `L` plane, and `R`/`G`/`B` on a `P` image must work after conversion to RGBA. Test added to Task 2.
- Flat value outside 0 to 100 (the GUI slider cannot produce it, but the dataclass can) must raise `ValueError`, not silently wrap. Test added to Task 2.
- Levels with black or white outside 0 to 255, or white equal to black, must raise `ValueError` with a readable message. Test added to Task 3.
- Non-square inputs must keep width and height in the right order in the output. Test added to Task 4.
- An output path whose extension disagrees with the chosen format must be rewritten to match the format, so a user who types `orm.png` with TGA selected gets `orm.tga`. Test added to Task 5.

---

### Task 1: Project scaffold

**Files:**

- Create: `pyproject.toml`
- Create: `orm_packer/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`

**Interfaces:**

- Produces: `conftest.make_grey(tmp_path, name, value, size=(4, 4))` helper returning the written path, used by every later test file.

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "orm-packer"
version = "0.1.0"
description = "Pack AO, roughness, and metallic maps into one ORM texture"
requires-python = ">=3.12"
dependencies = ["Pillow>=10"]

[project.optional-dependencies]
dev = ["pytest>=8", "pyinstaller>=6"]

[project.scripts]
orm-packer = "orm_packer.gui:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["orm_packer*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write the package and test scaffolding**

`orm_packer/__init__.py`:

```python
"""Pack AO, roughness, and metallic maps into one ORM texture."""
```

`tests/__init__.py` is empty.

`tests/conftest.py`:

```python
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def make_grey(tmp_path):
    """Write a solid 8-bit greyscale image and return its path."""

    def _make(name: str, value: int, size: tuple[int, int] = (4, 4)) -> Path:
        path = tmp_path / name
        Image.new("L", size, value).save(path)
        return path

    return _make
```

`.gitignore`:

```text
.venv/
__pycache__/
*.pyc
build/
dist/
*.spec
.pytest_cache/
```

- [ ] **Step 3: Create a venv and install**

Run:

```bash
cd ~/dev/orm-packer && python3 -m venv .venv && .venv/bin/pip install -q -e '.[dev]' && .venv/bin/pytest -q
```

Expected: `no tests ran` with exit code 5. That proves pytest and Pillow import.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml orm_packer tests .gitignore
git commit -m "Scaffold orm-packer package"
```

---

### Task 2: Source planes (flat, black, file channel)

**Files:**

- Create: `orm_packer/pipeline.py`
- Create: `tests/test_planes.py`

**Interfaces:**

- Produces:
  - `CHANNELS: tuple[str, ...] = ("Grey", "R", "G", "B", "A")`
  - `flat_plane(value: int, size: tuple[int, int]) -> Image.Image` (mode L)
  - `black_plane(size: tuple[int, int]) -> Image.Image` (mode L)
  - `load_plane(path: Path, channel: str) -> Image.Image` (mode L)

- [ ] **Step 1: Write the failing tests**

`tests/test_planes.py`:

```python
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
    Image.new("RGB", (2, 2), (60, 70, 80)).convert("P").save(pal)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_planes.py -q`
Expected: FAIL at import, `cannot import name 'black_plane' from 'orm_packer.pipeline'` (or module not found).

- [ ] **Step 3: Write the implementation**

`orm_packer/pipeline.py`:

```python
"""Image pipeline for ORM packing. Pure Pillow, no Tk."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

CHANNELS: tuple[str, ...] = ("Grey", "R", "G", "B", "A")

_SIXTEEN_BIT_MODES = {"I", "I;16", "I;16B", "I;16L", "I;16N"}


def flat_plane(value: int, size: tuple[int, int]) -> Image.Image:
    """A constant L plane from a 0..100 percentage."""
    if not 0 <= value <= 100:
        raise ValueError(f"flat value must be 0 to 100, got {value}")
    return Image.new("L", size, round(value * 255 / 100))


def black_plane(size: tuple[int, int]) -> Image.Image:
    return Image.new("L", size, 0)


def load_plane(path: Path, channel: str) -> Image.Image:
    """Load one 8-bit L plane from a file: the whole image as grey, or one named band."""
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}, expected one of {CHANNELS}")
    with Image.open(path) as opened:
        opened.load()
        image = opened
        if image.mode in _SIXTEEN_BIT_MODES:
            # Pillow accepts a linear lambda for I-mode point(): scale 0..65535 to 0..255.
            image = image.convert("I").point(lambda v: v * (255 / 65535), "L")
        if image.mode == "P":
            image = image.convert("RGBA")
        if channel == "Grey":
            return image.convert("L")
        if channel not in image.getbands():
            raise ValueError(f"{path.name} has no {channel} channel (bands: {''.join(image.getbands())})")
        return image.getchannel(channel)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_planes.py -q`
Expected: all PASS. If `test_load_16bit_scales_to_8bit` fails on the half value, the installed Pillow rounds differently; the assertion already allows 127 or 128, so check the full-scale case first.

- [ ] **Step 5: Commit**

```bash
git add orm_packer/pipeline.py tests/test_planes.py
git commit -m "Add source plane loading: flat, black, and file channels"
```

---

### Task 3: Levels and invert

**Files:**

- Modify: `orm_packer/pipeline.py`
- Create: `tests/test_adjust.py`

**Interfaces:**

- Consumes: nothing new.
- Produces: `adjust(plane: Image.Image, black_point: int, white_point: int, invert: bool) -> Image.Image` (mode L in, mode L out).

- [ ] **Step 1: Write the failing tests**

`tests/test_adjust.py`:

```python
import pytest
from PIL import Image

from orm_packer.pipeline import adjust


def plane(value: int) -> Image.Image:
    return Image.new("L", (2, 2), value)


def px(image: Image.Image) -> int:
    return image.getpixel((0, 0))


def test_identity_levels_no_invert():
    assert px(adjust(plane(123), 0, 255, False)) == 123


def test_levels_stretch():
    # black 64, white 192: 64 -> 0, 128 -> 128, 192 -> 255
    assert px(adjust(plane(64), 64, 192, False)) == 0
    assert px(adjust(plane(128), 64, 192, False)) == 128
    assert px(adjust(plane(192), 64, 192, False)) == 255


def test_levels_clamp():
    assert px(adjust(plane(10), 64, 192, False)) == 0
    assert px(adjust(plane(250), 64, 192, False)) == 255


def test_invert():
    assert px(adjust(plane(0), 0, 255, True)) == 255
    assert px(adjust(plane(200), 0, 255, True)) == 55


def test_levels_then_invert():
    # 64 -> 0 by levels, then invert -> 255
    assert px(adjust(plane(64), 64, 192, True)) == 255


@pytest.mark.parametrize(
    "black,white",
    [(128, 128), (200, 100), (-1, 255), (0, 256)],
)
def test_bad_levels_raise(black, white):
    with pytest.raises(ValueError, match="levels"):
        adjust(plane(0), black, white, False)


def test_adjust_keeps_mode_and_size():
    out = adjust(Image.new("L", (3, 5), 9), 0, 255, True)
    assert out.mode == "L"
    assert out.size == (3, 5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_adjust.py -q`
Expected: FAIL, `cannot import name 'adjust'`.

- [ ] **Step 3: Write the implementation**

Append to `orm_packer/pipeline.py`:

```python
def adjust(plane: Image.Image, black_point: int, white_point: int, invert: bool) -> Image.Image:
    """Apply input levels then optional invert to an L plane."""
    if not (0 <= black_point < white_point <= 255):
        raise ValueError(
            f"levels need 0 <= black < white <= 255, got black={black_point} white={white_point}"
        )
    scale = 255 / (white_point - black_point)

    def level(v: int) -> int:
        return max(0, min(255, round((v - black_point) * scale)))

    out = plane.point(level)
    if invert:
        out = out.point(lambda v: 255 - v)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_adjust.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add orm_packer/pipeline.py tests/test_adjust.py
git commit -m "Add levels and invert adjustment"
```

---

### Task 4: Slot and pack

**Files:**

- Modify: `orm_packer/pipeline.py`
- Create: `tests/test_pack.py`

**Interfaces:**

- Consumes: `flat_plane`, `black_plane`, `load_plane`, `adjust` from Tasks 2 and 3.
- Produces:
  - `class SizeMismatch(ValueError)`
  - `@dataclass Slot(path: Path | None = None, channel: str = "Grey", invert: bool = False, black_point: int = 0, white_point: int = 255, flat_value: int | None = None)`
  - `pack(ao: Slot, roughness: Slot, metallic: Slot, size: tuple[int, int] | None = None) -> Image.Image` (mode RGB)
  - `needs_size(*slots: Slot) -> bool` (True when no slot will load a file)

- [ ] **Step 1: Write the failing tests**

`tests/test_pack.py`:

```python
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
    out = pack(Slot(path=ao, flat_value=100), Slot(flat_value=50), Slot())
    assert rgb(out) == (255, 128, 0)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pack.py -q`
Expected: FAIL, `cannot import name 'SizeMismatch'`.

- [ ] **Step 3: Write the implementation**

Add to the imports at the top of `orm_packer/pipeline.py`:

```python
from dataclasses import dataclass
```

Append to `orm_packer/pipeline.py`:

```python
class SizeMismatch(ValueError):
    """Input files do not share one size."""


@dataclass
class Slot:
    path: Path | None = None
    channel: str = "Grey"
    invert: bool = False
    black_point: int = 0
    white_point: int = 255
    flat_value: int | None = None  # 0..100, overrides path when set

    @property
    def loads_file(self) -> bool:
        return self.flat_value is None and self.path is not None


_SLOT_NAMES = ("AO", "Roughness", "Metallic")


def needs_size(*slots: Slot) -> bool:
    """True when no slot will load a file, so the caller must supply an output size."""
    return not any(slot.loads_file for slot in slots)


def pack(
    ao: Slot,
    roughness: Slot,
    metallic: Slot,
    size: tuple[int, int] | None = None,
) -> Image.Image:
    """Pack three slots into an RGB image. Raises on any bad input; writes nothing."""
    slots = (ao, roughness, metallic)

    loaded: dict[str, Image.Image] = {}
    for name, slot in zip(_SLOT_NAMES, slots):
        if slot.loads_file:
            assert slot.path is not None
            loaded[name] = load_plane(slot.path, slot.channel)

    if loaded:
        sizes = {name: plane.size for name, plane in loaded.items()}
        if len(set(sizes.values())) > 1:
            detail = ", ".join(
                f"{name} {slot.path.name} {sizes[name][0]}x{sizes[name][1]}"
                for name, slot in zip(_SLOT_NAMES, slots)
                if name in sizes
            )
            raise SizeMismatch(f"input sizes differ: {detail}")
        size = next(iter(sizes.values()))
    elif size is None:
        raise ValueError("no input files loaded, so an output size is required")

    planes = []
    for name, slot in zip(_SLOT_NAMES, slots):
        if slot.flat_value is not None:
            plane = flat_plane(slot.flat_value, size)
        elif slot.path is None:
            plane = black_plane(size)
        else:
            plane = loaded[name]
        planes.append(adjust(plane, slot.black_point, slot.white_point, slot.invert))

    return Image.merge("RGB", planes)
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add orm_packer/pipeline.py tests/test_pack.py
git commit -m "Add Slot and pack"
```

---

### Task 5: Output path, round trip, and ImageMagick parity

**Files:**

- Modify: `orm_packer/pipeline.py`
- Create: `tests/test_output.py`

**Interfaces:**

- Consumes: `Slot`, `pack` from Task 4.
- Produces:
  - `FORMATS: dict[str, str] = {"TGA": ".tga", "PNG": ".png"}`
  - `resolve_output_path(path: Path, fmt: str) -> Path`
  - `save(image: Image.Image, path: Path) -> None`

- [ ] **Step 1: Write the failing tests**

`tests/test_output.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_output.py -q`
Expected: FAIL, `cannot import name 'FORMATS'`.

- [ ] **Step 3: Write the implementation**

Append to `orm_packer/pipeline.py`:

```python
FORMATS: dict[str, str] = {"TGA": ".tga", "PNG": ".png"}


def resolve_output_path(path: Path, fmt: str) -> Path:
    """Force the output path's extension to match the chosen format."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}, expected one of {list(FORMATS)}")
    return path.with_suffix(FORMATS[fmt])


def save(image: Image.Image, path: Path) -> None:
    """Write the packed image. TGA is uncompressed (Pillow's default without rle=True)."""
    image.save(path)
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all PASS, with the magick test either passing or skipped. If `magick` is installed and the parity test fails, print both images' first row and check whether ImageMagick wrote a BGR TGA that Pillow decodes correctly; the `convert("RGB")` call is there to normalise mode only, not channel order.

- [ ] **Step 5: Commit**

```bash
git add orm_packer/pipeline.py tests/test_output.py
git commit -m "Add output path resolution, save, and ImageMagick parity test"
```

---

### Task 6: Tk window

**Files:**

- Create: `orm_packer/gui.py`
- Create: `orm_packer/__main__.py`

**Interfaces:**

- Consumes: `CHANNELS`, `FORMATS`, `Slot`, `SizeMismatch`, `needs_size`, `pack`, `resolve_output_path`, `save` from Tasks 2 to 5.
- Produces: `main() -> None` referenced by `pyproject.toml` `[project.scripts]`.

No automated tests. The pipeline is covered; this task is verified by hand in Step 3.

- [ ] **Step 1: Write the window**

`orm_packer/gui.py`:

```python
"""Tk front end. Collects the form into Slots, calls pack, shows errors."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .pipeline import (
    CHANNELS,
    FORMATS,
    Slot,
    needs_size,
    pack,
    resolve_output_path,
    save,
)

IMAGE_TYPES = [
    ("Images", "*.tga *.png *.tif *.tiff *.bmp *.jpg *.jpeg"),
    ("All files", "*.*"),
]


class SlotRow:
    """One row of the form: file, channel, invert, levels, flat value."""

    def __init__(self, parent: ttk.Frame, label: str, row: int) -> None:
        self.path: Path | None = None
        self.file_label = tk.StringVar(value="no file")
        self.channel = tk.StringVar(value="Grey")
        self.invert = tk.BooleanVar(value=False)
        self.black = tk.IntVar(value=0)
        self.white = tk.IntVar(value=255)
        self.use_flat = tk.BooleanVar(value=False)
        self.flat = tk.IntVar(value=0)

        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8))
        ttk.Button(parent, text="Browse", command=self.browse).grid(row=row, column=1)
        ttk.Button(parent, text="×", width=2, command=self.clear).grid(row=row, column=2)
        ttk.Label(parent, textvariable=self.file_label, width=28).grid(row=row, column=3, sticky="w", padx=(4, 8))
        ttk.Combobox(parent, textvariable=self.channel, values=CHANNELS, width=5, state="readonly").grid(row=row, column=4)
        ttk.Checkbutton(parent, text="Invert", variable=self.invert).grid(row=row, column=5, padx=8)
        ttk.Spinbox(parent, from_=0, to=255, textvariable=self.black, width=4).grid(row=row, column=6)
        ttk.Spinbox(parent, from_=0, to=255, textvariable=self.white, width=4).grid(row=row, column=7, padx=(4, 8))
        ttk.Checkbutton(parent, text="Flat", variable=self.use_flat).grid(row=row, column=8)
        tk.Scale(parent, from_=0, to=100, resolution=1, orient="horizontal", variable=self.flat, length=120).grid(row=row, column=9)

    def browse(self) -> None:
        chosen = filedialog.askopenfilename(filetypes=IMAGE_TYPES)
        if chosen:
            self.path = Path(chosen)
            self.file_label.set(self.path.name)

    def clear(self) -> None:
        self.path = None
        self.file_label.set("no file")

    def slot(self) -> Slot:
        return Slot(
            path=self.path,
            channel=self.channel.get(),
            invert=self.invert.get(),
            black_point=self.black.get(),
            white_point=self.white.get(),
            flat_value=self.flat.get() if self.use_flat.get() else None,
        )


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ORM Packer")
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=12)
        frame.grid()

        headers = ("Map", "", "", "File", "Channel", "", "Black", "White", "", "Flat value")
        for col, text in enumerate(headers):
            ttk.Label(frame, text=text).grid(row=0, column=col, sticky="w")

        self.rows = [
            SlotRow(frame, "AO (R)", 1),
            SlotRow(frame, "Roughness (G)", 2),
            SlotRow(frame, "Metallic (B)", 3),
        ]

        self.format = tk.StringVar(value="TGA")
        self.output = tk.StringVar(value="")
        self.status = tk.StringVar(value="")

        bottom = ttk.Frame(frame)
        bottom.grid(row=4, column=0, columnspan=10, sticky="we", pady=(12, 0))
        ttk.Label(bottom, text="Format").grid(row=0, column=0, padx=(0, 4))
        ttk.Combobox(bottom, textvariable=self.format, values=list(FORMATS), width=5, state="readonly").grid(row=0, column=1)
        ttk.Button(bottom, text="Output…", command=self.choose_output).grid(row=0, column=2, padx=8)
        ttk.Label(bottom, textvariable=self.output, width=40).grid(row=0, column=3, sticky="w")
        ttk.Button(bottom, text="Pack", command=self.do_pack).grid(row=0, column=4, padx=(8, 0))

        ttk.Label(frame, textvariable=self.status).grid(row=5, column=0, columnspan=10, sticky="w", pady=(8, 0))

    def choose_output(self) -> None:
        fmt = self.format.get()
        ext = FORMATS[fmt]
        chosen = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(fmt, "*" + ext)])
        if chosen:
            self.output.set(chosen)

    def ask_size(self) -> tuple[int, int] | None:
        width = simpledialog.askinteger("Output size", "Width (px)", minvalue=1, initialvalue=1024, parent=self)
        if width is None:
            return None
        height = simpledialog.askinteger("Output size", "Height (px)", minvalue=1, initialvalue=width, parent=self)
        if height is None:
            return None
        return (width, height)

    def do_pack(self) -> None:
        if not self.output.get():
            messagebox.showerror("ORM Packer", "Choose an output file first.")
            return
        try:
            slots = [row.slot() for row in self.rows]
        except tk.TclError:
            messagebox.showerror("ORM Packer", "Levels must be whole numbers from 0 to 255.")
            return

        size = None
        if needs_size(*slots):
            size = self.ask_size()
            if size is None:
                return

        try:
            image = pack(*slots, size=size)
            out = resolve_output_path(Path(self.output.get()), self.format.get())
            save(image, out)
        except (OSError, ValueError) as exc:  # SizeMismatch is a ValueError
            messagebox.showerror("ORM Packer", str(exc))
            return

        self.status.set(f"Wrote {out} ({image.width}×{image.height})")


def main() -> None:
    App().mainloop()
```

`orm_packer/__main__.py`:

```python
from .gui import main

main()
```

- [ ] **Step 2: Check it imports and the pipeline suite still passes**

Run: `.venv/bin/python -c "import orm_packer.gui" && .venv/bin/pytest -q`
Expected: no import error, all tests PASS. On macOS, `import tkinter` failing means the venv's Python has no Tk; use a python.org build or `brew install python-tk`.

- [ ] **Step 3: Manual check**

Run: `.venv/bin/python -m orm_packer`

Walk through, in order, and confirm each:

1. Window opens with three rows and the bottom bar.
2. Pack with no output chosen: error box "Choose an output file first."
3. Choose output, Pack with no files: size dialog appears, cancel it, nothing written.
4. Browse AO to any PNG, Pack: file written, status line shows the path and size.
5. Set format to PNG while output ends in `.tga`, Pack: written file ends in `.png`.
6. Browse Roughness to an image of a different size, Pack: error box names both files and sizes, form unchanged.
7. Set black 200, white 100, Pack: error box mentions levels.
8. Type `abc` in a levels spinbox, Pack: "Levels must be whole numbers" error.
9. Tick Flat on Metallic, drag to 50, Pack: open the output in any viewer, blue channel is 128.

- [ ] **Step 4: Commit**

```bash
git add orm_packer/gui.py orm_packer/__main__.py
git commit -m "Add Tk window"
```

---

### Task 7: README and Windows build notes

**Files:**

- Create: `README.md`
- Modify: none. `.markdownlint-cli2.yaml` is already committed at the repo root.

**Interfaces:** none.

- [ ] **Step 1: Write the README**

`README.md`:

```markdown
# ORM Packer

Packs three greyscale PBR maps into one ORM texture: ambient occlusion in red, roughness in green, metallic in blue. Replaces:

    magick AmbientOcclusion.tga Roughness.tga Metallic.tga -set colorspace sRGB -combine ORM.tga

and adds a black fallback for missing maps, channel selection, invert, levels, a flat constant per slot, and TGA or PNG output. No colour conversion is applied; pixel values are copied as they are, so import the result into the engine as linear (sRGB off).

## Run from source

    python -m venv .venv
    .venv\Scripts\pip install -e .[dev]
    .venv\Scripts\python -m orm_packer

On macOS or Linux use `.venv/bin/` in place of `.venv\Scripts\`.

## Tests

    .venv\Scripts\pytest

The ImageMagick parity test runs only if `magick` is on the path.

## Build the Windows exe

PyInstaller cannot cross-compile, so run this on Windows:

    .venv\Scripts\pyinstaller --onefile --windowed --name orm-packer orm_packer\__main__.py

The result is `dist\orm-packer.exe`.

## Per-slot options

- Channel: Grey uses the whole image as greyscale. R, G, B, A pull one band from a colour image.
- Invert: applied after levels.
- Black and White: input levels, 0 to 255. Black must be below White.
- Flat: ignores the file and fills the channel with a 0 to 100 percentage.

All loaded inputs must be the same size. If no slot loads a file, the app asks for an output size.
```

- [ ] **Step 2: Lint**

Run: `cd ~/dev/orm-packer && markdownlint-cli2 README.md docs/**/*.md`
Expected: `0 issues`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Add README with run, test, and Windows build instructions"
```

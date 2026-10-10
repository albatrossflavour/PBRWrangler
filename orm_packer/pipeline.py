"""Image pipeline for ORM packing. Pure Pillow, no Tk."""

from __future__ import annotations

from dataclasses import dataclass
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


FORMATS: dict[str, str] = {"TGA": ".tga", "PNG": ".png"}


def resolve_output_path(path: Path, fmt: str) -> Path:
    """Force the output path's extension to match the chosen format."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}, expected one of {list(FORMATS)}")
    return path.with_suffix(FORMATS[fmt])


def save(image: Image.Image, path: Path) -> None:
    """Write the packed image. TGA is uncompressed (Pillow's default without rle=True)."""
    image.save(path)

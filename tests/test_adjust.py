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

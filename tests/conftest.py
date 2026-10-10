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

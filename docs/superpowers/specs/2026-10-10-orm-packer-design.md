# ORM Packer design

## Purpose

A Windows desktop tool for Edward that packs three greyscale PBR maps (ambient occlusion, roughness, metallic) into the red, green, and blue channels of one ORM texture. It replaces the current command:

```text
magick AmbientOcclusion.tga Roughness.tga Metallic.tga -set colorspace sRGB -combine ORM.tga
```

That command works when all three files exist and need no adjustment. The tool adds the missing pieces: a black fallback when a slot has no file, per-slot channel selection, invert, levels, a flat constant value, and a choice of output format.

## Constraints

- Windows GUI, delivered as a single exe Edward can double-click.
- Python, so Edward can read and change it.
- No colour space conversion anywhere. The existing command only relabels the data with `-set colorspace`, pixel values are copied unchanged, and the engine imports the result as linear. The tool does the same.
- Channel order is fixed: AO to R, roughness to G, metallic to B.

## Stack

- Python 3.12 or later.
- Pillow for image IO and channel work.
- Tk (tkinter, standard library) for the GUI. PySide was rejected because it roughly triples the exe size for no gain at this scale.
- pytest for the pipeline tests.
- PyInstaller, one-file windowed mode, for the exe. PyInstaller cannot cross-compile, so the build runs on a Windows machine.

## Layout

```text
orm_packer/
  __init__.py
  pipeline.py     pure functions, no Tk imports
  gui.py          Tk window, calls pipeline
  __main__.py     entry point
tests/
  test_pipeline.py
pyproject.toml
```

## User interface

One window, no menus. Three identical rows in the order AO, Roughness, Metallic. Each row holds:

- Browse button and the chosen file name (or "no file").
- Channel picker: Grey, R, G, B, A. Default Grey.
- Invert checkbox, default off.
- Levels: two spinboxes, input black point and input white point, range 0 to 255, defaults 0 and 255.
- Flat Value checkbox with a 0 to 100 slider. When ticked the file is ignored and the channel is filled with that constant.

Below the rows:

- Output format dropdown: TGA, PNG. Default TGA.
- Output file picker.
- Pack button.
- One-line status label.

## Pipeline

`pipeline.py` exposes:

```python
@dataclass
class Slot:
    path: Path | None = None
    channel: str = "Grey"        # Grey, R, G, B, A
    invert: bool = False
    black_point: int = 0
    white_point: int = 255
    flat_value: int | None = None  # 0..100, overrides path when set

def pack(ao: Slot, roughness: Slot, metallic: Slot, size: tuple[int, int] | None = None) -> Image.Image
```

Per slot, in this order:

1. If `flat_value` is set, the plane is a constant `round(flat_value * 255 / 100)`.
2. Else if `path` is None, the plane is black (0).
3. Else load the file. Grey converts the image to mode L. R, G, B, A take that band from the image, erroring if the band does not exist (A on an RGB image, R on an L image). 16-bit inputs (mode I or I;16) are scaled to 8-bit.
4. Apply levels: `out = clamp((in - black) * 255 / (white - black))`. White must be greater than black, otherwise `ValueError`.
5. Apply invert: `out = 255 - in`.

Then merge the three planes with `Image.merge("RGB", ...)` and return. No alpha channel in the output.

Size rules:

- Every loaded file must have the same dimensions. A mismatch raises `SizeMismatch` naming the files and sizes. No silent resize.
- Loaded files define the output size. Flat and black planes adopt it.
- If no slot loads a file, `size` is required. The GUI prompts for it in that case. `pack` raises `ValueError` if it is missing.

Saving is the caller's job (`image.save(path)`), with the format inferred from the extension. TGA is saved uncompressed.

## Error handling

Every failure (unreadable file, missing band, size mismatch, bad levels, missing output path, write failure) is raised as an exception from the pipeline or the save call. The GUI catches them, shows a message box with the text, and leaves the form untouched. Nothing is written until all three slots have loaded cleanly.

## Testing

`tests/test_pipeline.py`, using small generated images (4 by 4 is enough):

- Channel mapping: three distinct grey images land in R, G, B respectively.
- Black fallback: a slot with no path gives a zero plane.
- Flat value: 0, 50, and 100 give 0, 128, and 255.
- Channel picker: R, G, B, A from an RGBA source, and the error for a missing band.
- Levels: known input maps to the expected output, and white <= black raises.
- Invert.
- Levels then invert ordering.
- Size mismatch raises.
- No files and no size raises; no files with size gives a black image of that size.
- 16-bit input reduces to the expected 8-bit values.
- Round trip through TGA and PNG preserves pixel values.
- If `magick` is on the path: three generated TGAs through the existing command and through `pack` with default slots are pixel-identical. Skipped otherwise.

The GUI is tested by hand on Windows.

## Packaging

```text
pyinstaller --onefile --windowed --name orm-packer orm_packer/__main__.py
```

Run on Windows. The resulting `dist/orm-packer.exe` is the deliverable.

## Out of scope

- Preview thumbnails.
- Alpha channel in the output.
- Batch or folder processing.
- Resizing inputs to match.
- Any colour management.

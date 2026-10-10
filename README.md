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

The ImageMagick parity test runs only if `magick` is on the path. The GUI tests need a display.

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

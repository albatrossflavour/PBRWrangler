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

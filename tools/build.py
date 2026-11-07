#!/usr/bin/env python3
"""Rebuild transparent Amiya cursor assets from source_atlas.png.

Requires Pillow: python -m pip install -r requirements.txt
Pure Python writers for Windows .cur (32-bit DIB) and .ani (RIFF/ACON).
"""
from __future__ import annotations

import math
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parents[1]
ATLAS = BASE / "assets" / "source_atlas.png"
SIZES = (32, 48, 64, 96, 128)
# The Windows ANI loader rejects the five-size combination used by static CURs.
# This subset passes native loading at 32, 48, 64, 96 and 128 requested pixels.
ANI_SIZES = (32, 64, 96, 128)
# row/col indicate positions in 4x4 source atlas. Hotspots are in original cell pixels.
# Set hotspot at the custom pointer / symbol where possible.
ITEMS = [
    ("arrow",       "Normal",           0, 0, (143, 44)),
    ("help",        "Help",             0, 1, (115, 60)),
    ("appstarting", "Working",          0, 2, (73, 64)),
    ("wait",        "Busy",             0, 3, (30, 65)),
    ("crosshair",   "Precision",        1, 0, (162, 60)),
    ("ibeam",       "Text",             1, 1, (111, 62)),
    ("nwpen",       "Handwriting",      1, 2, (74, 58)),
    ("no",          "Unavailable",      1, 3, (28, 70)),
    ("sizeall",     "Move",             2, 0, (250, 133)),
    ("sizewe",      "Horizontal",       2, 1, (220, 133)),
    ("sizenesw",    "Diagonal NE-SW",   2, 2, (203, 140)),
    ("uparrow",     "Alternate",        2, 3, (20, 38)),
    ("sizens",      "Vertical",         3, 0, (245, 134)),
    ("sizenwse",    "Diagonal NW-SE",   3, 1, (205, 139)),
    ("hand",        "Link",             3, 2, (79, 70)),
    ("extra",       "Extra",            3, 3, (34, 53)),
]

# 17 registry roles from 16 distinct poses. Two newer roles share the Extra pose.
SCHEME = [
    ("Arrow", "arrow.cur"), ("Help", "help.cur"),
    ("AppStarting", "appstarting.ani"), ("Wait", "wait.ani"),
    ("Crosshair", "crosshair.cur"), ("IBeam", "ibeam.cur"),
    ("NWPen", "nwpen.cur"), ("No", "no.cur"),
    ("SizeNS", "sizens.cur"), ("SizeWE", "sizewe.cur"),
    ("SizeNWSE", "sizenwse.cur"), ("SizeNESW", "sizenesw.cur"),
    ("SizeAll", "sizeall.cur"), ("UpArrow", "uparrow.cur"),
    ("Hand", "hand.cur"), ("Pin", "pin.cur"),
    ("Person", "person.cur"),
]


def clean_alpha(img: Image.Image) -> Image.Image:
    """Remove transparent background noise without adding a white outline."""
    img = img.convert("RGBA")
    p = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = p[x, y]
            if a < 9:
                p[x, y] = (0, 0, 0, 0)
    return img


def extract(tile: Image.Image, row: int, col: int) -> tuple[Image.Image, tuple[int, int]]:
    # The 4x4 image is visually continuous. Drop a few stray pixels from
    # adjacent tiles at the right edge of cells (2,2) and (3,2).
    tile = clean_alpha(tile)
    if (row, col) in {(2, 2), (3, 2)}:
        tile.paste((0, 0, 0, 0), (335, 0, 384, 256))
    a = tile.getchannel("A")
    bbox = a.point(lambda v: 255 if v > 18 else 0).getbbox()
    if not bbox:
        raise ValueError(f"no image in tile {row},{col}")
    left = max(0, bbox[0] - 2)
    top = max(0, bbox[1] - 2)
    right = min(tile.width, bbox[2] + 2)
    bottom = min(tile.height, bbox[3] + 2)
    return tile.crop((left, top, right, bottom)), (left, top)


def position_sprite(sprite: Image.Image, hotspot: tuple[int, int], original_offset: tuple[int, int], size: int):
    """Fit a thumbnail into size x size and preserve its cursor hotspot."""
    padding = max(2, round(size * 0.045))
    factor = min((size - padding * 2) / sprite.width, (size - padding * 2) / sprite.height)
    w = max(1, round(sprite.width * factor))
    h = max(1, round(sprite.height * factor))
    scaled = sprite.resize((w, h), Image.Resampling.LANCZOS)
    x = (size - w) // 2
    y = (size - h) // 2
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    frame.alpha_composite(scaled, (x, y))
    hx = round(x + (hotspot[0] - original_offset[0]) * factor)
    hy = round(y + (hotspot[1] - original_offset[1]) * factor)
    hx = max(0, min(size - 1, hx))
    hy = max(0, min(size - 1, hy))
    return frame, (hx, hy)


def encode_cur(frame: Image.Image, hotspot: tuple[int, int]) -> bytes:
    """32-bit Windows CUR, uncompressed BMP/DIB, correct AND mask."""
    frame = frame.convert("RGBA")
    w, h = frame.size
    if w != h or not 1 <= w <= 256:
        raise ValueError("cursor frame must be square 1..256 px")
    hx, hy = hotspot
    if not 0 <= hx < w or not 0 <= hy < h:
        raise ValueError("hotspot out of bounds")
    p = frame.load()
    xor_rows = []
    and_rows = []
    rowmask_bytes = ((w + 31) // 32) * 4
    for y in range(h - 1, -1, -1):
        xor_row = bytearray()
        mask = bytearray(rowmask_bytes)
        for x in range(w):
            r, g, b, a = p[x, y]
            if a <= 8:
                r = g = b = a = 0
            xor_row.extend((b, g, r, a))
            if a == 0:
                mask[x // 8] |= 1 << (7 - (x % 8))
        xor_rows.append(bytes(xor_row))
        and_rows.append(bytes(mask))
    xor_data = b"".join(xor_rows)
    mask_data = b"".join(and_rows)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(xor_data), 0, 0, 0, 0)
    dib += xor_data + mask_data
    icon_dir = struct.pack("<HHH", 0, 2, 1)
    icon_entry = struct.pack("<BBBBHHII", 0 if w == 256 else w, 0 if h == 256 else h,
                             0, 0, hx, hy, len(dib), 6 + 16)
    return icon_dir + icon_entry + dib


def chunk(fourcc: bytes, data: bytes) -> bytes:
    assert len(fourcc) == 4
    return fourcc + struct.pack("<I", len(data)) + data + (b"\0" if len(data) & 1 else b"")


def encode_multi_cur(images: list[tuple[Image.Image, tuple[int, int]]]) -> bytes:
    """Combine individually encoded DIBs into a multi-resolution CUR."""
    entries, payloads = [], []
    offset = 6 + 16 * len(images)
    for image, hotspot in images:
        single = encode_cur(image, hotspot)
        w, h, colors, reserved, hx, hy, length, start = struct.unpack_from("<BBBBHHII", single, 6)
        payload = single[start:start + length]
        entries.append(struct.pack("<BBBBHHII", w, h, colors, reserved, hx, hy, length, offset))
        payloads.append(payload)
        offset += length
    return struct.pack("<HHH", 0, 2, len(images)) + b"".join(entries) + b"".join(payloads)


def encode_ani(frames: list[bytes], jiffies: int = 6) -> bytes:
    """RIFF/ACON cursor with full .cur frames and per-frame timing."""
    n = len(frames)
    # CBSize(36), nFrames, nSteps, width/height(0), depth/planes(0), jifRate, flags(AF_ICON)
    header = struct.pack("<9I", 36, n, n, 0, 0, 0, 0, jiffies, 1)
    contents = chunk(b"anih", header)
    contents += chunk(b"rate", struct.pack("<" + "I" * n, *([jiffies] * n)))
    contents += chunk(b"LIST", b"fram" + b"".join(chunk(b"icon", f) for f in frames))
    body = b"ACON" + contents
    return b"RIFF" + struct.pack("<I", len(body)) + body


def animate_frame(frame: Image.Image, index: int, kind: str) -> Image.Image:
    """Subtle vertical bounce/pulse; hotspot remains fixed in the .cur header."""
    n = 8
    phase = 2 * math.pi * index / n
    dy = round((1.5 if kind == "appstarting" else 0.9) * math.sin(phase))
    # Subpixel scale would shift the hotspot; a 1px bounce is unobtrusive.
    output = Image.new("RGBA", frame.size)
    output.alpha_composite(frame, (0, dy))
    return output


def build_preview(sprites: list[tuple[str, Image.Image]], out: Path):
    cell_w, cell_h = 244, 248
    canvas = Image.new("RGB", (4 * cell_w + 32, 4 * cell_h + 38), (252, 252, 253))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for i, (name, sprite) in enumerate(sprites):
        col, row = i % 4, i // 4
        cx, cy = 16 + col * cell_w, 15 + row * cell_h
        draw.rounded_rectangle((cx + 3, cy + 3, cx + cell_w - 9, cy + cell_h - 6), 14,
                               fill=(246, 248, 251), outline=(224, 227, 233), width=2)
        img = sprite.copy()
        img.thumbnail((200, 199), Image.Resampling.LANCZOS)
        rgba_bg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        rgba_bg.alpha_composite(img, (cx + (cell_w - img.width)//2 - 4, cy + 7))
        canvas.paste(rgba_bg, (0, 0), rgba_bg)
        label = ITEMS[i][1]
        bbox = draw.textbbox((0, 0), label, font=font)
        draw.text((cx + (cell_w - (bbox[2]-bbox[0]))//2 - 3, cy + 211), label, font=font,
                  fill=(39, 60, 78))
    canvas.save(out)


def main():
    atlas = Image.open(ATLAS).convert("RGBA")
    if atlas.size != (1536, 1024):
        raise ValueError(f"expected 1536x1024 source atlas; got {atlas.size}")
    (BASE / "png").mkdir(exist_ok=True)
    extracted = {}
    sprites = []
    for name, label, row, col, hotspot in ITEMS:
        tile = atlas.crop((col*384, row*256, (col+1)*384, (row+1)*256))
        sprite, offset = extract(tile, row, col)
        sprite.save(BASE / "png" / f"{name}.png")
        extracted[name] = (sprite, offset, hotspot)
        sprites.append((name, sprite))
    # Two extra registry states reuse the last image.
    for other in ("pin", "person"):
        extracted[other] = extracted["extra"]
        extracted["extra"][0].save(BASE / "png" / f"{other}.png")
    build_preview(sprites, BASE / "preview.png")

    destination = BASE / "cursors" / "multi"
    destination.mkdir(parents=True, exist_ok=True)
    for name, (sprite, offset, hotspot) in extracted.items():
        images = [position_sprite(sprite, hotspot, offset, size) for size in SIZES]
        (destination / f"{name}.cur").write_bytes(encode_multi_cur(images))
        if name in ("appstarting", "wait"):
            animation_images = [images[SIZES.index(size)] for size in ANI_SIZES]
            frames = [encode_multi_cur([(animate_frame(frame, i, name), hs)
                                        for frame, hs in animation_images]) for i in range(8)]
            (destination / f"{name}.ani").write_bytes(encode_ani(frames))
    print("Built:", len(ITEMS), "distinct poses, 17 cursor roles, 5 resolutions, 2 ANI animations")
    print("Preview:", BASE / "preview.png")


if __name__ == "__main__":
    main()

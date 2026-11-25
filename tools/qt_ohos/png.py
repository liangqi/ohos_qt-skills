"""Minimal PNG reader + screenshot diff, dependency-free.

Used by `smoke-interact`: the gate needs a numeric answer to "did the screen
actually change after the tap, or is it a white rectangle?" and the tool may run
on a host with no Pillow. Only the subset the device screenshots use is
implemented: bit depth 8 (plus 1/2/4/8 for palette), colour types 0/2/3/4/6,
non-interlaced.

    from qt_ohos.png import read_png, diff_ratio, distinct_colors
    a, b = read_png("shot1.png"), read_png("shot2.png")
    diff_ratio(a, b)        # 0.0 == identical, 1.0 == every pixel changed
    distinct_colors(b)      # ~1 on a blank window
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


@dataclass
class PNGImage:
    width: int
    height: int
    channels: int
    pixels: bytes                      # row-major, 8-bit samples, unfiltered

    def rgb(self) -> bytes:
        if self.channels == 3:
            return self.pixels
        out = bytearray(self.width * self.height * 3)
        src = self.pixels
        if self.channels == 4:         # drop alpha (screenshots are opaque)
            for i in range(self.width * self.height):
                out[i * 3:i * 3 + 3] = src[i * 4:i * 4 + 3]
        elif self.channels == 2:       # gray + alpha
            for i in range(self.width * self.height):
                gray = src[i * 2]
                out[i * 3:i * 3 + 3] = bytes((gray, gray, gray))
        else:                          # gray
            for i in range(self.width * self.height):
                gray = src[i]
                out[i * 3:i * 3 + 3] = bytes((gray, gray, gray))
        return bytes(out)


def read_png(path) -> PNGImage:
    return read_png_bytes(Path(path).read_bytes())


def read_png_bytes(data: bytes) -> PNGImage:
    if not data.startswith(_PNG_MAGIC):
        raise ValueError("not a PNG file")
    pos = len(_PNG_MAGIC)
    width = height = depth = color_type = interlace = 0
    palette: List[Tuple[int, int, int]] = []
    idat = bytearray()
    while pos + 8 <= len(data):
        length, ctype = struct.unpack_from(">I4s", data, pos)
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            (width, height, depth, color_type, _comp, _filt,
             interlace) = struct.unpack(">IIBBBBB", body[:13])
        elif ctype == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body) - 2, 3)]
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
    if not width or not height:
        raise ValueError("PNG has no IHDR")
    if interlace:
        raise ValueError("interlaced PNG is not supported")
    if color_type not in _CHANNELS:
        raise ValueError("unsupported PNG colour type %d" % color_type)
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise ValueError("PNG zlib stream is corrupt (%s)" % exc)

    if depth == 8:
        channels = _CHANNELS[color_type]
        stride = width * channels
        rows = _unfilter(raw, stride, height, channels)
        pixels = b"".join(rows)
        if color_type == 3:
            pixels = _expand_palette(pixels, palette)
            channels = 3
    elif depth in (1, 2, 4) and color_type in (0, 3):
        channels = 1
        stride = (width * depth + 7) // 8
        rows = _unfilter(raw, stride, height, 1)
        pixels = _expand_subbyte(b"".join(rows), width, height, depth)
        if color_type == 3:
            pixels = _expand_palette(pixels, palette)
            channels = 3
    else:
        raise ValueError("unsupported PNG bit depth %d" % depth)
    return PNGImage(width=width, height=height, channels=channels,
                    pixels=pixels)


def _unfilter(raw: bytes, stride: int, height: int, bpp: int) -> List[bytes]:
    rows: List[bytes] = []
    prev = bytearray(stride)
    cursor = 0
    for _ in range(height):
        if cursor >= len(raw):
            break
        ftype = raw[cursor]
        line = bytearray(raw[cursor + 1:cursor + 1 + stride])
        cursor += 1 + stride
        if len(line) < stride:
            line += bytes(stride - len(line))
        if ftype == 1:                 # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:               # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:               # Average
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:               # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise ValueError("unknown PNG filter %d" % ftype)
        rows.append(bytes(line))
        prev = line
    return rows


def _expand_palette(indexes: bytes, palette: List[Tuple[int, int, int]]) -> bytes:
    out = bytearray(len(indexes) * 3)
    last = (0, 0, 0)
    for i, index in enumerate(indexes):
        if index < len(palette):
            last = palette[index]
        out[i * 3:i * 3 + 3] = bytes(last)
    return bytes(out)


def _expand_subbyte(data: bytes, width: int, height: int, depth: int) -> bytes:
    per_byte = 8 // depth
    mask = (1 << depth) - 1
    scale = 255 // mask
    out = bytearray(width * height)
    for y in range(height):
        row = data[y * ((width + per_byte - 1) // per_byte):]
        for x in range(width):
            byte = row[x // per_byte] if x // per_byte < len(row) else 0
            shift = 8 - depth * (x % per_byte + 1)
            out[y * width + x] = ((byte >> shift) & mask) * scale
    return bytes(out)


def distinct_colors(image: PNGImage, limit: int = 64) -> int:
    """Distinct colours, capped: 1 means a solid rectangle."""
    rgb = image.rgb()
    seen = set()
    step = max(1, (len(rgb) // 3) // 20000)     # sample at most ~20k pixels
    for i in range(0, len(rgb) - 2, 3 * step):
        seen.add(rgb[i:i + 3])
        if len(seen) >= limit:
            return limit
    return len(seen)


def diff_ratio(a: PNGImage, b: PNGImage, tolerance: int = 8) -> float:
    """Fraction of pixels whose RGB differs by more than `tolerance`."""
    if (a.width, a.height) != (b.width, b.height):
        return 1.0
    left, right = a.rgb(), b.rgb()
    total = a.width * a.height
    changed = 0
    for i in range(0, total * 3, 3):
        if (abs(left[i] - right[i]) > tolerance
                or abs(left[i + 1] - right[i + 1]) > tolerance
                or abs(left[i + 2] - right[i + 2]) > tolerance):
            changed += 1
    return changed / float(total or 1)

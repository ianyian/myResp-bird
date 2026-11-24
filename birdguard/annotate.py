"""Draw detection boxes / status onto frames and encode JPEGs."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .detectors.base import Detection


_fonts: dict[int, ImageFont.ImageFont] = {}


def _font(size: int):
    if size not in _fonts:
        try:
            _fonts[size] = ImageFont.load_default(size=size)  # Pillow >= 10.1
        except TypeError:
            _fonts[size] = ImageFont.load_default()
    return _fonts[size]


def _label(d: ImageDraw.ImageDraw, xy, text: str, font, fg, bg) -> None:
    x0, y0, x1, y1 = d.textbbox(xy, text, font=font)
    pad = max(2, (y1 - y0) // 4)
    d.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=bg)
    d.text(xy, text, fill=fg, font=font)


def annotate(
    frame: np.ndarray,
    detections: list[Detection],
    targets: set[str],
    threshold: float,
    status: str = "",
) -> Image.Image:
    img = Image.fromarray(frame[:, :, :3])
    d = ImageDraw.Draw(img)
    w, h = img.size
    line = max(2, w // 320)
    font = _font(max(12, w // 45))
    for det in detections:
        is_target = det.label in targets and det.score >= threshold
        color = (255, 40, 40) if is_target else (255, 210, 0)
        x0, y0, x1, y1 = det.bbox
        box = [x0 * w, y0 * h, x1 * w, y1 * h]
        d.rectangle(box, outline=color, width=line)
        size = font.size if hasattr(font, "size") else 12
        _label(d, (box[0] + 4, max(4, box[1] - size - 6)), f"{det.label} {det.score:.0%}",
               font, (0, 0, 0), color)
    if status:
        _label(d, (8, 8), status, font, (255, 255, 255), (0, 0, 0))
    return img


def to_jpeg(img: Image.Image, width: int | None = None, quality: int = 80) -> bytes:
    if width and img.width > width:
        img = img.resize((width, int(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

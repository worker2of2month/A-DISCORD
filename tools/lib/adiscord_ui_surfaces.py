"""Shared deterministic surfaces for the remaining A-Discord interface skin."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps


Color = tuple[int, int, int, int]


@dataclass(frozen=True)
class UiPalette:
    deep: Color
    panel: Color
    edge: Color
    edge_light: Color
    accent: Color
    accent_light: Color


PALETTES = {
    "technology": UiPalette(
        (7, 11, 12, 255),
        (17, 24, 25, 255),
        (55, 69, 70, 255),
        (104, 124, 123, 255),
        (48, 126, 126, 255),
        (74, 166, 162, 255),
    ),
    "logistics": UiPalette(
        (10, 10, 8, 255),
        (25, 22, 17, 255),
        (75, 64, 47, 255),
        (132, 112, 75, 255),
        (153, 101, 43, 255),
        (197, 142, 67, 255),
    ),
    "deployment": UiPalette(
        (8, 10, 7, 255),
        (21, 25, 17, 255),
        (64, 70, 49, 255),
        (112, 121, 79, 255),
        (91, 111, 57, 255),
        (132, 151, 78, 255),
    ),
    "intelligence": UiPalette(
        (7, 9, 12, 255),
        (17, 21, 27, 255),
        (54, 65, 78, 255),
        (98, 116, 135, 255),
        (58, 91, 121, 255),
        (84, 128, 164, 255),
    ),
}


def load_surface_source(
    path: Path,
    minimum_size: tuple[int, int] = (1024, 1024),
) -> Image.Image:
    if not path.is_file():
        raise RuntimeError(f"missing UI surface source: {path}")
    with Image.open(path) as source_image:
        source = source_image.convert("RGBA")
    if source.width < minimum_size[0] or source.height < minimum_size[1]:
        raise RuntimeError(
            f"UI surface source must be at least {minimum_size}, got {source.size}: {path}"
        )
    return source


def metal_surface(
    source: Image.Image,
    size: tuple[int, int],
    palette: UiPalette,
    brightness: float = 0.82,
    centering: tuple[float, float] = (0.5, 0.5),
) -> Image.Image:
    fitted = ImageOps.fit(
        source.convert("RGBA"),
        size,
        method=Image.Resampling.LANCZOS,
        centering=centering,
    )
    fitted = ImageEnhance.Contrast(fitted).enhance(0.92)
    fitted = ImageEnhance.Brightness(fitted).enhance(brightness)
    luminance = ImageOps.grayscale(fitted.convert("RGB"))
    tint = ImageOps.colorize(
        luminance,
        black=palette.deep[:3],
        white=palette.edge_light[:3],
    ).convert("RGBA")
    output = Image.blend(fitted, tint, 0.62)
    output.putalpha(255)
    return output


def surface(image: Image.Image, box: tuple[int, int, int, int], palette: UiPalette) -> None:
    """Lay down the neutral working surface inside a semantic region."""
    ImageDraw.Draw(image, "RGBA").rectangle(box, fill=palette.panel)


def outer_frame(image: Image.Image, box: tuple[int, int, int, int], palette: UiPalette) -> None:
    """Draw a complete frame only for a true outer window."""
    draw = ImageDraw.Draw(image, "RGBA")
    left, top, right, bottom = box
    draw.rectangle(box, outline=palette.deep, width=2)
    draw.rectangle((left + 2, top + 2, right - 2, bottom - 2), outline=palette.edge)
    draw.line((left + 4, top + 3, right - 4, top + 3), fill=palette.edge_light)
    draw.line((left + 4, bottom - 3, right - 4, bottom - 3), fill=palette.accent)


def recessed_well(image: Image.Image, box: tuple[int, int, int, int], palette: UiPalette) -> None:
    """Draw a dark, bounded recess for icons, counters, or text fields."""
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle(box, fill=palette.deep, outline=palette.edge)
    left, top, right, _ = box
    draw.line((left + 1, top + 1, right - 1, top + 1), fill=palette.panel)


def raised_field(image: Image.Image, box: tuple[int, int, int, int], palette: UiPalette) -> None:
    """Draw a lighter field for readable active content."""
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle(box, fill=palette.panel, outline=palette.edge)
    left, top, right, _ = box
    draw.line((left + 1, top + 1, right - 1, top + 1), fill=palette.edge_light)


def status_band(image: Image.Image, box: tuple[int, int, int, int], color: Color) -> None:
    """Fill a narrow semantic status region without affecting its surround."""
    ImageDraw.Draw(image, "RGBA").rectangle(box, fill=color)


def partial_rails(image: Image.Image, box: tuple[int, int, int, int], palette: UiPalette) -> None:
    """Add open-ended rails for nested structure without a repeated frame."""
    draw = ImageDraw.Draw(image, "RGBA")
    left, top, right, bottom = box
    inset = 4
    draw.line((left + inset, top, right - inset, top), fill=palette.edge)
    draw.line((left + inset, bottom, right - inset, bottom), fill=palette.edge_light)


def horizontal_state_strip(
    image: Image.Image,
    box: tuple[int, int, int, int],
    palette: UiPalette,
    state_colors: tuple[Color, ...],
) -> None:
    """Divide a field into horizontal state bands using supplied state colors."""
    left, top, right, bottom = box
    if not state_colors:
        raise ValueError("state_colors must not be empty")
    draw = ImageDraw.Draw(image, "RGBA")
    width = right - left + 1
    for index, color in enumerate(state_colors):
        start = left + width * index // len(state_colors)
        end = left + width * (index + 1) // len(state_colors) - 1
        draw.rectangle((start, top, end, bottom), fill=color)
    draw.rectangle(box, outline=palette.edge)


def framed_panel(
    source: Image.Image,
    size: tuple[int, int],
    palette: UiPalette,
    brightness: float = 0.82,
) -> Image.Image:
    output = metal_surface(source, size, palette, brightness)
    draw = ImageDraw.Draw(output, "RGBA")
    right = size[0] - 1
    bottom = size[1] - 1
    draw.rectangle((0, 0, right, bottom), outline=palette.deep, width=4)
    draw.rectangle((4, 4, right - 4, bottom - 4), outline=palette.edge, width=2)
    draw.line((8, 7, right - 8, 7), fill=palette.edge_light, width=1)
    draw.line((8, bottom - 7, right - 8, bottom - 7), fill=palette.accent, width=1)
    for x, y in ((10, 10), (right - 10, 10), (10, bottom - 10), (right - 10, bottom - 10)):
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=palette.deep, outline=palette.edge)
    return output


def button_strip(
    source: Image.Image,
    frame_size: tuple[int, int],
    palette: UiPalette,
) -> Image.Image:
    width, height = frame_size
    output = Image.new("RGBA", (width * 3, height), (0, 0, 0, 0))
    for state, brightness in enumerate((0.78, 0.98, 0.56)):
        frame = metal_surface(
            source,
            frame_size,
            palette,
            brightness,
            (0.32 + state * 0.18, 0.5),
        )
        if state == 2:
            frame = ImageOps.grayscale(frame.convert("RGB")).convert("RGBA")
            frame.putalpha(255)
        draw = ImageDraw.Draw(frame, "RGBA")
        edge = palette.accent_light if state == 1 else palette.edge
        draw.rectangle((0, 0, width - 1, height - 1), outline=palette.deep, width=3)
        draw.rectangle((3, 3, width - 4, height - 4), outline=edge, width=1)
        draw.line((6, 5, width - 7, 5), fill=palette.edge_light, width=1)
        draw.line((6, height - 6, width - 7, height - 6), fill=palette.accent, width=1)
        output.alpha_composite(frame, (state * width, 0))
    return output


def dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.convert("RGBA").save(stream, format="DDS")
    return stream.getvalue()


def replace_counted(
    text: str,
    old: str,
    new: str,
    expected: int,
) -> str:
    old_token = f'"{old}"'
    actual = text.count(old_token)
    if actual != expected:
        raise ValueError(f"{old}: expected {expected}, found {actual}")
    return text.replace(old_token, f'"{new}"')


def apply_or_check(
    outputs: dict[Path, bytes],
    apply: bool,
    label: str,
) -> int:
    stale = [
        path
        for path, data in outputs.items()
        if not path.is_file() or path.read_bytes() != data
    ]
    if not apply:
        if stale:
            for path in stale:
                print(f"STALE: {path}")
            return 1
        print(f"{label} outputs are current.")
        return 0

    for path, data in outputs.items():
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"WROTE: {path}")
    return 0

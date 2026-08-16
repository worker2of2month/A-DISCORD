#!/usr/bin/env python3
"""Build A-Discord weapon and night-combat technology icons deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tools.lib.paths import repository_root


ROOT = repository_root()
MANIFEST = ROOT / "tools" / "data" / "adiscord_technology_weapon_icons.json"
SOURCE_DIR = ROOT / "tools" / "assets" / "source" / "technology_weapons"
OUTPUT_DIR = ROOT / "gfx" / "interface" / "technologies"
CONTACT_SHEET = (
    ROOT
    / "docs"
    / "superpowers"
    / "reports"
    / "2026-08-15-adiscord-technology-icon-contact-sheet.png"
)

WIDE_SIZE = (176, 72)
COMPACT_SIZE = (72, 72)
WIDE_MARGIN = (5, 4)
COMPACT_MARGIN = (4, 4)

DEPRECATED_CONNECTOR_OUTPUTS = tuple(
    Path("gfx") / "interface" / "techtree" / filename
    for filename in (
        "techtree_line_vertical.dds",
        "techtree_line_horisontal.dds",
        "techline_center_all_researched.dds",
        "techline_center_bottom_left_researched.dds",
        "techline_center_bottom_right_researched.dds",
        "techline_center_down_researched.dds",
        "techline_center_left_researched.dds",
        "techline_center_right_researched.dds",
        "techline_center_top_left_researched.dds",
        "techline_center_top_right_researched.dds",
        "techline_center_up_researched.dds",
    )
)


@dataclass(frozen=True)
class IconSpec:
    key: str
    source: str
    source_sha256: str
    tier: int
    kind: str
    output: str
    crop: tuple[int, int, int, int] | None = None
    source_size: tuple[int, int] = (1893, 831)
    family: str = "service"
    runtime_master: bool = False


def load_manifest(path: Path = MANIFEST) -> tuple[IconSpec, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    icons: list[IconSpec] = []
    for entry in payload["icons"]:
        crop = entry.get("crop")
        icons.append(
            IconSpec(
                key=entry["key"],
                source=entry["source"],
                source_sha256=entry["source_sha256"],
                tier=int(entry["tier"]),
                kind=entry["kind"],
                output=entry["output"],
                crop=tuple(crop) if crop is not None else None,
                source_size=tuple(entry.get("source_size", (1893, 831))),
                family=entry.get("family", "night" if entry["kind"] == "compact" else "service"),
                runtime_master=bool(entry.get("runtime_master", False)),
            )
        )
    return tuple(icons)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("source image has no visible alpha content")
    return bbox


def fit_rgba(
    image: Image.Image,
    size: tuple[int, int],
    margin: tuple[int, int],
) -> Image.Image:
    rgba = image.convert("RGBA")
    visible = rgba.crop(alpha_bbox(rgba))
    limit = (size[0] - margin[0] * 2, size[1] - margin[1] * 2)
    visible.thumbnail(limit, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(
        visible,
        ((size[0] - visible.width) // 2, (size[1] - visible.height) // 2),
    )
    return canvas


def _source_image(spec: IconSpec, root: Path) -> Image.Image:
    path = root / "tools" / "assets" / "source" / "technology_weapons" / spec.source
    if not path.is_file():
        raise RuntimeError(f"missing technology icon source: {path.relative_to(root)}")
    data = path.read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != spec.source_sha256:
        raise RuntimeError(
            f"technology icon source hash differs for {path.relative_to(root)}: "
            f"expected {spec.source_sha256}, got {actual_hash}"
        )
    with Image.open(BytesIO(data)) as source:
        image = source.convert("RGBA")
    if image.size != spec.source_size:
        raise RuntimeError(
            f"technology icon source must be {spec.source_size[0]}x{spec.source_size[1]}, "
            f"got {image.size}: {path.relative_to(root)}"
        )
    if spec.crop is not None:
        left, top, right, bottom = spec.crop
        if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
            raise RuntimeError(f"invalid crop {spec.crop} for {path.relative_to(root)}")
        image = image.crop(spec.crop)
    return image


def render_icon(spec: IconSpec, root: Path = ROOT) -> Image.Image:
    source = _source_image(spec, root)
    if spec.runtime_master:
        expected_size = WIDE_SIZE if spec.kind == "wide" else COMPACT_SIZE
        if source.size != expected_size:
            raise RuntimeError(
                f"runtime master for {spec.key} must be {expected_size[0]}x{expected_size[1]}, got {source.size}"
            )
        return source
    if spec.kind == "wide":
        return fit_rgba(source, WIDE_SIZE, WIDE_MARGIN)
    if spec.kind == "compact":
        return fit_rgba(source, COMPACT_SIZE, COMPACT_MARGIN)
    raise RuntimeError(f"unknown technology icon kind {spec.kind!r} for {spec.key}")


def _dds_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="DDS", pixel_format="DXT5")
    return stream.getvalue()


def _png_bytes(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def _contact_sheet(rendered: tuple[tuple[IconSpec, Image.Image], ...]) -> Image.Image:
    service = [(spec, icon) for spec, icon in rendered if spec.family == "service"]
    squad = [(spec, icon) for spec, icon in rendered if spec.family == "squad"]
    compact = [(spec, icon) for spec, icon in rendered if spec.kind == "compact"]
    cell_width = 212
    sheet = Image.new("RGBA", (cell_width * max(len(service), len(squad)), 390), (14, 16, 17, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for row, entries, prefix in ((0, service, "W"), (1, squad, "S")):
        y = 16 + row * 132
        for index, (spec, icon) in enumerate(entries):
            x = index * cell_width + (cell_width - icon.width) // 2
            sheet.alpha_composite(icon, (x, y))
            draw.text(
                (index * cell_width + 8, y + 92),
                f"{prefix}{spec.tier} {spec.key}",
                fill=(222, 220, 205, 255),
                font=font,
            )

    compact_total = len(compact) * 102
    compact_x = max(12, (sheet.width - compact_total) // 2)
    for index, (spec, icon) in enumerate(compact):
        x = compact_x + index * 102
        sheet.alpha_composite(icon, (x + 15, 292))
        prefix = "A" if spec.family == "personal_antitank" else "N"
        draw.text((x, 368), f"{prefix}{spec.tier} {spec.key[:11]}", fill=(172, 204, 174, 255), font=font)
    return sheet


def render_outputs(root: Path = ROOT) -> dict[Path, bytes]:
    manifest = root / "tools" / "data" / "adiscord_technology_weapon_icons.json"
    rendered = tuple((spec, render_icon(spec, root)) for spec in load_manifest(manifest))
    outputs: dict[Path, bytes] = {}
    for spec, icon in rendered:
        relative = Path("gfx") / "interface" / "technologies" / spec.output
        if spec.runtime_master:
            outputs[relative] = (root / "tools" / "assets" / "source" / "technology_weapons" / spec.source).read_bytes()
        else:
            outputs[relative] = _dds_bytes(icon)
    outputs[CONTACT_SHEET.relative_to(ROOT)] = _png_bytes(_contact_sheet(rendered))
    return outputs


def validate(outputs: dict[Path, bytes], root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for relative in DEPRECATED_CONNECTOR_OUTPUTS:
        if (root / relative).exists():
            issues.append(
                f"obsolete generated connector overrides vanilla: {relative.as_posix()}"
            )
    for relative, expected in outputs.items():
        path = root / relative
        if not path.is_file():
            issues.append(f"missing generated technology icon: {relative.as_posix()}")
        elif path.read_bytes() != expected:
            issues.append(f"generated technology icon differs: {relative.as_posix()}")
    return issues


def apply(outputs: dict[Path, bytes], root: Path = ROOT) -> None:
    for relative in DEPRECATED_CONNECTOR_OUTPUTS:
        path = root / relative
        if path.is_file():
            path.unlink()
    for relative, data in outputs.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(data)
        temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="compare outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write generated outputs")
    args = parser.parse_args()

    try:
        outputs = render_outputs(ROOT)
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.apply:
        apply(outputs, ROOT)
    issues = validate(outputs, ROOT)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    dds_count = sum(path.suffix == ".dds" for path in outputs)
    print(f"A-Discord technology UI assets are current ({dds_count} DDS files and one contact sheet).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

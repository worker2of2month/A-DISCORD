"""Sprite contracts and deterministic previews for A-Discord UI assets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class SpriteContract:
    source_name: str
    target_name: str
    filename: str
    kind: Literal["spriteType", "corneredTileSpriteType", "frameAnimatedSpriteType"]
    total_size: tuple[int, int]
    frames: int = 1
    border_size: tuple[int, int] | None = None
    effect_file: str | None = None
    always_transparent: bool = False
    tiling_center: bool = False
    extra_lines: tuple[str, ...] = ()


def validate_contract_image(contract: SpriteContract, image: Image.Image) -> None:
    if image.mode != "RGBA":
        raise ValueError(f"{contract.target_name}: expected RGBA, found {image.mode}")
    if image.size != contract.total_size:
        expected = f"{contract.total_size[0]}x{contract.total_size[1]}"
        actual = f"{image.width}x{image.height}"
        raise ValueError(f"{contract.target_name}: expected {expected}, found {actual}")
    if contract.frames < 1:
        raise ValueError(f"{contract.target_name}: frames must be positive")
    if contract.total_size[0] % contract.frames:
        raise ValueError(f"{contract.target_name}: width is not divisible by frames")


def render_gfx_entry(contract: SpriteContract, texture_file: str) -> str:
    lines = [
        f"    {contract.kind} = {{",
        f'        name = "{contract.target_name}"',
        f"        size = {{ x = {contract.total_size[0]} y = {contract.total_size[1]} }}",
        f'        textureFile = "{texture_file}"',
    ]
    if contract.frames != 1:
        lines.append(f"        noOfFrames = {contract.frames}")
    if contract.border_size is not None:
        lines.append(
            f"        borderSize = {{ x = {contract.border_size[0]} y = {contract.border_size[1]} }}"
        )
    if contract.effect_file is not None:
        lines.append(f'        effectFile = "{contract.effect_file}"')
    if contract.always_transparent:
        lines.append("        alwaysTransparent = yes")
    if contract.tiling_center:
        lines.append("        tilingCenter = yes")
    lines.extend(f"        {line}" for line in contract.extra_lines)
    lines.append("    }")
    return "\n".join(lines) + "\n"


def contact_sheet(
    entries: Sequence[tuple[str, Image.Image]],
    width: int,
) -> Image.Image:
    padding = 8
    label_height = 12
    gap = 4
    output_width = max(width, *(image.width + padding * 2 for _, image in entries))
    font = ImageFont.load_default()
    height = padding
    for _, image in entries:
        height += label_height + gap + image.height + padding

    output = Image.new("RGBA", (output_width, height), (30, 34, 38, 255))
    draw = ImageDraw.Draw(output)
    y = padding
    for label, image in entries:
        draw.text((padding, y), label, fill=(214, 220, 222, 255), font=font)
        y += label_height + gap
        output.alpha_composite(image.convert("RGBA"), (padding, y))
        y += image.height + padding
    return output

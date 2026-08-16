"""Build the generated A-Discord party texticons from transparent masters."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AssetSpec:
    key: str
    asset_class: str
    source_kind: str
    source: Path | None
    output: Path
    sprite: str
    runtime_size: tuple[int, int]
    ideology: str | None = None
    archetype: str | None = None


@dataclass(frozen=True)
class ProtectedSpec:
    key: str
    output: Path
    sprite: str
    sha256: str
    runtime_size: tuple[int, int]


@dataclass(frozen=True)
class AssignmentSpec:
    party_key: str
    sprite: str


@dataclass(frozen=True)
class Catalog:
    assets: tuple[AssetSpec, ...]
    protected: tuple[ProtectedSpec, ...]
    assignments: tuple[AssignmentSpec, ...]


CATALOG_PATH = Path("tools/data/adiscord_party_texticons.json")
GENERATED_CLASSES = {"existing", "country", "generic", "fallback"}
SOURCE_KINDS = {"master", "procedural_white_flag"}
LOWER_SHA256 = re.compile(r"[0-9a-f]{64}")


def _require_fields(record: object, fields: set[str], context: str) -> dict[str, object]:
    if not isinstance(record, dict):
        raise RuntimeError(f"{context} must be an object")
    missing = sorted(fields - record.keys())
    if missing:
        raise RuntimeError(f"{context} missing fields: {', '.join(missing)}")
    return record


def _relative_path(value: object, context: str) -> Path:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{context} must be a non-empty path string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"{context} must be project-relative: {value}")
    return path


def _runtime_size(value: object, context: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2 or any(type(item) is not int for item in value):
        raise RuntimeError(f"{context} must be a two-integer list")
    return value[0], value[1]


def _unique(values: list[str], context: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise RuntimeError(f"duplicate {context}: {', '.join(duplicates)}")


def load_catalog(root: Path = ROOT) -> Catalog:
    path = root / CATALOG_PATH
    if not path.is_file():
        raise RuntimeError(f"party texticon catalog is missing: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid party texticon catalog: {error}") from error
    top = _require_fields(
        raw,
        {"schema", "generated_assets", "protected_legacy", "country_assignments"},
        "catalog",
    )
    if top["schema"] != 1:
        raise RuntimeError(f"unsupported party texticon catalog schema: {top['schema']!r}")
    if not all(isinstance(top[field], list) for field in ("generated_assets", "protected_legacy", "country_assignments")):
        raise RuntimeError("catalog collections must be lists")

    assets: list[AssetSpec] = []
    for index, candidate in enumerate(top["generated_assets"]):
        context = f"generated_assets[{index}]"
        record = _require_fields(
            candidate,
            {"key", "class", "source_kind", "output", "sprite", "runtime_size"},
            context,
        )
        key = record["key"]
        asset_class = record["class"]
        source_kind = record["source_kind"]
        sprite = record["sprite"]
        if not all(isinstance(value, str) and value for value in (key, asset_class, source_kind, sprite)):
            raise RuntimeError(f"{context} string fields must be non-empty")
        if asset_class not in GENERATED_CLASSES:
            raise RuntimeError(f"{context} has unknown class: {asset_class}")
        if source_kind not in SOURCE_KINDS:
            raise RuntimeError(f"{context} has unknown source kind: {source_kind}")
        size = _runtime_size(record["runtime_size"], f"{context}.runtime_size")
        if size != (32, 32):
            raise RuntimeError(f"{context} generated runtime size must be [32, 32]")
        source_value = record.get("source")
        source = None
        if source_kind == "master":
            source = _relative_path(source_value, f"{context}.source")
            if not (root / source).is_file():
                raise RuntimeError(f"{context} master is missing: {source.as_posix()}")
        elif source_value is not None:
            raise RuntimeError(f"{context} procedural asset must not declare a source")
        if source_kind == "procedural_white_flag" and asset_class != "fallback":
            raise RuntimeError(f"{context} procedural white flag must be a fallback")
        ideology = record.get("ideology")
        archetype = record.get("archetype")
        if asset_class == "generic":
            if not all(isinstance(value, str) and value for value in (ideology, archetype)):
                raise RuntimeError(f"{context} generic asset requires ideology and archetype")
        elif ideology is not None or archetype is not None:
            raise RuntimeError(f"{context} non-generic asset must not declare ideology/archetype")
        output = _relative_path(record["output"], f"{context}.output")
        nod_values = (key, source.as_posix() if source is not None else "", output.as_posix(), sprite)
        if any("NOD" in value.upper() for value in nod_values):
            raise RuntimeError(f"{context} must not create a NOD-specific generated record")
        assets.append(
            AssetSpec(
                key=key,
                asset_class=asset_class,
                source_kind=source_kind,
                source=source,
                output=output,
                sprite=sprite,
                runtime_size=size,
                ideology=ideology,
                archetype=archetype,
            )
        )

    protected: list[ProtectedSpec] = []
    for index, candidate in enumerate(top["protected_legacy"]):
        context = f"protected_legacy[{index}]"
        record = _require_fields(
            candidate,
            {"key", "output", "sprite", "sha256", "runtime_size"},
            context,
        )
        key, sprite, sha256 = record["key"], record["sprite"], record["sha256"]
        if not all(isinstance(value, str) and value for value in (key, sprite, sha256)):
            raise RuntimeError(f"{context} string fields must be non-empty")
        if LOWER_SHA256.fullmatch(sha256) is None:
            raise RuntimeError(f"{context}.sha256 must be 64 lowercase hexadecimal characters")
        output = _relative_path(record["output"], f"{context}.output")
        if not (root / output).is_file():
            raise RuntimeError(f"{context} protected file is missing: {output.as_posix()}")
        protected.append(
            ProtectedSpec(
                key=key,
                output=output,
                sprite=sprite,
                sha256=sha256,
                runtime_size=_runtime_size(record["runtime_size"], f"{context}.runtime_size"),
            )
        )

    assignments: list[AssignmentSpec] = []
    declared_generated_sprites = {asset.sprite for asset in assets}
    for index, candidate in enumerate(top["country_assignments"]):
        context = f"country_assignments[{index}]"
        record = _require_fields(candidate, {"party_key", "sprite"}, context)
        party_key, sprite = record["party_key"], record["sprite"]
        if not all(isinstance(value, str) and value for value in (party_key, sprite)):
            raise RuntimeError(f"{context} string fields must be non-empty")
        if sprite not in declared_generated_sprites:
            raise RuntimeError(f"{context} references undeclared generated sprite: {sprite}")
        assignments.append(AssignmentSpec(party_key=party_key, sprite=sprite))

    _unique([asset.key for asset in assets] + [item.key for item in protected], "key")
    _unique([asset.source.as_posix() for asset in assets if asset.source is not None], "source")
    _unique([asset.output.as_posix() for asset in assets] + [item.output.as_posix() for item in protected], "output")
    _unique([asset.sprite for asset in assets] + [item.sprite for item in protected], "sprite")
    _unique([assignment.party_key for assignment in assignments], "assignment party key")
    return Catalog(tuple(assets), tuple(protected), tuple(assignments))


CATALOG = load_catalog()
ASSETS = CATALOG.assets
PROTECTED = CATALOG.protected
ASSIGNMENTS = CATALOG.assignments

REGISTRY_PATH = Path("interface/parties_texticons.gfx")
COUNTRY_REPORT_PATH = Path(
    "docs/superpowers/reports/2026-08-16-adiscord-party-country-emblems-contact-sheet.png"
)
GENERIC_REPORT_PATH = Path(
    "docs/superpowers/reports/2026-08-16-adiscord-party-generic-emblems-contact-sheet.png"
)


def render_icon(source: Path, runtime_size: tuple[int, int] = (32, 32)) -> bytes:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        if min(rgba.size) < 512:
            raise RuntimeError(f"party texticon master must be at least 512px: {source}")
        alpha = rgba.getchannel("A")
        if alpha.getextrema() == (255, 255):
            raise RuntimeError(f"party texticon master lacks transparency: {source}")
        bbox = alpha.getbbox()
        if bbox is None:
            raise RuntimeError(f"party texticon master is fully transparent: {source}")
        artwork_size = (runtime_size[0] - 2, runtime_size[1] - 2)
        cropped = rgba.crop(bbox)
        cropped.thumbnail(artwork_size, Image.Resampling.LANCZOS)
        cropped = cropped.filter(ImageFilter.UnsharpMask(radius=0.55, percent=115, threshold=2))
        canvas = Image.new("RGBA", runtime_size, (0, 0, 0, 0))
        canvas.alpha_composite(
            cropped,
            ((runtime_size[0] - cropped.width) // 2, (runtime_size[1] - cropped.height) // 2),
        )
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=False, compress_level=9)
        return output.getvalue()


def render_white_flag(runtime_size: tuple[int, int] = (32, 32)) -> bytes:
    if runtime_size != (32, 32):
        raise RuntimeError("procedural white flag supports only 32 by 32 pixels")
    canvas = Image.new("RGBA", runtime_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    dark = (28, 31, 34, 255)
    pole_light = (205, 210, 212, 255)
    draw.line((6, 4, 6, 28), fill=dark, width=3)
    draw.line((6, 5, 6, 27), fill=pole_light, width=1)
    outline = ((7, 5), (13, 4), (19, 6), (26, 5), (25, 15), (20, 17), (14, 15), (7, 16))
    cloth = ((8, 7), (13, 6), (19, 8), (24, 7), (23, 13), (20, 15), (14, 13), (8, 14))
    draw.polygon(outline, fill=dark)
    draw.polygon(cloth, fill=(247, 247, 243, 255))
    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _registry_assets(catalog: Catalog) -> list[AssetSpec | ProtectedSpec]:
    fallback = [asset for asset in catalog.assets if asset.asset_class == "fallback"]
    existing = [asset for asset in catalog.assets if asset.asset_class == "existing"]
    countries = sorted(
        (asset for asset in catalog.assets if asset.asset_class == "country"),
        key=lambda asset: asset.key,
    )
    generic = [asset for asset in catalog.assets if asset.asset_class == "generic"]
    protected_by_sprite = {item.sprite: item for item in catalog.protected}
    protected_order = [
        protected_by_sprite[sprite]
        for sprite in (
            "GFX_WRK_worker_revolutionary_party_texticon",
            "GFX_STP_hedonist_party_texticon",
            "GFX_VAL_etatist_party_texticon",
        )
    ]
    if len(fallback) != 1:
        raise RuntimeError(f"catalog must declare exactly one fallback, found {len(fallback)}")
    return [*fallback, *protected_order, *existing, *countries, *generic]


def render_registry(catalog: Catalog = CATALOG) -> bytes:
    lines = ["spriteTypes = {"]
    for item in _registry_assets(catalog):
        lines.extend(
            (
                "    spriteType = {",
                f'        name = "{item.sprite}"',
                f'        texturefile = "{item.output.as_posix()}"',
                "        legacy_lazy_load = no",
                "    }",
            )
        )
    lines.append("}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def render_contact_sheets(
    catalog: Catalog = CATALOG,
    root: Path = ROOT,
) -> dict[Path, bytes]:
    country_assets = sorted(
        (asset for asset in catalog.assets if asset.asset_class == "country"),
        key=lambda asset: asset.key,
    )
    if len(country_assets) != 16:
        raise RuntimeError(f"country contact sheet requires 16 assets, found {len(country_assets)}")
    country_sheet = Image.new("RGB", (1024, 1024), (34, 36, 40))
    country_draw = ImageDraw.Draw(country_sheet)
    country_font = ImageFont.load_default(size=18)
    for index, asset in enumerate(country_assets):
        if asset.source is None:
            raise RuntimeError(f"country asset lacks master source: {asset.key}")
        column, row = index % 4, index // 4
        cell_x, cell_y = column * 256, row * 256
        with Image.open(root / asset.source) as source:
            icon = ImageOps.contain(source.convert("RGBA"), (192, 192), Image.Resampling.LANCZOS)
        icon_x = cell_x + (256 - icon.width) // 2
        icon_y = cell_y + 16 + (192 - icon.height) // 2
        country_sheet.paste(icon, (icon_x, icon_y), icon)
        label = asset.source.name.split("_", 1)[0]
        box = country_draw.textbbox((0, 0), label, font=country_font)
        label_x = cell_x + (256 - (box[2] - box[0])) // 2
        country_draw.text((label_x, cell_y + 224), label, font=country_font, fill=(235, 235, 235))

    generic_assets = [asset for asset in catalog.assets if asset.asset_class == "generic"]
    if len(generic_assets) != 24:
        raise RuntimeError(f"generic contact sheet requires 24 assets, found {len(generic_assets)}")
    generic_sheet = Image.new("RGB", (960, 2048), (34, 36, 40))
    generic_draw = ImageDraw.Draw(generic_sheet)
    generic_font = ImageFont.load_default(size=16)
    for index, asset in enumerate(generic_assets):
        if asset.source is None or asset.ideology is None or asset.archetype is None:
            raise RuntimeError(f"generic asset lacks contact-sheet metadata: {asset.key}")
        row, column = divmod(index, 3)
        cell_x, cell_y = column * 320, row * 256
        with Image.open(root / asset.source) as source:
            icon = ImageOps.contain(source.convert("RGBA"), (192, 192), Image.Resampling.LANCZOS)
        icon_x = cell_x + (320 - icon.width) // 2
        icon_y = cell_y + 12 + (192 - icon.height) // 2
        generic_sheet.paste(icon, (icon_x, icon_y), icon)
        label = f"{asset.ideology}/{asset.archetype}"
        box = generic_draw.textbbox((0, 0), label, font=generic_font)
        label_x = cell_x + (320 - (box[2] - box[0])) // 2
        generic_draw.text((label_x, cell_y + 224), label, font=generic_font, fill=(235, 235, 235))

    return {
        root / COUNTRY_REPORT_PATH: _png_bytes(country_sheet),
        root / GENERIC_REPORT_PATH: _png_bytes(generic_sheet),
    }


def expected_outputs(root: Path = ROOT) -> dict[Path, bytes]:
    catalog = CATALOG if root == ROOT else load_catalog(root)
    outputs: dict[Path, bytes] = {}
    for asset in catalog.assets:
        if asset.source_kind == "master":
            if asset.source is None:
                raise RuntimeError(f"master asset lacks source: {asset.key}")
            rendered = render_icon(root / asset.source, asset.runtime_size)
        elif asset.source_kind == "procedural_white_flag":
            rendered = render_white_flag(asset.runtime_size)
        else:
            raise RuntimeError(f"unsupported source kind after validation: {asset.source_kind}")
        outputs[root / asset.output] = rendered
    outputs[root / REGISTRY_PATH] = render_registry(catalog)
    outputs.update(render_contact_sheets(catalog, root))
    return outputs


def protected_issues(root: Path = ROOT) -> list[str]:
    catalog = CATALOG if root == ROOT else load_catalog(root)
    problems: list[str] = []
    for protected in catalog.protected:
        path = root / protected.output
        if not path.is_file():
            problems.append(f"protected party texticon missing: {protected.output.as_posix()}")
            continue
        try:
            with Image.open(path) as image:
                if image.size != protected.runtime_size:
                    problems.append(
                        f"protected party texticon size mismatch: {protected.output.as_posix()} "
                        f"{image.size} != {protected.runtime_size}"
                    )
        except OSError as error:
            problems.append(f"protected party texticon unreadable: {protected.output.as_posix()}: {error}")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != protected.sha256:
            problems.append(
                f"protected party texticon hash mismatch: {protected.output.as_posix()} "
                f"{actual_hash} != {protected.sha256}"
            )
    return problems


def drift(root: Path = ROOT) -> list[str]:
    problems = protected_issues(root)
    if problems:
        return problems
    for output, expected in expected_outputs(root).items():
        if not output.is_file() or output.read_bytes() != expected:
            problems.append(output.relative_to(root).as_posix())
    return problems


def apply(root: Path = ROOT) -> None:
    problems = protected_issues(root)
    if problems:
        raise RuntimeError("; ".join(problems))
    for output, expected in expected_outputs(root).items():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate generated icons (default)")
    actions.add_argument("--apply", action="store_true", help="write generated icons")
    args = parser.parse_args()
    if args.apply:
        try:
            apply()
        except RuntimeError as error:
            print(f"Party texticon build refused: {error}")
            return 1
        print("Built 51 party texticons, one GFX registry, and two contact sheets.")
        return 0
    problems = drift()
    if problems:
        print("Party texticon drift: " + ", ".join(problems))
        return 1
    print("Party texticons are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

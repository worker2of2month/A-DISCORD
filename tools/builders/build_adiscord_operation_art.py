"""Export operation photographs with the supplied CRT layer; retain no originals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

from tools.lib.adiscord_ui_surfaces import apply_or_check, dds_bytes
from tools.lib.paths import repository_root
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = repository_root()
BASE_GAME = Path(r"Z:\SteamLibrary\steamapps\common\Hearts of Iron IV")
MANIFEST = ROOT / "tools/assets/source/intelligence_operations/operation_art_prompts.json"


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def read_entries(path):
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def overlaid_files(directory):
    replaced = {
        entry.value for entry in read_entries(ROOT / "descriptor.mod")
        if entry.key == "replace_path"
    }
    files = {} if directory in replaced else {
        path.name: path for path in (BASE_GAME / directory).glob("*.txt")
    }
    files.update({path.name: path for path in (ROOT / directory).glob("*.txt")})
    return [files[name] for name in sorted(files)]


def native_bindings():
    """Follow operations through native fallback phases to their actual GFX paths."""
    phases = {}
    for path in overlaid_files("common/operation_phases"):
        for entry in read_entries(path):
            if isinstance(entry.value, list):
                phases[entry.key] = {child.key: child.value for child in entry.value}
    sprites = set()
    for path in overlaid_files("common/operations"):
        for operation in read_entries(path):
            if not isinstance(operation.value, list):
                continue
            for child in operation.value:
                if child.key == "icon":
                    sprites.add(child.value)
                elif child.key == "phases":
                    for phase in child.value:
                        sprites.update(phases[phase.key][key] for key in ("picture", "icon"))
    definitions = {}
    gfx_files = {path.name: path for path in (BASE_GAME / "interface").glob("*.gfx")}
    gfx_files.update({path.name: path for path in (ROOT / "interface").glob("*.gfx")})
    for path in gfx_files.values():
        # Only files mentioning a requested sprite need parsing.
        text = path.read_text(encoding="utf-8-sig")
        if not any(sprite in text for sprite in sprites):
            continue
        for group in parse_clausewitz(text):
            if not isinstance(group.value, list):
                continue
            for entry in group.value:
                if not isinstance(entry.value, list):
                    continue
                fields = {child.key.lower(): child.value for child in entry.value}
                name = fields.get("name")
                if name in sprites:
                    texture = fields["texturefile"].replace("\\", "/")
                    with Image.open(BASE_GAME / texture) as image:
                        definitions[name] = {"path": texture, "size": list(image.size)}
    if sprites != definitions.keys():
        raise ValueError(f"Missing operation sprites: {sorted(sprites - definitions.keys())}")
    return definitions


def finish_photo(source, overlay, size):
    photo = ImageOps.fit(source.convert("RGBA"), size, method=Image.Resampling.LANCZOS)
    photo = photo.filter(ImageFilter.GaussianBlur(0.3))
    photo = ImageOps.autocontrast(photo.convert("RGB"), cutoff=(0.3, 0.3), preserve_tone=True)
    photo = ImageEnhance.Contrast(photo).enhance(1.08)
    # Keep the supplied scanline rhythm visible even on the smallest native icon.
    crt = overlay.convert("RGBA").resize((448, 255), Image.Resampling.LANCZOS)
    left = (crt.width - size[0]) // 2
    top = (crt.height - size[1]) // 2
    crt = crt.crop((left, top, left + size[0], top + size[1]))
    # Mid-grey CRT pixels are neutral; scanlines must not lift photographic blacks.
    textured = ImageChops.soft_light(photo, crt.convert("RGB"))
    return Image.composite(textured, photo, crt.getchannel("A")).convert("RGBA")


def verified_image(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Source hash mismatch: {path.name}")
    with Image.open(path) as image:
        return image.convert("RGBA")


def expected_outputs(manifest, source_dir, overlay_path):
    overlay = verified_image(overlay_path, manifest["overlay"]["sha256"])
    scenes = {
        name: verified_image(source_dir / row["source_file"], row["source_sha256"])
        for name, row in manifest["scenes"].items()
    }
    rendered = {}
    outputs = {}
    for row in manifest["bindings"].values():
        key = (row["scene"], tuple(row["size"]))
        if key not in rendered:
            rendered[key] = dds_bytes(finish_photo(scenes[key[0]], overlay, key[1]))
        outputs[ROOT / row["path"]] = rendered[key]
    return outputs


def check_exports(manifest):
    failures = []
    for row in manifest["bindings"].values():
        path = ROOT / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256"):
            failures.append(row["path"])
    for path in failures:
        print(f"STALE: {path}")
    print(f"Operation art: {len(manifest['bindings'])} bindings, {len(failures)} stale exports")
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args()
    manifest = load_manifest()
    if bool(args.source_dir) != bool(args.overlay):
        parser.error("--source-dir and --overlay must be supplied together")
    if not args.source_dir:
        # Public checkout contains exports; editable originals are kept by the artist.
        result = check_exports(manifest)
        if args.apply and result:
            parser.error("Re-export needs --source-dir and --overlay containing the recorded originals")
        return result
    outputs = expected_outputs(manifest, args.source_dir, args.overlay)
    result = apply_or_check(outputs, args.apply, "Operation art")
    if args.apply and result == 0:
        for row in manifest["bindings"].values():
            row["sha256"] = hashlib.sha256(outputs[ROOT / row["path"]]).hexdigest()
        data = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        if MANIFEST.read_text(encoding="utf-8") != data:
            MANIFEST.write_text(data, encoding="utf-8")
    return result


if __name__ == "__main__":
    raise SystemExit(main())

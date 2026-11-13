"""Export super-event artwork through the supplied PSD without retaining originals."""

from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from tools.lib.paths import repository_root
from tools.lib.superevent_art import ARTWORK_BOX, CANVAS, apply_template


ROOT = repository_root()
MANIFEST = ROOT / "tools/assets/source/superevents/art_sources.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def planned_outputs(manifest: dict, source_root: Path) -> dict[Path, bytes]:
    template = ROOT / manifest["template"]["file"]
    if digest(template.read_bytes()) != manifest["template"]["sha256"]:
        raise ValueError("PSD changed; review the artwork export settings before rebuilding")
    outputs = {}
    for row in manifest["exports"].values():
        target = ROOT / row["runtime_file"]
        current = target.read_bytes() if target.exists() else b""
        # A completed export is not a source: applying CRT twice destroys detail.
        if row.get("runtime_sha256") and digest(current) == row["runtime_sha256"]:
            continue
        if "generated_file" in row:
            source = source_root / row["generated_file"]
            original = source.read_bytes()
        else:
            original = current
        if digest(original) != row["source_sha256"]:
            raise ValueError(f"Original artwork required to export {target.name}")
        with Image.open(BytesIO(original)) as image:
            result = apply_template(image, template)
        encoded = BytesIO()
        result.save(encoded, format="PNG")
        outputs[target] = encoded.getvalue()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--source-root", type=Path, default=Path.home() / ".codex/generated_images")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    outputs = planned_outputs(manifest, args.source_root)
    for path, content in outputs.items():
        print(f"{'WRITE' if args.apply else 'DIFFERENT'}: {path.relative_to(ROOT)}")
        if args.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    if args.apply:
        for row in manifest["exports"].values():
            row["runtime_sha256"] = digest((ROOT / row["runtime_file"]).read_bytes())
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in manifest["exports"].values():
        path = ROOT / row["runtime_file"]
        if path not in outputs or args.apply:
            with Image.open(path) as image:
                if image.size != CANVAS or image.getchannel("A").getbbox() != ARTWORK_BOX:
                    raise ValueError(f"Invalid super-event viewport: {path.name}")
    print(f"Super-event art: {len(outputs)} {'updated' if args.apply else 'different'} exports")
    return int(bool(outputs) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())

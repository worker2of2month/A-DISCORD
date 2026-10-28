"""Export reviewed NAM focus compositions without changing their artwork."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

from PIL import Image

from tools.lib.paths import repository_root


ROOT = repository_root()
SOURCE = Path("tools/assets/source/focus_icons/NAM")
MANIFEST = SOURCE / "focus_art_prompts.json"
OUTPUT = Path("gfx/interface/goals/NAM")
CANVAS = (150, 150)
CONTENT = (140, 134)


def expected_outputs() -> dict[Path, bytes]:
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    outputs = {}
    seen = set()
    for entry in manifest.get("focus_compositions", []):
        focus_id = entry["focus_id"]
        if not focus_id.startswith("NAM_") or focus_id in seen:
            raise ValueError(f"Invalid or duplicate focus: {focus_id}")
        seen.add(focus_id)
        source = (ROOT / SOURCE / entry["file"]).resolve()
        if not source.is_relative_to((ROOT / SOURCE).resolve()):
            raise ValueError(f"Source escapes artwork folder: {source}")
        output = OUTPUT / f"GFX_focus_{focus_id}.png"
        if entry["runtime"] != output.as_posix():
            raise ValueError(f"Runtime path does not match focus: {focus_id}")
        with Image.open(source) as image:
            if image.mode != "RGBA":
                raise ValueError(f"Composition lacks alpha: {source}")
            alpha = image.getchannel("A")
            if alpha.getextrema()[0] != 0:
                raise ValueError(f"Composition lacks transparent margins: {source}")
            bounds = alpha.getbbox()
            if bounds is None:
                raise ValueError(f"Empty composition: {source}")
            art = image.crop(bounds)
            art.thumbnail(CONTENT, Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", CANVAS)
            # Keep the silhouette above the native title plate and away from connectors.
            position = ((CANVAS[0] - art.width) // 2, 140 - art.height)
            canvas.alpha_composite(art, position)
            stream = io.BytesIO()
            canvas.save(stream, format="PNG", optimize=True)
            outputs[ROOT / output] = stream.getvalue()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, content in expected_outputs().items():
        if path.exists() and path.read_bytes() == content:
            continue
        stale.append(path)
        if args.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        print(f"{'WROTE' if args.apply else 'STALE'}: {path.relative_to(ROOT)}")
    if not stale:
        print("NAM focus icon exports are current.")
    return int(bool(stale) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())

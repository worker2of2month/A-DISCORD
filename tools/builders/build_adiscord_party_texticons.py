"""Build the generated A-Discord party texticons from transparent masters."""

from __future__ import annotations

import argparse
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AssetSpec:
    key: str
    source: Path
    output: Path


ASSETS = (
    AssetSpec("ivn_roar_of_freedom", Path("tools/assets/source/party_texticons/IVN_roar_of_freedom_source.png"), Path("gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png")),
    AssetSpec("ivn_emergency_committee", Path("tools/assets/source/party_texticons/IVN_emergency_committee_source.png"), Path("gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png")),
    AssetSpec("tva_wartime_technocratic_worker", Path("tools/assets/source/party_texticons/TVA_wartime_technocratic_worker_source.png"), Path("gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png")),
    AssetSpec("vad_vorkerland_imperial", Path("tools/assets/source/party_texticons/VAD_vorkerland_imperial_source.png"), Path("gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png")),
    AssetSpec("zao_independent_party", Path("tools/assets/source/party_texticons/ZAO_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png")),
    AssetSpec("pwr_independent_party", Path("tools/assets/source/party_texticons/PWR_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png")),
    AssetSpec("vla_independent_party", Path("tools/assets/source/party_texticons/VLA_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png")),
    AssetSpec("rom_independent_party", Path("tools/assets/source/party_texticons/ROM_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png")),
    AssetSpec("sol_independent_party", Path("tools/assets/source/party_texticons/SOL_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png")),
    AssetSpec("tru_independent_party", Path("tools/assets/source/party_texticons/TRU_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png")),
)


def render_icon(source: Path) -> bytes:
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
        cropped = rgba.crop(bbox)
        cropped.thumbnail((23, 23), Image.Resampling.LANCZOS)
        cropped = cropped.filter(ImageFilter.UnsharpMask(radius=0.55, percent=115, threshold=2))
        canvas = Image.new("RGBA", (25, 25), (0, 0, 0, 0))
        canvas.alpha_composite(cropped, ((25 - cropped.width) // 2, (25 - cropped.height) // 2))
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=False, compress_level=9)
        return output.getvalue()


def expected_outputs(root: Path = ROOT) -> dict[Path, bytes]:
    return {root / asset.output: render_icon(root / asset.source) for asset in ASSETS}


def drift(root: Path = ROOT) -> list[str]:
    problems = []
    for output, expected in expected_outputs(root).items():
        if not output.is_file() or output.read_bytes() != expected:
            problems.append(str(output.relative_to(root)))
    return problems


def apply(root: Path = ROOT) -> None:
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
        apply()
        print("Built 10 party texticons.")
        return 0
    problems = drift()
    if problems:
        print("Party texticon drift: " + ", ".join(problems))
        return 1
    print("Party texticons are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Composite the supplied super-event PSD over an artwork viewport."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageOps
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.composite import composite
from psd_tools.composite.adjustments import ADJUSTMENT_FUNC
from scipy.interpolate import RegularGridInterpolator


CANVAS = (1001, 639)
ARTWORK_BOX = (48, 82, 956, 592)
ARTWORK_SIZE = (908, 510)
EFFECT_LAYERS = {
    "CRTEffectUseGlow", "Hue/Saturation 1", "Levels 1",
    "Color Lookup 1", "Brightness/Contrast 1",
}


def apply_color_lookup(pixels, color_mode, layer):
    """The embedded .look table is RGB float32 with red varying fastest."""
    document = ET.fromstring(layer._data[b"LUT3DFileData"].value)
    size = int(document.findtext("LUT/size").strip('" \r\n'))
    data = bytes.fromhex(document.findtext("LUT/data").strip('" \r\n'))
    table = np.frombuffer(data, dtype="<f4").reshape(size, size, size, 3)
    axis = np.linspace(0, 1, size)
    interpolate = RegularGridInterpolator((axis, axis, axis), table)
    return interpolate(np.clip(pixels[..., :3], 0, 1)[..., ::-1]).astype(np.float32)


@lru_cache(maxsize=2)
def load_template(path: str):
    template = PSDImage.open(path)
    names = {layer.name for layer in template}
    if template.size != CANVAS or not EFFECT_LAYERS <= names:
        raise ValueError("The super-event PSD does not contain the expected effect stack")
    return template


def artwork_pixels(image: Image.Image) -> Image.Image:
    if image.size == CANVAS:
        return image.convert("RGB").crop(ARTWORK_BOX)
    return ImageOps.fit(image.convert("RGB"), ARTWORK_SIZE, method=Image.Resampling.LANCZOS)


def apply_template(image: Image.Image, template_path: Path) -> Image.Image:
    """Preserve native PSD offsets, blend modes, opacity and adjustment values."""
    template = load_template(str(template_path.resolve()))
    artwork = PixelLayer.frompil(
        artwork_pixels(image), template, name="Super-event artwork", top=82, left=48,
    )
    template.remove(artwork)
    template.insert(0, artwork)
    previous = ADJUSTMENT_FUNC.get("colorlookup")
    ADJUSTMENT_FUNC["colorlookup"] = apply_color_lookup
    try:
        color, _, _ = composite(
            template, alpha=0.0, viewport=ARTWORK_BOX,
            layer_filter=lambda layer: layer is artwork or layer.name in EFFECT_LAYERS,
            force=True,
        )
    finally:
        template.remove(artwork)
        if previous is None:
            ADJUSTMENT_FUNC.pop("colorlookup", None)
        else:
            ADJUSTMENT_FUNC["colorlookup"] = previous
    photo = Image.fromarray(np.rint(np.clip(color, 0, 1) * 255).astype(np.uint8))
    result = Image.new("RGBA", CANVAS)
    result.paste(photo, ARTWORK_BOX[:2])
    return result

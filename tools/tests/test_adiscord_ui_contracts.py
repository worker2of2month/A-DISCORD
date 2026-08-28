import unittest

from PIL import Image

from tools.lib.adiscord_ui_contracts import (
    SpriteContract,
    contact_sheet,
    render_gfx_entry,
    validate_contract_image,
)


class UiContractTests(unittest.TestCase):
    def test_fixed_sprite_requires_total_native_dimensions(self) -> None:
        contract = SpriteContract(
            source_name="GFX_example",
            target_name="GFX_ADISCORD_example",
            filename="example.dds",
            kind="spriteType",
            total_size=(516, 42),
            frames=2,
            effect_file="gfx/FX/buttonstate_nodowneffect.lua",
        )
        with self.assertRaisesRegex(ValueError, "expected 516x42"):
            validate_contract_image(contract, Image.new("RGBA", (258, 42)))

    def test_gfx_entry_preserves_kind_frames_and_effect(self) -> None:
        contract = SpriteContract(
            source_name="GFX_example",
            target_name="GFX_ADISCORD_example",
            filename="example.dds",
            kind="spriteType",
            total_size=(516, 42),
            frames=2,
            effect_file="gfx/FX/buttonstate_nodowneffect.lua",
        )
        rendered = render_gfx_entry(contract, "gfx/interface/example.dds")
        self.assertIn('name = "GFX_ADISCORD_example"', rendered)
        self.assertIn("noOfFrames = 2", rendered)
        self.assertIn('effectFile = "gfx/FX/buttonstate_nodowneffect.lua"', rendered)

    def test_contact_sheet_is_deterministic_and_rgba(self) -> None:
        entries = [
            ("a", Image.new("RGBA", (40, 20), (10, 20, 30, 255))),
            ("b", Image.new("RGBA", (20, 40), (40, 50, 60, 255))),
        ]
        first = contact_sheet(entries, width=160)
        second = contact_sheet(entries, width=160)
        self.assertEqual(first.mode, "RGBA")
        self.assertEqual(first.tobytes(), second.tobytes())

    def test_contract_validation_rejects_non_rgba_and_invalid_frame_width(self) -> None:
        non_rgba = SpriteContract(
            source_name="GFX_example",
            target_name="GFX_ADISCORD_example",
            filename="example.dds",
            kind="spriteType",
            total_size=(516, 42),
        )
        invalid_frames = SpriteContract(
            source_name="GFX_example",
            target_name="GFX_ADISCORD_example",
            filename="example.dds",
            kind="spriteType",
            total_size=(515, 42),
            frames=2,
        )

        with self.assertRaisesRegex(ValueError, "expected RGBA"):
            validate_contract_image(non_rgba, Image.new("RGB", (516, 42)))
        with self.assertRaisesRegex(ValueError, "width is not divisible by frames"):
            validate_contract_image(invalid_frames, Image.new("RGBA", (515, 42)))


if __name__ == "__main__":
    unittest.main()

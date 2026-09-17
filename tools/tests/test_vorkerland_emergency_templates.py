import json
import re
import unittest
from pathlib import Path


from tools.lib.paths import source_section
from tools.validators.validate_adiscord_division_templates import starting_template_counter


ROOT = Path(__file__).resolve().parents[2]
MAPPING = {
    "Emergency Militia": "ADISCORD_vorkerland_ensure_emergency_militia_template",
    "Worker Home Guard": "ADISCORD_vorkerland_ensure_worker_home_guard_template",
    "Workerland Militia": "ADISCORD_vorkerland_ensure_workerland_militia_template",
    "Workerland Mobile Group": "ADISCORD_vorkerland_ensure_workerland_mobile_group_template",
    "Armi Security Detachment": "ADISCORD_vorkerland_ensure_armi_security_detachment_template",
    "Armi Mobile Group": "ADISCORD_vorkerland_ensure_armi_mobile_group_template",
    "TVA Collapse Militia": "ADISCORD_vorkerland_ensure_tva_collapse_militia_template",
    "TVA Infiltration Cell": "ADISCORD_vorkerland_ensure_tva_infiltration_cell_template",
    "WPS Collapse Militia": "ADISCORD_vorkerland_ensure_wps_collapse_militia_template",
    "TGD Urban Guard": "ADISCORD_vorkerland_ensure_tgd_urban_guard_template",
    "Line Infantry Brigade": "ADISCORD_vorkerland_ensure_line_infantry_brigade_template",
}
REQUIRED_METADATA = {
    "Emergency Militia": ("is_locked = yes", "force_allow_recruiting = yes"),
    "Worker Home Guard": ("is_locked = yes", "force_allow_recruiting = yes"),
    "Workerland Mobile Group": (
        "is_locked = no",
        "force_allow_recruiting = yes",
    ),
}
CALLSITE_FILES = (
    "common/scripted_effects/ADISCORD_vorkerland_effects.txt",
    "common/scripted_effects/ADISCORD_vorkerland_effects.txt",
    "common/scripted_effects/ADISCORD_vorkerland_effects.txt",
    "common/decisions/ADISCORD_vorkerland_decisions.txt",
)


class EmergencyTemplateTests(unittest.TestCase):
    def test_every_template_has_idempotent_ensure_effect(self):
        source = source_section((ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8-sig"), 'emergency_template_effects')
        for name, effect in MAPPING.items():
            with self.subTest(name=name):
                block = re.search(rf"(?ms)^{re.escape(effect)}\s*=\s*\{{.*?^\}}", source)
                self.assertIsNotNone(block)
                self.assertIn(f'has_template = "{name}"', block.group(0))
                self.assertIn("NOT = {", block.group(0))
                self.assertIn(f'name = "{name}"', block.group(0))
                self.assertIn(f"template_counter = {starting_template_counter(name)}", block.group(0))

    def test_lock_and_recruitment_metadata_matches_live_spawn_contracts(self):
        source = source_section((
            ROOT
            / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        ).read_text(encoding="utf-8-sig"), 'emergency_template_effects')
        for name, required_tokens in REQUIRED_METADATA.items():
            effect = MAPPING[name]
            block = re.search(rf"(?ms)^{re.escape(effect)}\s*=\s*\{{.*?^\}}", source)
            self.assertIsNotNone(block)
            for token in required_tokens:
                with self.subTest(name=name, token=token):
                    self.assertIn(token, block.group(0))

    def test_every_authored_create_unit_precedes_scope_with_owner_ensure(self):
        all_source = "\n".join((ROOT / path).read_text(encoding="utf-8-sig") for path in CALLSITE_FILES)
        for name, effect in MAPPING.items():
            with self.subTest(name=name):
                for call in re.finditer(r"create_unit\s*=\s*\{[^{}]*division\s*=\s*\"[^\"]*division_template\s*=\s*\\\"" + re.escape(name), all_source):
                    before = all_source[max(0, call.start() - 500):call.start()]
                    self.assertIn(effect, before)

    def test_shared_owner_is_covered_once_in_division_template_audit(self):
        owner_path = (
            "common/scripted_effects/"
            "ADISCORD_vorkerland_effects.txt"
        )
        audit = json.loads(
            (ROOT / "tools/data/division_template_audit.json").read_text(
                encoding="utf-8"
            )
        )
        covered_names = []
        for row in audit["templates"]:
            sources = [row["source"], *row.get("source_aliases", [])]
            if row["technical_name"] in MAPPING and any(
                source.get("path") == owner_path for source in sources
            ):
                # One audit row can cover several definitions in the same file.
                covered_names.append(row["technical_name"])
        self.assertCountEqual(covered_names, MAPPING)

    def test_shared_owners_replace_redundant_emergency_and_home_guard_blocks(self):
        collapse = source_section((
            ROOT
            / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        ).read_text(encoding="utf-8-sig"), 'collapse_effects')
        self.assertNotIn('name = "Emergency Militia"', collapse)
        self.assertNotIn('name = "Worker Home Guard"', collapse)


if __name__ == "__main__":
    unittest.main()

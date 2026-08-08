from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import validate


class DivisionTemplateAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self._write(
            "history/countries/AAA - Audit.txt",
            'oob = "AAA"\n# load_oob = "COMMENTED"\n',
        )
        self._write(
            "history/units/AAA.txt",
            '''division_template = {
    name = "Аудитная линия"
    regiments = { infantry = { x = 0 y = 0 } }
    support = { engineer = { x = 0 y = 0 } }
    division_names_group = AAA_INF_01
}
units = {
    division = {
        division_name = { name = "Unrelated display name" }
        location = 1
        division_template = "Аудитная линия"
        start_experience_factor = 0.15
        start_equipment_factor = 0.70
    }
}
''',
        )
        self._write(
            "common/units/ADISCORD_test_units.txt",
            '''sub_units = {
    infantry = {
        active = yes
        categories = { category_all_infantry category_army }
        max_organisation = 55
        manpower = 1000
        supply_consumption = 0.06
        need = { infantry_equipment = 100 }
    }
    engineer = {
        active = yes
        categories = { category_support_battalions category_army }
        max_organisation = 20
        manpower = 300
        supply_consumption = 0.02
        need = { support_equipment = 30 }
    }
}
''',
        )
        self._write(
            "common/units/equipment/ADISCORD_test_equipment.txt",
            '''equipments = {
    infantry_equipment = { is_archetype = yes active = yes }
    infantry_equipment_0 = { archetype = infantry_equipment active = yes }
    support_equipment = { is_archetype = yes active = yes }
    support_equipment_1 = { archetype = support_equipment active = yes }
}
''',
        )
        self._write(
            "common/technologies/ADISCORD_test_tech.txt",
            '''technologies = {
    ADISCORD_tech_starting_org = {
        category_all_infantry = { max_organisation = 1 }
    }
}
''',
        )
        self._write(
            "common/scripted_effects/ADISCORD_technology_baseline_effects.txt",
            '''ADISCORD_grant_technology_profile_common = {
    set_technology = { ADISCORD_tech_starting_org = 1 popup = no }
}
ADISCORD_grant_technology_profile_land = {
    set_technology = { ADISCORD_tech_starting_org = 1 popup = no }
}
ADISCORD_grant_2150_technology_baseline = {
    ADISCORD_grant_technology_profile_common = yes
}
ADISCORD_grant_starting_technology_profile = {
    ADISCORD_grant_2150_technology_baseline = yes
    ADISCORD_grant_technology_profile_land = yes
}
''',
        )
        self._write(
            "common/on_actions/00_ADISCORD_on_actions.txt",
            "on_actions = { on_startup = { effect = { every_country = { "
            "ADISCORD_grant_starting_technology_profile = yes } } } }\n",
        )
        self._write(
            "tools/data/generated_output_owners.json",
            json.dumps({"schema_version": 1, "families": []}),
        )
        self.audit_path = self.root / "tools/data/division_template_audit.json"
        self._write_audit(self._valid_audit())

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def _write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _valid_audit(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "assumptions": {
                "organization": "slot arithmetic mean after starting technology",
                "equipment": "sum of every occupied subunit need block",
                "supply": "sum of every occupied subunit supply_consumption",
            },
            "role_floors": {
                "line": 30.0,
                "territorial": 25.0,
                "reservist": 25.0,
                "emergency_militia": 20.0,
                "utility": 0.0,
            },
            "optional_sources": [],
            "templates": [
                {
                    "key": "aaa_audit_line",
                    "source": {
                        "kind": "oob",
                        "path": "history/units/AAA.txt",
                        "owner": "AAA",
                    },
                    "technical_name": "Audit Line",
                    "display_name": "Audit Line",
                    "legacy_names": ["Аудитная линия"],
                    "regiments": [{"type": "infantry", "x": 0, "y": 0}],
                    "support": [{"type": "engineer", "x": 0, "y": 0}],
                    "computed": {
                        "organization": 38.0,
                        "manpower": 1300.0,
                        "equipment": {
                            "infantry_equipment": 100.0,
                            "support_equipment": 30.0,
                        },
                        "supply": 0.08,
                    },
                    "equipment_availability": {
                        "infantry_equipment": True,
                        "support_equipment": True,
                    },
                    "ai_role": "line",
                    "replacement_path": {"kind": "retain", "target": "aaa_audit_line"},
                }
            ],
            "references": [
                {
                    "key": "aaa_audit_line_oob",
                    "path": "history/units/AAA.txt",
                    "kind": "oob",
                    "technical_name": "Audit Line",
                    "legacy_names": ["Аудитная линия"],
                    "start_experience_factor": 0.15,
                    "start_equipment_factor": 0.70,
                    "count": 1,
                }
            ],
        }

    def _write_audit(self, payload: dict[str, object]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _issues(self) -> list[str]:
        return validate(self.root, self.audit_path)

    def test_semantic_parser_computes_full_cost_and_starting_technology_org(self) -> None:
        issues = self._issues()
        non_ascii = [issue for issue in issues if "non-ASCII" in issue]
        self.assertEqual(len(non_ascii), 2, issues)
        self.assertFalse(any("computed" in issue for issue in issues), issues)
        self.assertFalse(any("coverage" in issue for issue in issues), issues)
        self.assertFalse(any("Unrelated display name" in issue for issue in issues), issues)

    def test_missing_template_row_is_a_coverage_failure(self) -> None:
        audit = self._valid_audit()
        audit["templates"] = []
        self._write_audit(audit)
        self.assertTrue(
            any("template coverage" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_create_unit_and_delete_references_are_semantic_and_covered(self) -> None:
        self._write(
            "common/scripted_effects/ADISCORD_refs.txt",
            '''audit_effect = {
    capital_scope = {
        create_unit = {
            division = "division_template = \\"Аудитная линия\\" start_experience_factor = 0.25 start_equipment_factor = 0.50"
            owner = PREV
        }
    }
    delete_unit_template_and_units = {
        division_template = "Аудитная линия"
        disband = no
    }
}
''',
        )
        audit = self._valid_audit()
        audit["references"].extend(
            [
                {
                    "key": "aaa_create_unit",
                    "path": "common/scripted_effects/ADISCORD_refs.txt",
                    "kind": "create_unit",
                    "technical_name": "Audit Line",
                    "legacy_names": ["Аудитная линия"],
                    "start_experience_factor": 0.25,
                    "start_equipment_factor": 0.50,
                    "count": 1,
                },
                {
                    "key": "aaa_delete_template",
                    "path": "common/scripted_effects/ADISCORD_refs.txt",
                    "kind": "technical_reference",
                    "technical_name": "Audit Line",
                    "legacy_names": ["Аудитная линия"],
                    "count": 1,
                },
            ]
        )
        self._write_audit(audit)
        issues = self._issues()
        self.assertEqual(
            len([issue for issue in issues if "non-ASCII" in issue]),
            4,
            issues,
        )
        self.assertFalse(any("reference coverage" in issue for issue in issues), issues)

    def test_unlisted_create_unit_reference_fails_coverage(self) -> None:
        self._write(
            "common/decisions/ADISCORD_refs.txt",
            'x = { create_unit = { division = "division_template = \\"Audit Line\\"" } }\n',
        )
        self.assertTrue(
            any("reference coverage" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_present_malformed_oob_start_factor_is_a_hard_issue(self) -> None:
        oob = self.root / "history/units/AAA.txt"
        oob.write_text(
            oob.read_text(encoding="utf-8").replace(
                "start_experience_factor = 0.15",
                "start_experience_factor = invalid",
            ),
            encoding="utf-8",
        )
        audit = self._valid_audit()
        audit["references"][0]["start_experience_factor"] = 1.0
        self._write_audit(audit)

        self.assertTrue(
            any(
                "invalid numeric start_experience_factor" in issue
                for issue in self._issues()
            ),
            self._issues(),
        )

    def test_present_malformed_create_unit_start_factor_is_a_hard_issue(self) -> None:
        self._write(
            "common/decisions/ADISCORD_refs.txt",
            '''x = {
    create_unit = {
        division = "division_template = \\"Audit Line\\" start_experience_factor = 0.25 start_equipment_factor = invalid"
    }
}
''',
        )
        audit = self._valid_audit()
        audit["references"].append(
            {
                "key": "aaa_malformed_create_unit",
                "path": "common/decisions/ADISCORD_refs.txt",
                "kind": "create_unit",
                "technical_name": "Audit Line",
                "legacy_names": [],
                "start_experience_factor": 0.25,
                "start_equipment_factor": 1.0,
                "count": 1,
            }
        )
        self._write_audit(audit)

        self.assertTrue(
            any(
                "invalid numeric start_equipment_factor" in issue
                for issue in self._issues()
            ),
            self._issues(),
        )

    def test_missing_equipment_archetype_is_explicit(self) -> None:
        equipment = self.root / "common/units/equipment/ADISCORD_test_equipment.txt"
        equipment.write_text(
            "equipments = { infantry_equipment = { is_archetype = yes active = yes } }\n",
            encoding="utf-8",
        )
        self.assertTrue(
            any("missing equipment archetype support_equipment" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_organization_below_role_floor_is_explicit(self) -> None:
        audit = self._valid_audit()
        audit["role_floors"]["line"] = 40.0
        self._write_audit(audit)
        self.assertTrue(
            any("organization 38" in issue and "floor 40" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_starting_technology_profile_must_be_routed_to_every_country(self) -> None:
        self._write(
            "common/on_actions/00_ADISCORD_on_actions.txt",
            "on_actions = { on_startup = { effect = { } } }\n",
        )
        self.assertTrue(
            any("starting technology profile is not routed" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_owner_specific_starting_organization_modifier_is_not_silently_ignored(self) -> None:
        self._write(
            "common/technologies/ADISCORD_test_tech.txt",
            '''technologies = {
    ADISCORD_tech_starting_org = {
        category_all_infantry = { max_organisation = 1 }
    }
    ADISCORD_tech_land_only_org = {
        category_all_infantry = { max_organisation = 2 }
    }
}
''',
        )
        effects = self.root / "common/scripted_effects/ADISCORD_technology_baseline_effects.txt"
        effects.write_text(
            effects.read_text(encoding="utf-8").replace(
                "ADISCORD_tech_starting_org = 1 popup = no }\n}\nADISCORD_grant_2150",
                "ADISCORD_tech_starting_org = 1 ADISCORD_tech_land_only_org = 1 popup = no }\n}\nADISCORD_grant_2150",
            ),
            encoding="utf-8",
        )
        self.assertTrue(
            any("owner-specific starting organization modifier" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_non_prefixed_starting_organization_technology_is_audited(self) -> None:
        self._write(
            "common/technologies/ADISCORD_test_tech.txt",
            '''technologies = {
    ADISCORD_tech_starting_org = {
        category_all_infantry = { max_organisation = 1 }
    }
    vanilla_org = {
        category_all_infantry = { max_organisation = 2 }
    }
}
''',
        )
        self._write(
            "common/scripted_effects/ADISCORD_technology_baseline_effects.txt",
            '''ADISCORD_grant_technology_profile_common = {
    set_technology = { ADISCORD_tech_starting_org = 1 popup = no }
}
ADISCORD_grant_technology_profile_land = {
    set_technology = { vanilla_org = 1 popup = no }
}
ADISCORD_grant_2150_technology_baseline = {
    ADISCORD_grant_technology_profile_common = yes
}
ADISCORD_grant_starting_technology_profile = {
    ADISCORD_grant_2150_technology_baseline = yes
    ADISCORD_grant_technology_profile_land = yes
}
''',
        )
        self.assertTrue(
            any(
                "owner-specific starting organization modifier vanilla_org" in issue
                for issue in self._issues()
            ),
            self._issues(),
        )

    def test_profile_granted_technology_without_definition_is_a_hard_issue(self) -> None:
        self._write(
            "common/scripted_effects/ADISCORD_technology_baseline_effects.txt",
            '''ADISCORD_grant_technology_profile_common = {
    set_technology = { ADISCORD_tech_starting_org = 1 popup = no }
}
ADISCORD_grant_technology_profile_land = {
    set_technology = { ADISCORD_tech_missing = 1 popup = no }
}
ADISCORD_grant_2150_technology_baseline = {
    ADISCORD_grant_technology_profile_common = yes
}
ADISCORD_grant_starting_technology_profile = {
    ADISCORD_grant_2150_technology_baseline = yes
    ADISCORD_grant_technology_profile_land = yes
}
''',
        )
        self.assertTrue(
            any(
                "starting technology ADISCORD_tech_missing has no definition" in issue
                for issue in self._issues()
            ),
            self._issues(),
        )

    def test_divergent_duplicate_name_fails_only_within_owner_namespace(self) -> None:
        self._write(
            "history/units/AAA.txt",
            (self.root / "history/units/AAA.txt").read_text(encoding="utf-8")
            + '''division_template = {
    name = "Аудитная линия"
    regiments = { infantry = { x = 0 y = 0 } infantry = { x = 0 y = 1 } }
}
''',
        )
        self.assertTrue(
            any("divergent duplicate" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_divergent_duplicate_name_fails_across_oobs_with_the_same_owner(self) -> None:
        self._write(
            "history/units/AAA.txt",
            '''division_template = {
    name = "Audit Line"
    regiments = { infantry = { x = 0 y = 0 } }
    support = { engineer = { x = 0 y = 0 } }
}
units = {
    division = {
        division_template = "Audit Line"
        start_experience_factor = 0.15
        start_equipment_factor = 0.70
    }
}
''',
        )
        country = self.root / "history/countries/AAA - Audit.txt"
        country.write_text(
            country.read_text(encoding="utf-8") + 'load_oob = "AAA_alt"\n',
            encoding="utf-8",
        )
        self._write(
            "history/units/AAA_alt.txt",
            '''division_template = {
    name = "Audit Line"
    regiments = {
        infantry = { x = 0 y = 0 }
        infantry = { x = 0 y = 1 }
    }
}
''',
        )
        audit = self._valid_audit()
        second = dict(audit["templates"][0])
        second["key"] = "aaa_audit_line_alt"
        second["source"] = {
            "kind": "oob",
            "path": "history/units/AAA_alt.txt",
            "owner": "AAA",
        }
        second["regiments"] = [
            {"type": "infantry", "x": 0, "y": 0},
            {"type": "infantry", "x": 0, "y": 1},
        ]
        second["support"] = []
        second["computed"] = {
            "organization": 56.0,
            "manpower": 2000.0,
            "equipment": {"infantry_equipment": 200.0},
            "supply": 0.12,
        }
        second["equipment_availability"] = {"infantry_equipment": True}
        second["replacement_path"] = {"kind": "retain", "target": "aaa_audit_line_alt"}
        audit["templates"].append(second)
        self._write_audit(audit)

        self.assertTrue(
            any("divergent duplicate" in issue and "owner AAA" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_optional_source_requires_exact_registry_owner_and_audits_when_present(self) -> None:
        audit = self._valid_audit()
        audit["optional_sources"] = [
            {
                "path": "history/units/BBB.txt",
                "owner_module": "tools.builders.build_bbb",
            }
        ]
        self._write_audit(audit)
        issues = self._issues()
        self.assertTrue(any("optional source" in issue and "registry" in issue for issue in issues), issues)

        self._write(
            "tools/data/generated_output_owners.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "families": [
                        {
                            "id": "bbb",
                            "owner_module": "tools.builders.build_bbb",
                            "output_globs": ["history/units/BBB.txt"],
                        }
                    ],
                }
            ),
        )
        self.assertFalse(any("optional source" in issue for issue in self._issues()), self._issues())

        self._write(
            "history/countries/BBB - Optional.txt",
            'oob = "BBB"\n',
        )
        self._write(
            "history/units/BBB.txt",
            'division_template = { name = "BBB Line" regiments = { infantry = { x = 0 y = 0 } } }\n',
        )
        self.assertTrue(
            any("template coverage" in issue and "BBB" in issue for issue in self._issues()),
            self._issues(),
        )

    def test_template_source_kind_must_be_known_and_match_the_actual_definition(self) -> None:
        for source_kind in ("unknown", "script"):
            with self.subTest(source_kind=source_kind):
                audit = self._valid_audit()
                audit["templates"][0]["source"]["kind"] = source_kind
                self._write_audit(audit)

                self.assertTrue(
                    any("source kind" in issue for issue in self._issues()),
                    self._issues(),
                )

    def test_template_source_owner_must_match_the_actual_definition(self) -> None:
        audit = self._valid_audit()
        audit["templates"][0]["source"]["owner"] = "WRONG"
        self._write_audit(audit)

        self.assertTrue(
            any("source owner" in issue for issue in self._issues()),
            self._issues(),
        )


if __name__ == "__main__":
    unittest.main()

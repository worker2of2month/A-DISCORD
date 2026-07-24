# Stelander–Kefreyt Crisis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete event-driven Stelander succession crisis, contextual Nodrul intervention, Kefreyt contract campaign, guarded northern war, adaptive AI, and decision-board UI described in the approved design.

**Architecture:** Country-scoped variables and role flags are changed only by central scripted effects. Timed missions and narrow on-actions drive phase changes; focuses and decisions call those effects, while GUI and AI only read precomputed state. Civil-war countries are tracked through global event targets so the postwar successor can be either the original STP or a dynamic splinter without breaking the later VAL war.

**Tech Stack:** Hearts of Iron IV 1.19 script, national focuses, decisions/missions, country events, scripted effects/triggers/localisation/GUI, dynamic modifiers, AI strategies, Russian UTF-8-BOM localisation, and Python `unittest` feature validators.

## Global Constraints

- Preserve all existing focus IDs named in the design; add new IDs only under `STP_`, `VAL_`, `NOD_`, or `ADISCORD_STP_VAL_`.
- Ivanov dies on campaign day 267; the four pre-death mission durations are 70, 70, 63, and 63 days, with the engine's inclusive start day verified in-game against `DEATH_CAMPAIGN_DAY = 267`.
- Standard crisis focuses cost 5 focus points (35 days), are `cancelable = no`, and survive stages 1–4 only through their own sticky flag.
- No `on_daily`, unrestricted `every_country`, global daily simulation, or GUI-side state mutation.
- Readiness and suspicion remain clamped to 0–100; node levels remain clamped to 0–3 or 0–2 exactly as specified.
- The player receives no guaranteed-success operation: posture, exposure, resources, target state, and cooldowns must all be checked at resolution.
- All equipment support is removed from a real sender stockpile before it is escrowed or transferred.
- `start_civil_war.army_ratio` splits the current army; arbitrary player-created divisions are never deleted or recreated.
- VAL cannot receive a scripted early STP war goal before the crisis window; the final VAL–STP war is unavoidable after 120/180/300/450 days.
- Temporary intervention uses `add_to_war`, not permanent faction membership.
- State 45/88 resource rights, military access, NAPs, truce, event targets, factory locks, participant flags, and delayed-event tokens have explicit cleanup paths.
- Full northern peace is allowed only for a clean campaign against eligible independent CIN and OSF; unexpected participants permanently contaminate that campaign.
- Reuse existing focus/idea art and existing leader likenesses. Derive Sotnikov's required 156×210 leader portrait from his existing 78×88 BOP art without inventing a different face.
- Preserve unrelated dirty-worktree changes. In particular, add new crisis AI and on-action files instead of editing dirty `common/ai_strategy/VAL.txt` or dirty `common/on_actions/00_ADISCORD_on_actions.txt`.
- Run `python tools/validate_tc.py` and the feature validator after every task; static success does not replace final in-game debug-log and UI verification.

---

## File and Interface Map

### New focused files

| Path | Responsibility |
|---|---|
| `tools/stp_val_crisis_manifest.py` | Canonical IDs, ranges, stage schedule, focus groups, successor matrix, state IDs |
| `tools/validate_adiscord_stp_val_crisis.py` | Read-only feature gate with sectioned checks |
| `tools/test_validate_adiscord_stp_val_crisis.py` | Unit tests for the validator and manifest |
| `common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt` | Schema init, clamped variable changes, modifier refresh, generic cleanup |
| `common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt` | Civil war, escrow, outcome finalization, intervention, war timers |
| `common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt` | VAL operations, contracts, obligations, leverage, northern campaign |
| `common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt` | Role, phase, outcome, deal, NOD and northern eligibility triggers |
| `common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt` | Three STP variable-backed crisis spirits and the VAL contract-state spirit |
| `common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt` | Narrow startup, war, peace, capitulation and government-change hooks |
| `common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt` | STP board, VAL board, NOD posture, northern campaign categories |
| `common/decisions/ADISCORD_STP_crisis_decisions.txt` | Health missions, two operation slots, party/resistance operations |
| `common/decisions/ADISCORD_VAL_contract_decisions.txt` | Foreign-operation slot, negotiation, obligations and war countdowns |
| `common/decisions/ADISCORD_NOD_crisis_decisions.txt` | Posture missions, limited-war timeouts and intervention choices |
| `events/ADISCORD_STP_crisis_events.txt` | Side choice, posture, death, civil-war and successor events |
| `events/ADISCORD_VAL_contract_events.txt` | Operation resolution, deal, timer warning and final-war events |
| `events/ADISCORD_NOD_crisis_events.txt` | NOD posture, limited wars, mandate and intervention events |
| `common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt` | Minimal focus tree for either civil-war side |
| `common/national_focus/ADISCORD_national_focus_STP_postwar.txt` | Leader-gated short postwar branches |
| `common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt` | Static posture-gated STP, VAL and NOD strategies |
| `interface/ADISCORD_STP_VAL_crisis.gui` | STP/VAL panels embedded in their decision categories |
| `interface/ADISCORD_STP_VAL_crisis.gfx` | Alias sprites for three STP spirits and the VAL contract spirit |
| `common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt` | Read-only `context_type = decision_category` bindings |
| `common/scripted_localisation/ADISCORD_STP_VAL_crisis_scripted_loc.txt` | Qualitative board text and tier names |
| `localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml` | Events, decisions, spirits, tooltips and GUI copy |
| `gfx/leaders/STP/portrait_STP_Grigory_Sotnikov.png` | 156×210 country-leader portrait derived from the existing Sotnikov BOP art |

### Existing files changed deliberately

| Path | Change |
|---|---|
| `common/national_focus/ADISCORD_national_focus_STP.txt` | Calendar-driven spine, staged availability, focus effects, side choice |
| `common/national_focus/ADISCORD_national_focus_VAL.txt` | Real rewards, doctrine exclusivity, crisis branch and final invoice |
| `common/characters/STP.txt` | Shabrat leader block plus Sotnikov and Hedersett characters |
| `interface/ADISCORD_leader_portraits.gfx` | Register derived 156×210 Sotnikov art and existing 156×210 Hedersett art |
| `history/countries/STP - StepanLand.txt` | Main-role flag and schema bootstrap |
| `history/countries/VAL - ValeraLand.txt` | Remove static mercenary idea grant and bootstrap authority |
| `history/units/STP.txt` | Lock the unique Capital Guard template and cap it at one |
| `common/ideas/valeraland.txt` | Keep `VAL_mercenary_state` as a hidden no-modifier save stub |
| `common/bookmarks/the_gathering_storm.txt` | Stop granting the obsolete VAL idea |
| `common/on_actions/00_on_actions.txt` | Remove only the unsafe CIN/OSF/APH capitulation block |
| `common/decisions/ADISCORD_test_wars_decisions.txt` | Remove only the two VAL test-war decisions |
| `common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt` | Gate to the main prewar role and canonical health variable |
| `common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt` | Read canonical health and postwar role safely |
| `common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt` | Read canonical health stage and 0–100 suspicion/readiness safely |
| `localisation/russian/ADISCORD_national_focuses_l_russian.yml` | Correct existing STP/VAL focus descriptions |
| `localisation/russian/ADISCORD_stp_state_face_l_russian.yml` | Correct stage-face and percent-format localisation |

### Stable scripted interfaces

Later tasks must call these exact interfaces rather than writing variables directly:

```text
ADISCORD_STP_VAL_initialize_schema
STP_set_health_stage
STP_set_crisis_phase
STP_change_readiness
STP_change_suspicion
STP_change_node_palace
STP_change_node_officers
STP_change_node_mountains
STP_change_node_market
STP_change_node_street
STP_change_node_val_channel
STP_commit_to_shabrat
STP_commit_to_party
STP_lose_shabrat
STP_refresh_crisis_modifier
STP_finalize_internal_outcome
STP_cleanup_internal_war
VAL_change_contract_authority
VAL_change_stp_leverage
VAL_refresh_contract_modifier
VAL_clear_foreign_operation
VAL_STP_cleanup_contract_relations
VAL_STP_start_war_countdown
VAL_STP_trigger_breach
STP_VAL_begin_final_war
VAL_northern_cleanup_active_campaign
```

Role and eligibility triggers:

```text
STP_is_main_crisis_country
STP_is_crisis_party_side
STP_is_crisis_resistance_side
STP_is_postwar_country
STP_can_attempt_bloodless_coup
STP_resistance_network_is_viable
VAL_can_open_stp_negotiation
VAL_can_start_full_northern_campaign
VAL_can_start_partial_cin_campaign
VAL_can_start_partial_osf_campaign
NOD_can_directly_defend_stp
```

---

### Task 1: Add a failing feature validator and canonical manifest

**Files:**
- Create: `tools/stp_val_crisis_manifest.py`
- Create: `tools/validate_adiscord_stp_val_crisis.py`
- Create: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Consumes: approved design IDs and current repository paths.
- Produces: `validate(root: Path, section: str | None) -> list[str]`, CLI `--section`, and constants imported by tests.

- [ ] **Step 1: Write manifest unit tests before the manifest exists**

```python
import unittest

from tools.stp_val_crisis_manifest import (
    CIVIL_WAR_STATE_MAP,
    DECISION_CATEGORIES,
    DEATH_CAMPAIGN_DAY,
    HEALTH_STAGE_DAYS,
    LEADERS,
    NOD_LIMITED_TARGET_STATES,
    NOD_POSTURES,
    NODE_LIMITS,
    POSTWAR_FOCUS_IDS,
    RESOURCE_STATES,
    VAL_STP_INTEL_STATES,
    WAR_COUNTDOWN_MISSIONS,
)


class CrisisManifestTests(unittest.TestCase):
    def test_health_calendar_reaches_day_267(self):
        self.assertEqual(HEALTH_STAGE_DAYS, (70, 70, 63, 63))
        self.assertEqual(DEATH_CAMPAIGN_DAY, 267)
        self.assertEqual(sum(HEALTH_STAGE_DAYS), DEATH_CAMPAIGN_DAY - 1)

    def test_successors_have_distinct_ideology_groups(self):
        self.assertEqual(LEADERS["shabrat"], ("STP_maksim_shabrat", "chauvinism_ideology", "chauvinism"))
        self.assertEqual(LEADERS["sotnikov"], ("STP_grigory_sotnikov", "etatism_ideology", "etatism"))
        self.assertEqual(LEADERS["hedersett"], ("STP_rufus_hedersett", "aristocratic_hedonism", "hedonism"))
        self.assertEqual(len({group for _, _, group in LEADERS.values()}), 3)

    def test_node_limits_and_resource_states_are_fixed(self):
        self.assertEqual(NODE_LIMITS["palace"], 2)
        self.assertEqual(NODE_LIMITS["officers"], 3)
        self.assertEqual(NODE_LIMITS["mountains"], 3)
        self.assertEqual(NODE_LIMITS["market"], 2)
        self.assertEqual(NODE_LIMITS["street"], 2)
        self.assertEqual(NODE_LIMITS["val_channel"], 2)
        self.assertEqual(RESOURCE_STATES, (45, 88))
        self.assertEqual(VAL_STP_INTEL_STATES, (43, 44, 45, 88))
        self.assertEqual(len(POSTWAR_FOCUS_IDS), 15)

    def test_cross_file_ids_are_canonical(self):
        self.assertEqual(len(DECISION_CATEGORIES), 5)
        self.assertEqual(len(NOD_POSTURES), 5)
        self.assertEqual(NOD_LIMITED_TARGET_STATES["YPR"], (15, 19))
        self.assertEqual(WAR_COUNTDOWN_MISSIONS[-1], "STP_VAL_war_countdown_breached")
        self.assertEqual(set().union(*CIVIL_WAR_STATE_MAP.values()), {1, 2, 3, 28, 29, 43, 44, 45, 46, 53, 88})
```

- [ ] **Step 2: Run the unit test and verify RED**

Run: `python -m unittest tools.test_validate_adiscord_stp_val_crisis -v`

Expected: `ModuleNotFoundError: No module named 'tools.stp_val_crisis_manifest'`.

- [ ] **Step 3: Create the manifest with exact constants**

```python
HEALTH_STAGE_DAYS = (70, 70, 63, 63)
DEATH_CAMPAIGN_DAY = 267
RESOURCE_STATES = (45, 88)
VAL_STP_INTEL_STATES = (43, 44, 45, 88)
NORTHERN_STATES = {"CIN": 59, "OSF": 61}
NODE_LIMITS = {
    "palace": 2,
    "officers": 3,
    "mountains": 3,
    "market": 2,
    "street": 2,
    "val_channel": 2,
}
LEADERS = {
    "shabrat": ("STP_maksim_shabrat", "chauvinism_ideology", "chauvinism"),
    "sotnikov": ("STP_grigory_sotnikov", "etatism_ideology", "etatism"),
    "hedersett": ("STP_rufus_hedersett", "aristocratic_hedonism", "hedonism"),
}
DECISION_CATEGORIES = (
    "STP_crisis_operations",
    "VAL_contract_campaign",
    "NOD_crisis_posture",
    "VAL_northern_campaign",
    "STP_VAL_war_countdown_category",
)
NOD_POSTURES = (
    "NOD_crisis_posture_guardian",
    "NOD_crisis_posture_ypr",
    "NOD_crisis_posture_cof",
    "NOD_crisis_posture_beshay",
    "NOD_crisis_posture_wait",
)
NOD_BORDER_STATES = (10, 11)
NOD_LIMITED_TARGET_STATES = {
    "YPR": (15, 19),
    "COF": (14,),
    "BHG": (5,),
    "BBV": (7,),
}
NOD_LIMITED_TIMEOUT_DAYS = {"YPR": 240, "COF": 180, "BHG": 120, "BBV": 120}
WAR_COUNTDOWN_MISSIONS = (
    "STP_VAL_war_countdown_120",
    "STP_VAL_war_countdown_180",
    "STP_VAL_war_countdown_300",
    "STP_VAL_war_countdown_450",
    "STP_VAL_war_countdown_breached",
)
NORTHERN_MODES = (
    "VAL_northern_campaign_full",
    "VAL_northern_campaign_partial_cin",
    "VAL_northern_campaign_partial_osf",
)
NORTHERN_TARGET_LOCKS = (
    "VAL_northern_target_59_resolved",
    "VAL_northern_target_61_resolved",
)
CIVIL_WAR_STATE_MAP = {
    "party_base": (1, 2, 3),
    "palace": (28,),
    "officers": (29,),
    "mountains": (43, 44, 53),
    "market": (45,),
    "street": (46,),
    "resource_garrison": (88,),
}
RESISTANCE_POSTURES = {
    1: "quiet_palace_conspiracy",
    2: "officer_network",
    3: "mountain_street_uprising",
    4: "external_val_contract",
}
SECURITY_POSTURES = {
    1: ("total_surveillance", "street", "palace"),
    2: ("targeted_arrests", "palace", "mountains"),
    3: ("garrison_rotation", "officers", "market"),
    4: ("mass_purge", "mountains", "street"),
    5: ("false_tolerance", "market", "officers"),
}
VAL_NEGOTIATION_POSTURES = {
    1: "cautious_broker",
    2: "predatory_concessionaire",
    3: "fear_nodrul_reaction",
    4: "double_game",
}
POSTWAR_FOCUS_IDS = (
    "STP_Shabrat_Count_The_Surviving_Regiments",
    "STP_Shabrat_Open_The_Archives",
    "STP_Shabrat_Break_The_Mandate",
    "STP_Shabrat_Buy_The_Desert_Season",
    "STP_Shabrat_Fortify_The_Resource_Road",
    "STP_Sotnikov_The_Military_Committee",
    "STP_Sotnikov_Rebuild_The_General_Staff",
    "STP_Sotnikov_Arm_The_Northern_Passes",
    "STP_Sotnikov_War_On_Two_Maps",
    "STP_Hedersett_The_Party_After_The_Father",
    "STP_Hedersett_End_The_Lists",
    "STP_Hedersett_One_Last_Purge",
    "STP_Hedersett_Renew_The_Nodrul_Mandate",
    "STP_Hedersett_Pay_The_Deferred_Invoice",
    "STP_Hedersett_Rebuild_The_Festival_Army",
)
```

- [ ] **Step 4: Add validator tests for a deliberately empty temporary root**

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from tools import validate_adiscord_stp_val_crisis as validator


class CrisisValidatorTests(unittest.TestCase):
    def test_empty_root_reports_each_feature_layer(self):
        with TemporaryDirectory() as tmp:
            issues = validator.validate(Path(tmp))
        self.assertTrue(any("core scripted effects" in issue for issue in issues))
        self.assertTrue(any("STP crisis decisions" in issue for issue in issues))
        self.assertTrue(any("VAL contract events" in issue for issue in issues))
        self.assertTrue(any("crisis GUI" in issue for issue in issues))

    def test_unknown_section_is_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                validator.validate(Path(tmp), "unknown")
```

- [ ] **Step 5: Run the validator tests and verify RED**

Run: `python -m unittest tools.test_validate_adiscord_stp_val_crisis -v`

Expected: import or missing-API failure for `validate_adiscord_stp_val_crisis`.

- [ ] **Step 6: Implement the sectioned validator**

Use these exact sections and required files:

```python
SECTIONS = ("core", "stp", "civil_war", "val", "nod", "north", "ai", "gui", "localisation", "performance")
REQUIRED_FILES = {
    "core": (
        ("common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt", "core scripted effects"),
        ("common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt", "crisis scripted triggers"),
        ("common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt", "crisis on-actions"),
    ),
    "stp": (
        ("common/decisions/ADISCORD_STP_crisis_decisions.txt", "STP crisis decisions"),
        ("events/ADISCORD_STP_crisis_events.txt", "STP crisis events"),
    ),
    "civil_war": (
        ("common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt", "crisis war effects"),
        ("common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt", "civil-war focus tree"),
        ("common/national_focus/ADISCORD_national_focus_STP_postwar.txt", "postwar focus tree"),
    ),
    "val": (
        ("common/decisions/ADISCORD_VAL_contract_decisions.txt", "VAL contract decisions"),
        ("events/ADISCORD_VAL_contract_events.txt", "VAL contract events"),
    ),
    "nod": (
        ("common/decisions/ADISCORD_NOD_crisis_decisions.txt", "NOD crisis decisions"),
        ("events/ADISCORD_NOD_crisis_events.txt", "NOD crisis events"),
    ),
    "north": (
        ("common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt", "contract and northern effects"),
    ),
    "ai": (
        ("common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt", "crisis AI strategies"),
    ),
    "gui": (
        ("interface/ADISCORD_STP_VAL_crisis.gui", "crisis GUI"),
        ("common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt", "crisis scripted GUI"),
    ),
    "localisation": (
        ("localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml", "Russian crisis localisation"),
    ),
    "performance": (),
}
```

`validate()` must read files with `utf-8-sig`, report absent layers without crashing, reject unknown sections, check balanced braces, expose `extract_named_block(text, identifier)` through a brace-aware scanner, forbid `on_daily` and unrestricted `every_country` in feature files, and expose a CLI that exits 1 on findings and 0 on success. The manifest also owns `OWNED_FEATURE_FILES`; CLI `--print-owned-files` prints only those exact paths so final staging never relies on `git add -A` or broad directories.

- [ ] **Step 7: Run the tests and confirm GREEN**

Run: `python -m unittest tools.test_validate_adiscord_stp_val_crisis -v`

Expected: all manifest/validator unit tests pass.

- [ ] **Step 8: Run the feature validator and confirm the intended implementation RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py`

Expected: failure listing the not-yet-created gameplay layers.

- [ ] **Step 9: Commit the validator foundation**

```powershell
git add -- tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "test: add Stelander Kefreyt crisis feature gate"
```

### Task 2: Add schema initialization, successor characters, unique guard, and dynamic spirits

**Files:**
- Create: `common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt`
- Create: `common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt`
- Create: `common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt`
- Create: `common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt`
- Create: `interface/ADISCORD_STP_VAL_crisis.gfx`
- Create: `gfx/leaders/STP/portrait_STP_Grigory_Sotnikov.png`
- Modify: `common/characters/STP.txt`
- Modify: `interface/ADISCORD_leader_portraits.gfx`
- Modify: `history/units/STP.txt`
- Modify: `history/countries/STP - StepanLand.txt`
- Modify: `history/countries/VAL - ValeraLand.txt`
- Modify: `common/ideas/valeraland.txt`
- Modify: `common/bookmarks/the_gathering_storm.txt`
- Modify: `common/scripted_effects/ADISCORD_stp_state_face_effects.txt`
- Modify: `common/scripted_effects/ADISCORD_scripted_effects_stelander.txt`
- Modify: `common/bop/ADISCORD_bop_STP.txt`
- Modify: `localisation/russian/nsb_characters_l_russian.yml`

**Interfaces:**
- Consumes: manifest defaults and existing 156×210 STP portraits.
- Produces: all central clamped variable effects, schema version 1, successor characters, locked Capital Guard, three separate STP crisis spirits, and `VAL_contract_state`.

- [ ] **Step 1: Extend the validator tests with schema invariants**

Add tests asserting:

```python
def test_core_schema_owns_all_mutations(self):
    root = validator.ROOT
    core = validator.read(root / "common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt") or ""
    for effect in (
        "ADISCORD_STP_VAL_initialize_schema",
        "STP_set_crisis_phase",
        "STP_change_readiness",
        "STP_change_suspicion",
        "STP_refresh_crisis_modifier",
        "VAL_change_contract_authority",
        "VAL_change_stp_leverage",
        "VAL_refresh_contract_modifier",
    ):
        self.assertIn(effect, core)

def test_old_mercenary_idea_is_only_a_stub(self):
    idea = validator.read(validator.ROOT / "common/ideas/valeraland.txt") or ""
    history = validator.read(validator.ROOT / "history/countries/VAL - ValeraLand.txt") or ""
    bookmark = validator.read(validator.ROOT / "common/bookmarks/the_gathering_storm.txt") or ""
    stub = validator.extract_named_block(idea, "VAL_mercenary_state")
    self.assertIsNotNone(stub)
    self.assertNotIn("send_volunteer_size", stub)
    self.assertNotIn("army_attack_factor", stub)
    self.assertNotIn("VAL_mercenary_state", history)
    self.assertNotIn("VAL_mercenary_state", bookmark)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tools.test_validate_adiscord_stp_val_crisis.CrisisValidatorTests -v`

Expected: missing core files and unchanged mercenary idea assertions fail.

- [ ] **Step 3: Implement defaults and clamped mutation effects**

`ADISCORD_STP_VAL_initialize_schema` must migrate before it defaults: when schema version is absent, multiply an existing 0–1 `STP_party_suspicion` by 100, clamp it, copy an existing `STP_state_face_stage` into an absent `STP_leader_health_stage`, then set only absent defaults. Mirror the final health stage back to `STP_state_face_stage` for save compatibility and assign `ADISCORD_STP_VAL_crisis_schema_version = 1` last. A second call must change nothing. New-game defaults are:

```text
ADISCORD_STP_VAL_crisis_schema_version = 1
STP_leader_health_stage = 1
STP_state_face_stage = 1
STP_resistance_readiness = 10
STP_party_suspicion = 5
STP_crisis_phase = 1
STP_side_commitment = 0
STP_node_palace = 0
STP_node_officers = 0
STP_node_mountains = 0
STP_node_market = 0
STP_node_street = 0
STP_node_val_channel = 0
STP_security_posture = 0
STP_resistance_posture = 0
STP_security_adaptation_palace = 0
STP_security_adaptation_officers = 0
STP_security_adaptation_mountains = 0
STP_security_adaptation_market = 0
STP_security_adaptation_street = 0
STP_security_adaptation_foreign = 0
VAL_contract_authority = 35
VAL_STP_leverage = 0
VAL_negotiation_posture = 0
VAL_CIN_influence = 0
VAL_OSF_influence = 0
VAL_APH_influence = 0
VAL_CIN_contract_posture = 0
VAL_OSF_contract_posture = 0
VAL_APH_contract_posture = 0
```

`STP_set_crisis_phase` consumes an exact value 0–4, changes `STP_crisis_phase` only when different, and calls `mark_focus_tree_layout_dirty` in the current STP/postwar scope and literal VAL when it exists. Startup sets phase 1, Ivanov’s death sets 2 before outcome evaluation, `STP_finalize_internal_outcome` sets 3, and `STP_VAL_begin_final_war` sets 4.

`STP_change_readiness`, `STP_change_suspicion`, `STP_change_node_palace`, `STP_change_node_officers`, `STP_change_node_mountains`, `STP_change_node_market`, `STP_change_node_street`, and `STP_change_node_val_channel` each consume `value`, add it to their named variable, clamp with explicit below-zero and above-maximum branches, then call `STP_refresh_crisis_modifier`. `VAL_change_contract_authority` and `VAL_change_stp_leverage` follow the same contract and clamp to 0–100.

- [ ] **Step 4: Define variable-backed dynamic modifiers**

```hoi4
STP_fading_father = {
    enable = { has_country_flag = STP_main_campaign_side NOT = { has_country_flag = STP_ivanov_dead } }
    political_power_factor = STP_fading_pp_factor
    stability_factor = STP_fading_stability_factor
    command_power_gain_mult = STP_fading_command_power_factor
    planning_speed = STP_fading_planning_factor
    army_org_factor = STP_fading_org_factor
}

STP_underground_network = {
    enable = { has_country_flag = STP_main_campaign_side NOT = { has_country_flag = STP_internal_war_started } }
    stability_factor = STP_network_stability_factor
    consumer_goods_factor = STP_network_consumer_goods_factor
}

STP_security_pressure = {
    enable = { has_country_flag = STP_main_campaign_side NOT = { has_country_flag = STP_internal_outcome_finalized } }
    stability_factor = STP_pressure_stability_factor
    political_power_factor = STP_pressure_pp_factor
    industrial_capacity_factory = STP_pressure_factory_output_factor
}

VAL_contract_state = {
    enable = { original_tag = VAL }
    army_attack_factor = VAL_contract_attack_factor
    army_defence_factor = VAL_contract_defence_factor
    army_org_factor = VAL_contract_org_factor
    army_org_regain = VAL_contract_org_regain
    equipment_capture_factor = VAL_contract_capture_factor
    supply_consumption_factor = VAL_contract_supply_factor
    planning_speed = VAL_contract_planning_factor
    political_power_gain = VAL_contract_pp_gain
    stability_factor = VAL_contract_stability_factor
    ADISCORD_economy_trade_income_factor = VAL_contract_trade_income_factor
    ADISCORD_economy_military_industry_income_factor = VAL_contract_military_income_factor
    ADISCORD_economy_army_expense_factor = VAL_contract_army_expense_factor
}
```

`STP_refresh_crisis_modifier` sets the fading-father table by health stage, the underground-network thresholds at readiness 25/50/75/90, and the security-pressure thresholds at suspicion 25/50/75/90, then ensures the three distinct modifiers are active only during their documented lifecycles. `VAL_refresh_contract_modifier` sets every backing variable for the five authority bands 0–24, 25–49, 50–74, 75–89, and 90–100, then ensures only `VAL_contract_state` is active.

The core tests assert these exact STP backing-variable tables:

```text
fading stage 1: PP 0, stability 0, command 0, planning 0, org 0
fading stage 2: PP -0.05, stability -0.02, command -0.05, planning 0, org 0
fading stage 3: PP -0.10, stability -0.05, command -0.10, planning -0.05, org 0
fading stage 4: PP -0.20, stability -0.10, command -0.20, planning -0.10, org -0.05

network 0–24: stability 0, consumer goods 0
network 25–49: stability -0.02, consumer goods +0.01
network 50–74: stability -0.04, consumer goods +0.02
network 75–89: stability -0.07, consumer goods +0.03
network 90–100: stability -0.10, consumer goods +0.04

pressure 0–24: stability 0, PP 0, factory output 0
pressure 25–49: stability -0.02, PP -0.05, factory output 0
pressure 50–74: stability -0.05, PP -0.10, factory output -0.03
pressure 75–89: stability -0.10, PP -0.15, factory output -0.05
pressure 90–100: stability -0.15, PP -0.20, factory output -0.10
```

Register exact 68×68 aliases in `interface/ADISCORD_STP_VAL_crisis.gfx`:

```text
GFX_idea_STP_fading_father -> gfx/interface/ideas/STP/idea_STP_deadman_rulling_the_country.png
GFX_idea_STP_underground_network -> gfx/interface/ideas/STP/idea_STP_National_Strikes.png
GFX_idea_STP_security_pressure -> gfx/interface/ideas/STP/idea_STP_hidden_slaves_trade.png
GFX_idea_VAL_contract_state -> gfx/interface/ideas/VAL/idea_VAL_mercenary_state.png
```

- [ ] **Step 5: Add all three successor leader definitions**

Use existing art:

```hoi4
STP_maksim_shabrat = {
    name = STP_maksim_shabrat
    portraits = { civilian = { large = GFX_portrait_STP_Maksim_Shabrat } }
    country_leader = { ideology = chauvinism_ideology expire = "2200.1.1.1" id = -1 }
}
STP_grigory_sotnikov = {
    name = STP_grigory_sotnikov
    portraits = { civilian = { large = GFX_portrait_STP_Grigory_Sotnikov } }
    country_leader = { ideology = etatism_ideology expire = "2200.1.1.1" id = -1 }
}
STP_rufus_hedersett = {
    name = STP_rufus_hedersett
    portraits = { civilian = { large = GFX_portrait_STP_Rufus_Hedersett } }
    country_leader = { ideology = aristocratic_hedonism expire = "2200.1.1.1" id = -1 }
}
```

Create `gfx/leaders/STP/portrait_STP_Grigory_Sotnikov.png` as a 156×210 leader portrait derived from `gfx/interface/bop/STP_bop_less_hedonism_Sotnikov.png`, inspect it visually, then bind `GFX_portrait_STP_Grigory_Sotnikov` to it. Bind `GFX_portrait_STP_Rufus_Hedersett` to `gfx/leaders/STP/portrait_STP_Rufus_Hedersett.png`.

- [ ] **Step 6: Make Capital Guard unique and conservation-safe**

In `history/units/STP.txt`, add to the `Capital Guard` template:

```hoi4
is_locked = yes
force_allow_recruiting = no
division_cap = 1
```

Do not alter the other 13 starting divisions. Later civil-war code will test the template’s existence, disband it before the stockpile snapshot, and recreate one empty guard only when the existence flag was set.

- [ ] **Step 7: Bootstrap roles and migrate the old idea**

STP history receives `set_country_flag = STP_main_campaign_side` and `set_country_flag = STP_shabrat_available`; absence of the two loyalty flags means Capital Guard and state-88 garrison begin loyal to the party. VAL history and bookmark lose `VAL_mercenary_state`. The idea definition remains with its picture, `allowed = { always = no }`, `removal_cost = -1`, and an empty `modifier = { }`.

The new on-startup hook calls `ADISCORD_STP_VAL_initialize_schema` only for literal tags STP/VAL/NOD, removes the old STP power balance, removes the mercenary stub from VAL, and schedules no country-wide loop. During legacy migration, literal tag STP receives `STP_main_campaign_side` only while no internal-war/postwar role or finalized outcome exists; this restores old saves without granting the main role to a splinter. If STP is still pre-outcome, neither `STP_shabrat_available` nor `STP_shabrat_lost` exists, and `STP_maksim_shabrat` is an active recruited character, set `STP_shabrat_available`. For literal VAL on a pre-schema legacy save, reconstruct `VAL_contract_authority` idempotently from the manifest's completed-focus reward table: start at the historical base of 35, add the authority reward of every already completed central or specialization focus exactly once, clamp to 0–100, and assign the schema version only after reconstruction. A second load must leave the value unchanged. Unit tests cover both STP old-save paths and VAL saves with no completed focus, central focuses only, and mixed central/specialization completion. Legacy state-face setters become wrappers over `STP_set_health_stage`; legacy suspicion setters call `STP_change_suspicion` with 0–100 deltas. Keep old BOP and dynamic-modifier IDs as inert save stubs, but remove all active callbacks and the history grant.

- [ ] **Step 8: Run validators**

Run:

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section core
python tools/validate_tc.py
```

Expected: unit tests, core section, and total-conversion validator pass.

- [ ] **Step 9: Commit**

```powershell
git add -- common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt interface/ADISCORD_STP_VAL_crisis.gfx gfx/leaders/STP/portrait_STP_Grigory_Sotnikov.png common/characters/STP.txt interface/ADISCORD_leader_portraits.gfx history/units/STP.txt "history/countries/STP - StepanLand.txt" "history/countries/VAL - ValeraLand.txt" common/ideas/valeraland.txt common/bookmarks/the_gathering_storm.txt common/scripted_effects/ADISCORD_stp_state_face_effects.txt common/scripted_effects/ADISCORD_scripted_effects_stelander.txt common/bop/ADISCORD_bop_STP.txt localisation/russian/nsb_characters_l_russian.yml tools/test_validate_adiscord_stp_val_crisis.py tools/validate_adiscord_stp_val_crisis.py
git commit -m "feat: initialize Stelander Kefreyt crisis state"
```

### Task 3: Drive Ivanov’s calendar and staged focus windows

**Files:**
- Create: `common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt`
- Create: `common/decisions/ADISCORD_STP_crisis_decisions.txt`
- Create: `events/ADISCORD_STP_crisis_events.txt`
- Modify: `common/national_focus/ADISCORD_national_focus_STP.txt`
- Modify: `common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt`
- Modify: `common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt`
- Modify: `common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt`
- Modify: `localisation/russian/ADISCORD_stp_state_face_l_russian.yml`
- Modify: `tools/stp_val_crisis_manifest.py`

**Interfaces:**
- Consumes: `STP_set_health_stage`, main-role trigger and schema defaults.
- Produces: one visible active health mission, automatic spine completion, stage-gated sticky focuses, irreversible side choice by day 140.

- [ ] **Step 1: Add calendar/focus validator assertions**

The tests must require exactly four health mission IDs, forbid `cancel_effect`, require `cancelable = no` and `select_effect` on every non-spine crisis focus, assert that the death effect completes `STP_The_Father_Of_Peace_Is_Gone`, and require one-time posture selectors: five values for `STP_security_posture` and four values for `STP_resistance_posture`. Both selectors may run only while their variable is 0; no startup, reload, failure, refusal, stage-change, or ordinary cleanup path may reset or reroll either posture. Only the terminal full-crisis cleanup may remove them.

- [ ] **Step 2: Run the STP validator and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section stp`

Expected: missing decisions/events and focus-window invariants.

- [ ] **Step 3: Add the four chained health missions**

Define all five decision categories up front and add their IDs to the manifest:

```text
STP_crisis_operations: allowed tag = STP, visible with STP_main_campaign_side
VAL_contract_campaign: allowed tag = VAL, visible after VAL board unlock
NOD_crisis_posture: allowed tag = NOD, visible while the STP crisis exists
VAL_northern_campaign: allowed tag = VAL, visible after northern operations unlock
STP_VAL_war_countdown_category: allowed when tag = VAL or STP_is_postwar_country, visible only with one canonical countdown mission
```

`STP_VAL_war_countdown_category` is deliberately role-based so a human dynamic STP splinter can own and see the same native mission ID. It has no scripted GUI panel.

```text
STP_health_stage_1_to_2: 70 days
STP_health_stage_2_to_3: 70 days
STP_health_stage_3_to_4: 63 days
STP_health_stage_4_to_death: 63 days
```

Each timeout calls one event. The events use `STP_set_health_stage`, activate the next mission, and auto-complete the listed spine. The death event calls `STP_set_crisis_phase = { value = 2 }` before evaluating the internal outcome:

```text
stage 1 init: STP_Nectar_of_the_Gods
stage 2: STP_The_Man_Who_Bought_The_Sky, STP_When_The_Guarantee_Died
stage 3: STP_The_Dying_Feast, STP_The_Doctors_Lie
stage 4: STP_The_Last_Signature, STP_Cancel_The_Morning_Address, STP_A_Glass_Raised_Too_High
death: STP_The_Father_Of_Peace_Is_Gone
```

Only the main prewar STP can see/own these missions.

- [ ] **Step 4: Rewire the playable crisis focus windows**

Keep all existing IDs and cost 5. Use these stage gates:

```text
stage 1 roots:
  STP_Foreign_Guests_At_The_Banquet
  STP_Kefreite_Security_Offer
  STP_The_Old_Man_On_The_Balcony
  STP_The_City_Still_Dances
  STP_Count_The_Loyalists

stage 2:
  STP_Show_Him_The_Truth
  STP_Govern_In_His_Name
  STP_The_Valirian_Advisers
  STP_Contractors_In_The_Passes
  STP_Rumours_In_The_Highlands
  STP_The_Lower_Market

stage 3:
  STP_The_Party_Was_Not_Born_Here
  STP_The_Desert_Watches_The_Snow
  STP_The_Mountain_Printing_House
  STP_Hunt_The_Mountain_Cells
  STP_Steal_The_Black_Ledger
  STP_Burn_The_Client_Archives
  STP_The_Silent_Mountain_March
  STP_One_Last_National_Festival
  STP_Turn_The_Young_Officers
  STP_Feed_The_Festival_Police
  STP_The_Last_Confession
  STP_The_Hand_That_Still_Signs

stage 4:
  STP_Imported_Freedom
  STP_Cut_The_Silk_Leash
  STP_Renew_The_Cultural_Mandate
  STP_No_Mercenaries_In_Our_Mountains
  STP_Sell_The_Highland_Concessions
  STP_A_Name_On_The_Walls
  STP_Erase_His_Name
  STP_The_First_Witness
  STP_Silence_The_First_Witness
  STP_Lower_Market_Dossiers
  STP_The_Port_Must_Smile
  STP_Call_For_Shabrat
  STP_Seal_The_Western_Wing
  STP_The_People_Stop_Singing
  STP_Drown_The_Rumours_In_Music
  STP_Garrisons_Hesitate
  STP_Garrisons_Swear_Loyalty
```

The sticky flag is deterministic and unique: prefix the complete focus ID with `STP_focus_active_`. For example, `STP_The_Lower_Market` uses `STP_focus_active_STP_The_Lower_Market`, and `STP_Garrisons_Hesitate` uses `STP_focus_active_STP_Garrisons_Hesitate`. The validator enumerates the full manifest focus list and rejects a missing, shared, or duplicate sticky flag.

Every playable focus uses the same literal structure with its listed numeric stage:

```hoi4
cancelable = no
cancel_if_invalid = yes
continue_if_invalid = no
select_effect = { set_country_flag = STP_focus_active_STP_The_Lower_Market }
available = {
    NOT = { has_country_flag = STP_ivanov_dead }
    NOT = { has_country_flag = STP_crisis_late_choice_lock }
    OR = {
        check_variable = { var = STP_leader_health_stage value = 2 compare = equals }
        has_country_flag = STP_focus_active_STP_The_Lower_Market
    }
}
completion_reward = {
    clr_country_flag = STP_focus_active_STP_The_Lower_Market
    set_country_flag = STP_focus_market_open
}
```

Use these exact completion interfaces; the focuses open, discount, reveal, or protect operations and do not directly award a completed node:

| Focus | Side | Exact completion interface |
|---|---:|---|
| `STP_Foreign_Guests_At_The_Banquet` | neutral | `STP_focus_nodrul_observed` |
| `STP_Kefreite_Security_Offer` | neutral | `STP_focus_kefreyt_observed` |
| `STP_The_Old_Man_On_The_Balcony` | neutral | `STP_focus_palace_observed` |
| `STP_The_City_Still_Dances` | neutral | `STP_focus_street_observed` |
| `STP_Count_The_Loyalists` | neutral | `STP_focus_garrisons_observed` |
| `STP_Show_Him_The_Truth` | Shabrat | call `STP_commit_to_shabrat` |
| `STP_Govern_In_His_Name` | party | call `STP_commit_to_party` |
| `STP_The_Valirian_Advisers` | neutral | `STP_focus_nodrul_advisers_open` |
| `STP_Contractors_In_The_Passes` | neutral | `STP_focus_val_supply_open` |
| `STP_Rumours_In_The_Highlands` | neutral | `STP_focus_mountains_open` |
| `STP_The_Lower_Market` | neutral | `STP_focus_market_open` |
| `STP_The_Party_Was_Not_Born_Here` | Shabrat | `STP_focus_nodrul_disinformation_open` |
| `STP_The_Desert_Watches_The_Snow` | either | `STP_focus_val_red_line_known` |
| `STP_The_Mountain_Printing_House` | Shabrat | `STP_focus_mountain_caches_improved` |
| `STP_Hunt_The_Mountain_Cells` | party | `STP_focus_mountain_raids_improved` |
| `STP_Steal_The_Black_Ledger` | Shabrat | `STP_focus_black_ledger_open` |
| `STP_Burn_The_Client_Archives` | party | `STP_focus_archive_burning_open` |
| `STP_The_Silent_Mountain_March` | Shabrat | `STP_focus_silent_march_open` |
| `STP_One_Last_National_Festival` | party | `STP_focus_festival_police_open` |
| `STP_Turn_The_Young_Officers` | Shabrat | `STP_focus_young_officers_open` |
| `STP_Feed_The_Festival_Police` | party | `STP_focus_garrison_rotation_open` |
| `STP_The_Last_Confession` | Shabrat | `STP_focus_palace_channel_improved` |
| `STP_The_Hand_That_Still_Signs` | party | `STP_focus_seal_palace_improved` |
| `STP_Imported_Freedom` | Shabrat | `STP_focus_nodrul_mandate_exposed` |
| `STP_Cut_The_Silk_Leash` | Shabrat | `STP_focus_break_mandate_ready` |
| `STP_Renew_The_Cultural_Mandate` | party | `STP_focus_renew_mandate_ready` |
| `STP_No_Mercenaries_In_Our_Mountains` | party | `STP_focus_val_channel_countered` |
| `STP_Sell_The_Highland_Concessions` | Shabrat | `STP_focus_val_concession_ready` |
| `STP_A_Name_On_The_Walls` | Shabrat | `STP_focus_mountain_final_open` |
| `STP_Erase_His_Name` | party | `STP_focus_mountain_purge_open` |
| `STP_The_First_Witness` | Shabrat | `STP_focus_first_witness_open` |
| `STP_Silence_The_First_Witness` | party | `STP_focus_silence_witness_open` |
| `STP_Lower_Market_Dossiers` | Shabrat | `STP_focus_dossiers_protected` |
| `STP_The_Port_Must_Smile` | party | `STP_focus_market_censorship_ready` |
| `STP_Call_For_Shabrat` | Shabrat | `STP_focus_final_palace_move_open` |
| `STP_Seal_The_Western_Wing` | party | `STP_focus_final_palace_lock_open` |
| `STP_The_People_Stop_Singing` | Shabrat | `STP_focus_final_street_move_open` |
| `STP_Drown_The_Rumours_In_Music` | party | `STP_focus_final_street_lock_open` |
| `STP_Garrisons_Hesitate` | Shabrat | `STP_focus_final_garrison_move_open` |
| `STP_Garrisons_Swear_Loyalty` | party | `STP_focus_final_garrison_lock_open` |

Side-gated entries additionally require the exact `STP_side_commitment` value. Stage availability is equality, not `>=`, so a focus can cross a stage only through its own sticky flag. The validator requires every playable crisis focus and all fourteen operation starts to check `NOT = { has_country_flag = STP_crisis_late_choice_lock }`, making the forced day-140 penalty a real 35-day lock.

- [ ] **Step 5: Implement side choice and forced day-140 fallback**

`STP_Show_Him_The_Truth` calls `STP_commit_to_shabrat` and sets side commitment 1; `STP_Govern_In_His_Name` calls `STP_commit_to_party` and sets 2. Each clears the other route’s availability and schedules the matching hidden posture-selection event.

When Shabrat is committed and `STP_security_posture` is still 0, select exactly once from manifest values 1 total surveillance, 2 targeted arrests, 3 garrison rotation, 4 mass purge, or 5 false tolerance. Weights read initial party popularity, NOD mandate, stability, army equipment, and the five observed-family flags. The selected value is never cleared or rerolled by failure, refusal, stage change, or save/reload; only full crisis cleanup removes it.

When the party route is committed and `STP_resistance_posture` is still 0, select exactly once from the manifest values: 1 quiet palace conspiracy, 2 officer network, 3 mountain-street uprising, or 4 external VAL contract. Weights read the already observed palace/officer/mountain/street/VAL-channel flags and paid escrow; the selected value is never cleared or rerolled by operation failure, refusal, save/reload, or stage change. Only full crisis cleanup removes it.

At the stage-3 transition, if commitment is still 0, fire a mandatory event. It completes the selected focus by event without its normal reward, removes 50 political power, sets `STP_crisis_late_choice_lock` for 35 days, and applies either `+10` suspicion (Shabrat) or `+10` resistance readiness (party). AI weights read initial party popularity, NOD mandate, stability, and army strength once.

- [ ] **Step 6: Gate the inlay and scripted localisation**

Replace `original_tag = STP` visibility with `tag = STP` plus `has_country_flag = STP_main_campaign_side`; read only `STP_leader_health_stage`. The old `STP_state_face_stage` remains a migration mirror but no longer controls gameplay or UI. Format readiness and suspicion as whole 0–100 values rather than engine percentages of a 0–1 value.

- [ ] **Step 7: Run validators**

Run:

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section stp
python tools/validate_tc.py
```

Expected: unit tests, STP section, and baseline pass; no missing focus references or unsupported `cancel_effect`.

- [ ] **Step 8: Commit**

```powershell
git add -- common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt common/decisions/ADISCORD_STP_crisis_decisions.txt events/ADISCORD_STP_crisis_events.txt common/national_focus/ADISCORD_national_focus_STP.txt common/focus_inlay_windows/ADISCORD_STP_state_face_inlay_window.txt common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt localisation/russian/ADISCORD_stp_state_face_l_russian.yml tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: add Ivanov crisis calendar and focus windows"
```

### Task 4: Implement the two-slot STP operation game and adaptive opponent

**Files:**
- Create: `common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt`
- Modify: `common/decisions/ADISCORD_STP_crisis_decisions.txt`
- Modify: `events/ADISCORD_STP_crisis_events.txt`
- Modify: `common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt`
- Modify: `common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt`
- Modify: `common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt`
- Modify: `tools/stp_val_crisis_manifest.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces the timed slot flags `STP_major_operation_active` and `STP_aux_operation_active`, six family-adaptation variables, exact escrow variables, one active AI-resistance project, and fourteen player operations.
- Every operation start pays the real political/command/equipment/factory cost before setting its slot; every resolver calls central clamped effects and one cleanup effect.

- [ ] **Step 1: Add manifest and validator tests for all operation IDs**

Require these exact IDs:

```text
STP_operation_palace_channel
STP_operation_recruit_young_officers
STP_operation_mountain_caches
STP_operation_steal_black_ledger
STP_operation_silent_march
STP_operation_nodrul_disinformation
STP_operation_val_secret_channel
STP_operation_seal_palace
STP_operation_rotate_garrisons
STP_operation_targeted_raid
STP_operation_burn_client_archives
STP_operation_arm_festival_police
STP_operation_request_nodrul_advisers
STP_operation_false_val_channel
```

The validator must assert seven Shabrat and seven party operations, exact `days_remove` values from the design table, one and only one slot flag per operation, no direct `set_variable` for readiness/suspicion/nodes outside core effects, real stockpile removal before escrow increments, reachable set/clear paths for both loyalty flags, and an idempotent `STP_lose_shabrat` path that retires the character.

- [ ] **Step 2: Run the focused STP tests and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section stp`

Expected: all fourteen operation IDs and escrow/adaptation ownership checks fail.

- [ ] **Step 3: Add operation slots, prices, and temporary factory locks**

Use major slot for young officers, mountain caches, black ledger, Nodrul disinformation, garrison rotation, targeted raid, client-archive burning, and Nodrul advisers. Use auxiliary slot for palace channel, silent march, VAL channel, palace sealing, festival police, and false VAL channel.

Exact duration and base cost mapping:

| Operation | Days | Political | Command | Equipment | Factory lock |
|---|---:|---:|---:|---|---:|
| palace channel | 28 | 40 | 10 | none | 0 |
| young officers | 35 | 35 | 20 | 400 infantry, 50 support | 0 |
| mountain caches | 35 | 25 | 0 | 600 infantry, 50 support equipment as logistics kits | 0 |
| black ledger | 28 | 45 | 0 | none | 2 civilian |
| silent march | 21 | 30 | 0 | none | 1 civilian |
| Nodrul disinformation | 35 | 50 | 0 | 250 infantry or 25 convoys | 0 |
| VAL secret channel | 28 | 35 | 0 | none | 1 civilian |
| seal palace | 28 | 35 | 10 | none | 0 |
| rotate garrisons | 28 | 30 | 25 | none | 0 |
| targeted raid | 28 | 40 | 15 | none | 0 |
| burn client archives | 28 | 35 | 0 | none | 2 civilian |
| arm festival police | 21 | 30 | 0 | 300 infantry | 0 |
| request Nodrul advisers | 35 | 50 | 0 | none | 0 |
| false VAL channel | 28 | 35 | 0 | none | 1 civilian |

For every operation with a factory cost, put `civilian_factory_use = 1` or `civilian_factory_use = 2` in the active timed decision’s `modifier` block, matching the TFR China decision pattern. This reserves exactly one or two civilian factories only while that operation is active. `STP_clear_operation_slot` removes the operation/mission and therefore releases the exact reservation; do not approximate it with `consumer_goods_factor`.

- [ ] **Step 4: Implement conservative equipment escrow**

The total conversion replaces vanilla equipment and defines no `motorized_equipment`, so the truck price is represented by existing `support_equipment` logistics kits rather than an invalid equipment ID. Use `STP_resistance_escrow_infantry` and `STP_resistance_escrow_support`; do not create the obsolete design-only `STP_resistance_escrow_trucks`. Start effects test `num_equipment@infantry_equipment`, `num_equipment@support_equipment`, or convoys; subtract the exact reserved amount with `add_equipment_to_stockpile` using a negative count, then add the same literal amount to escrow. A failed start never sets a slot or delayed event.

Nodrul disinformation exposes two mutually exclusive start decisions, one paying 250 infantry equipment and one paying 25 convoys, so no runtime “or-price” ambiguity exists.

- [ ] **Step 5: Implement family adaptation and deterministic counterplay**

Families are palace, officers, mountains, market, street, and foreign. Each resolver:

1. reads the saved `STP_security_posture`;
2. reads the matching adaptation 0–3;
3. checks whether the relevant focus revealed the current countermeasure;
4. resolves as improved success, normal success, compromised success, or failure;
5. increments only that family’s adaptation through `STP_change_security_adaptation`;
6. applies +5 suspicion when the same family is reused at adaptation 1;
7. charges 25% extra political cost at adaptation 2;
8. at adaptation 3 sets a 35-day family block and publishes a hard-counter tooltip.

Exact posture vulnerabilities:

```text
1 total surveillance: counters street, vulnerable to palace, observed as censorship and march surveillance
2 targeted arrests: counters palace, vulnerable to mountains, observed as missing couriers
3 garrison rotation: counters officers, vulnerable to market, observed as unit and commander transfers
4 mass purge: counters mountains, vulnerable to street, observed as raids and falling army experience
5 false tolerance: counters market, vulnerable to officers, observed as suspiciously free intermediaries
```

No branch gives a node solely from readiness. Successful results call exactly one of `STP_change_node_palace`, `STP_change_node_officers`, `STP_change_node_mountains`, `STP_change_node_market`, `STP_change_node_street`, or `STP_change_node_val_channel`; compromised results give the node only with +10 suspicion; failures add 8–15 suspicion or reduce readiness.

A successful `STP_operation_targeted_raid` against a discovered cache applies the exact escrow conservation split separately to infantry and support equipment: 50% is removed from escrow and returned to the party state’s real stockpile, 25% is removed and explicitly recorded as destroyed, and 25% remains in resistance escrow. The resolver snapshots the pre-raid amount, performs the 50/25/25 arithmetic once, and sets a one-shot raid token so save/reload cannot repeat the transfer.

Loyalty and leader reachability are explicit:

```text
successful palace channel with STP_focus_final_palace_move_open, palace 2, suspicion <=35 -> set STP_capital_guard_loyal_to_resistance
successful seal-palace operation with STP_focus_final_palace_lock_open -> clear that guard flag
successful young-officer operation with STP_focus_final_garrison_move_open and officers 2+ -> set STP_garrison_88_loyal_to_resistance
successful garrison rotation with STP_focus_final_garrison_lock_open -> clear that state-88 flag
successful targeted raid against a revealed palace channel at suspicion 75+ -> call STP_lose_shabrat
failed/compromised palace operation at suspicion 90+ -> call STP_lose_shabrat
```

`STP_lose_shabrat` is idempotent: it requires `STP_shabrat_available`, clears it, sets `STP_shabrat_lost`, and runs `retire_character = STP_maksim_shabrat`. It does not create Sotnikov readiness; the separately paid officers/mountains/escrow trigger must still qualify. Full crisis cleanup clears temporary loyalty flags, while the lost flag persists through outcome selection.

- [ ] **Step 6: Implement the party player's active AI-resistance cycle**

After `STP_commit_to_party`, schedule `stp_crisis.40` every 28 days until `STP_ivanov_dead`. Only one of these exact project flags can exist:

```text
STP_resistance_project_palace
STP_resistance_project_garrison_theft
STP_resistance_project_mountain_smuggling
STP_resistance_project_street_agitation
STP_resistance_project_external_contract
```

The start event shows a qualitative signal. A matching player counter-operation sets `STP_resistance_project_countered`; the delayed resolver checks it and either cancels/reduces the project or applies its paid result. Theft is capped at both 20% of the actual stockpile and 300 infantry/30 support; smuggling is capped at 400 infantry/30 support logistics kits and cannot create equipment when neither STP nor an open VAL sender can pay.

Posture 1 prioritizes the palace project, posture 2 garrison theft, posture 3 alternates mountain smuggling and street agitation according to the weaker preserved node, and posture 4 prioritizes the external contract with street agitation as its unpaid fallback. Resolver tests assert that the saved posture changes weights but is never mutated.

- [ ] **Step 7: Add the bloodless-coup and viable-network triggers**

`STP_can_attempt_bloodless_coup` requires side commitment 1, `STP_shabrat_available`, palace exactly 2, `STP_capital_guard_loyal_to_resistance`, officers at least 2, market exactly 2, readiness at least 85, suspicion at most 20, and `NOD_can_directly_defend_stp = no`.

`STP_resistance_network_is_viable` requires readiness at least 40, two of palace/officers/mountains/market/street above zero, and either 800 infantry in escrow or officers at least 2. `STP_sotnikov_network_is_viable` requires `STP_shabrat_lost` and absence of `STP_shabrat_available`, readiness at least 45, officers at least 2, mountains at least 1, and 1000 infantry in escrow.

- [ ] **Step 8: Run validators and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section stp
python tools/validate_tc.py
git diff --check
git add -- common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt common/decisions/ADISCORD_STP_crisis_decisions.txt events/ADISCORD_STP_crisis_events.txt common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: add adaptive Stelander crisis operations"
```

### Task 5: Materialize the internal outcome, civil war, and postwar campaign

**Files:**
- Create: `common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt`
- Create: `common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt`
- Create: `common/national_focus/ADISCORD_national_focus_STP_postwar.txt`
- Modify: `events/ADISCORD_STP_crisis_events.txt`
- Modify: `common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt`
- Modify: `common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt`
- Modify: `tools/stp_val_crisis_manifest.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces `STP_crisis_main_side`, `STP_crisis_party_side`, `STP_crisis_resistance_side`, and finally `STP_postwar_country` as global event targets.
- All four death outcomes and both no-war consolidations end through `STP_finalize_internal_outcome`.

- [ ] **Step 1: Add outcome-matrix and conservation tests**

Require eight literal `army_ratio` values split into the two role-dependent tables:

```text
resistance is revolter: 0, 0.2, 0.35, 0.5
party is revolter: 1, 0.8, 0.65, 0.5
```

Tests must reject arithmetic inside `army_ratio`, arbitrary division deletion, unguarded global targets, missing `load_focus_tree`, missing finalizer calls from bloodless/party-success/party-fail/civil-war completion, and any escrow transfer without zeroing the source variable.

- [ ] **Step 2: Run the civil-war validator and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section civil_war`

Expected: missing war effects, role tree, postwar tree, and finalizer paths.

- [ ] **Step 3: Implement the guarded split**

Before `start_civil_war`:

1. save the literal main STP as `STP_crisis_main_side`;
2. record whether a Capital Guard division exists;
3. if it exists, disband only template `Capital Guard` with `disband = yes`;
4. snapshot free infantry/support stockpiles after the returned equipment;
5. remove both internal sides from factions and record whether the NOD mandate must be restored;
6. set the main side ruling group to chauvinism or etatism for resistance, or hedonism for party;
7. select one of the four literal ratios from officers 0/1/2/3;
8. start the civil war with the opponent’s actual ideology group;
9. find the new internal country through `original_tag = STP`, civil-war relation, and absence of `STP_main_campaign_side`, then save its exact role target.

Immediately load `ADISCORD_STP_crisis_war_focus` with `keep_completed = no` on the temporary side and clear any copied main-role/calendar flags.

- [ ] **Step 4: Materialize a deterministic node-to-state map**

Use `size = 0` and explicit starter states: a resistance revolter starts with 43; a party revolter starts with 1, 2, 3, and 28. Immediately after both global role targets exist, `STP_apply_civil_war_state_map` enforces:

```text
party always: states 1, 2, 3
resistance palace package: state 28 only at palace 2 plus loyal Capital Guard
resistance officer package: state 29 at officers 1+
resistance mountain package: state 43 at mountains 1, state 44 at mountains 2, state 53 at mountains 3
resistance market package: state 45 at market 2
resistance street package: state 46 at street 1+
resistance resource-garrison package: state 88 only with STP_garrison_88_loyal_to_resistance
```

Every contestable state not earned by the resistance is transferred to the saved party side. If no resistance condition grants a state, transfer fallback state 43 to resistance so the war remains valid, but set `STP_resistance_isolated_fallback` and no preparation bonus. Set party capital to 28 when it owns Fada, otherwise 1; set resistance capital by priority 28, 29, 43, 44, 45, 46, 53, 88. Tests snapshot all eleven STP owners before the split and assert that after mapping every state is owned by exactly one saved internal side, with no random state outside the manifest.

- [ ] **Step 5: Normalize only free stockpiles and paid node packages**

Do not delete or recreate normal divisions. Reconcile the two free stockpiles to the saved total after the engine split; transfer the exact resistance escrow once and clear both escrow variables. If Capital Guard existed, create one empty locked guard on the side selected by `STP_capital_guard_loyal_to_resistance`; otherwise create none.

Materialize the remaining nodes exactly:

```text
officers 1: ratio table plus 10 command power and 30-day +5% planning idea
officers 2: ratio table plus 20 command power, 60-day +7.5% planning idea, Sotnikov/loyal junior-command package
officers 3: ratio table plus 30 command power, 90-day +10% planning idea, full loyal-command package
mountains 1/2/3: up to one empty mountain militia per level, each requiring 600 paid infantry equipment in the transferred escrow
street 1/2: up to one empty urban militia per level, each requiring 400 paid infantry equipment not already committed to mountain militia
market 1: 90-day party sabotage mission with civilian_factory_use = 1
market 2: state 45 plus a conservative transfer of up to 200 infantry and 50 support from the party’s actual post-split stockpile
palace 2 plus loyal guard: the single empty Capital Guard described above
```

Mountain packages are paid before street packages so the order is deterministic and displayed in the pre-split tooltip. If paid escrow is insufficient, skip the last militia rather than create equipment. Character and general assignment uses fixed role flags, not engine-random ownership. Conservation tests include the market transfer, both militia families, all officer tiers, and both Capital Guard existence cases.

- [ ] **Step 6: Resolve Ivanov's death through the exact matrix**

Evaluation order:

```text
side 1 + bloodless trigger -> Shabrat no-war outcome
side 1 + Shabrat available + viable network -> Shabrat main-side civil war
side 1 + Sotnikov viable -> Sotnikov main-side civil war
side 1 + neither viable -> Hedersett fail-state, no war
side 2 + network not viable -> Hedersett successful consolidation, no war
side 2 + Shabrat available + viable network -> Hedersett main, Shabrat revolter
side 2 + Sotnikov viable -> Hedersett main, Sotnikov revolter
```

The bloodless route removes `autonomy_shadow_state` and NOD faction membership. Hedersett’s successful no-war consolidation preserves the current mandate. The Shabrat-player fail-state sets `STP_underground_crushed_fail_state`, loses 10% stability, clears officers, and uses the Hedersett postwar route.

- [ ] **Step 7: Implement one finalizer and guarded completion hooks**

`STP_finalize_internal_outcome` runs in the actual winner scope, saves `STP_postwar_country`, sets `STP_postwar_campaign_side`, calls `STP_set_crisis_phase = { value = 3 }`, clears main/party/resistance temporary roles, assigns Shabrat/Sotnikov/Hedersett and ruling group, loads `ADISCORD_STP_postwar_focus`, marks exactly one of `STP_The_Mountain_Window` for Shabrat, `STP_No_One_Controls_The_Transition` for Sotnikov, or `STP_The_Party_Closes_Ranks` for Hedersett by event, calls external-participant cleanup, clears the three crisis targets, and starts the canonical VAL countdown interface.

Before clearing `STP_nodrul_mandate_pending`, the finalizer consumes it. A Hedersett winner restores `autonomy_shadow_state` and rejoins NOD’s existing faction only when NOD exists, has not capitulated or lost a corridor state, and the mandate was pending. A Shabrat or Sotnikov winner uses NOD’s `set_autonomy` scope to set the saved postwar country to `autonomy_free`, removes it from every faction, and permanently sets `STP_nodrul_mandate_broken`. Hedersett after a defeated/missing NOD also remains free and marks the mandate broken. The no-war Hedersett consolidation keeps the already-active mandate without recreating it.

At this checkpoint define safe forward interfaces in the war-effects file: `VAL_STP_start_war_countdown` records `VAL_STP_countdown_pending` plus the selected 120/180/300/450 type, and `VAL_STP_trigger_breach` records `VAL_STP_breach_pending`. They do not call undefined missions. Task 9 replaces their bodies with canonical mission activation and consumes any pending flag, so Tasks 5 and 8 stay parser-valid and green before the timer layer exists.

For the bloodless coup, successful party consolidation, and Shabrat-player failed no-war consolidation, the finalizer also sets `VAL_STP_deferred_invoice_window` on the saved postwar country for exactly 60 days while starting the default 120-day countdown interface. Civil-war outcomes do not receive this window. Expiry clears the flag; accepting, refusing, or completing the deferred-invoice negotiation consumes it immediately.

Call it from bloodless coup, both no-war consolidations, guarded `on_peace`, guarded `on_capitulation`, and a three-day fallback event. The handlers first confirm a saved internal role and never infer the winner from `FROM`, because VAL or NOD can be the capitulation recipient.

- [ ] **Step 8: Add the minimal war tree and exact 15-focus postwar tree**

The temporary tree has only:

```text
STP_Crisis_Rally_The_Provinces
STP_Crisis_Secure_The_Depots
STP_Crisis_Hold_The_Capital_Road
STP_Crisis_Request_External_Supplies
```

Each costs 5, is role-gated, and grants small logistics/command effects without restarting the health calendar.

The postwar tree uses the fifteen exact IDs in `POSTWAR_FOCUS_IDS`, costs 5, and gates each route by winner flag. Encode the design results exactly: Shabrat gets surviving-regiment normalization, archives, mandate break, one-step deal improvement, and fortifications in controlled 43/45/88; Sotnikov gets military committee, general staff, forts in 1/2, and a mutually exclusive primary plan against VAL or NOD; Hedersett gets party stabilization, lists-versus-purge choice, mandate-versus-deferred-invoice choice, and capital-army recovery. `STP_underground_crushed_fail_state` blocks `STP_Hedersett_The_Party_After_The_Father`.

- [ ] **Step 9: Validate and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section civil_war
python tools/validate_tc.py
git diff --check
git add -- common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt common/national_focus/ADISCORD_national_focus_STP_crisis_war.txt common/national_focus/ADISCORD_national_focus_STP_postwar.txt events/ADISCORD_STP_crisis_events.txt common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: add Stelander succession outcomes and civil war"
```

### Task 6: Add contextual Nodrul posture, distractions, and intervention

**Files:**
- Create: `common/decisions/ADISCORD_NOD_crisis_decisions.txt`
- Create: `events/ADISCORD_NOD_crisis_events.txt`
- Modify: `events/ADISCORD_STP_crisis_events.txt`
- Modify: `common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt`
- Modify: `common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt`
- Modify: `common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt`
- Modify: `common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt`
- Modify: `tools/stp_val_crisis_manifest.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces exactly one posture flag among guardian, YPR, COF, Beshay, wait; one 35-day escalation mission; guarded limited-war participant/generation flags; and three levels of STP support.

- [ ] **Step 1: Add NOD posture and limited-war tests**

Tests require all five posture flags, corridor checks for NOD states 10/11 and STP states 1/2, four exact timeout values 240/180/120/120, no territorial transfer, no permanent faction, and no global `skip_default_capitulation`. The `abort_when_not_enabled = yes` assertion is introduced with the AI file in Task 11.

- [ ] **Step 2: Run the NOD validator and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section nod`

Expected: missing posture, escalation, participant, and cleanup contracts.

- [ ] **Step 3: Select and lock an event-driven posture**

At initialization and each health-stage event call `NOD_select_crisis_posture`. It clears all five posture flags, calculates weights from current wars, army strength, stockpile, STP mandate, discovered Shabrat activity, and `STP_nodrul_disinformation_bias`, then sets one flag for at least the current 63–70 day stage.

Re-evaluate only on health stage, start/end of war, faction break, Ivanov death, capitulation, or disappearance of a target. Attacks against NOD, NOD capitulation, and missing targets may invalidate the lock immediately.

- [ ] **Step 4: Implement 35-day escalation missions and exact eligibility**

YPR requires both countries at peace with each other’s prospective coalition, no external faction/guarantee on YPR, control of 15/19, and NOD strength ratio at least 0.9. COF requires control of 14 and ratio 1.1. BHG requires control of 5 and ratio 1.25. BBV requires control of 7, ratio 1.25, and absence from faction BJK.

At mission timeout repeat every eligibility check before declaring a limited war. STP is not called. Set bilateral participant flags only after all checks pass. BBV inside BJK receives only the ultimatum/border event.

- [ ] **Step 5: Implement guarded limited peace**

Victory requires NOD control of 15 and 19 for 30 days, control of 14 for 30 days, or control/accepted concession for 5 or 7. Use generation-token flags for the 30-day control check. Results grant only:

```text
YPR: 365-day trade-rights modifier and demilitarization modifier for 15/19
COF: reparations modifier and demilitarization modifier for 14
BHG or BBV: 180-day trade concession and non-aggression pact
```

No state owner changes. Timeouts are 240/180/120/120 days and end in addressed white peace if unresolved. Third-party entry invokes an addressed emergency white peace for the saved NOD/target pair and clears only this limited-conflict state.

- [ ] **Step 6: Compute attention and support STP**

Save NOD deployed manpower at war start. Mark a Pyrrhic result if NOD losses exceed 8% of that value or its loss ratio is worse than 1.5. `NOD_can_directly_defend_stp` requires guardian posture, no other war, not capitulated, at least 85% army equipment, strength ratio to STP at least 0.8, and control of states 10 and 11.

Support levels:

```text
material: paid stockpile transfer only
limited: paid transfer plus temporary adviser/supply idea
full: add_to_war on the saved party side plus temporary military access
```

Full intervention never adds NOD or STP to a permanent faction during the internal war. Winning without Pyrrhic losses raises attention; a 180-day stalemate, white peace, defeat, or lost corridor lowers it. STP disinformation only changes posture weights and never directly starts a neighboring war.

- [ ] **Step 7: Validate and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section nod
python tools/validate_tc.py
git diff --check
git add -- common/decisions/ADISCORD_NOD_crisis_decisions.txt events/ADISCORD_NOD_crisis_events.txt events/ADISCORD_STP_crisis_events.txt common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: add contextual Nodrul crisis behavior"
```

### Task 7: Turn VAL's empty tree and static idea into a contract-state campaign

**Files:**
- Modify: `common/national_focus/ADISCORD_national_focus_VAL.txt`
- Modify: `common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt`
- Modify: `common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt`
- Modify: `common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt`
- Modify: `tools/stp_val_crisis_manifest.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces one selected arsenal model, mercenary doctrine, ash model, and northern approach; opens the external-operation board; unlocks exactly one crisis strategy after STP reaches rupture.

- [ ] **Step 1: Add focus-graph and spirit-band tests**

Require every existing VAL focus ID, cost 5, non-empty reward, exact mutual exclusions, and four AND prerequisite alternatives for `VAL_Contracts_Outlive_Kings`:

```text
VAL_One_Ledger_One_Banner + VAL_Export_Rifles_Not_Promises
VAL_One_Ledger_One_Banner + VAL_Morns_Supply_Trains
VAL_One_Ledger_One_Banner + VAL_Dead_Villages_Still_Count
VAL_One_Ledger_One_Banner + VAL_Different_Views_On_Freedom
```

Require the five authority bands 0–24, 25–49, 50–74, 75–89, 90–100 and forbid volunteer modifiers.

- [ ] **Step 2: Run the VAL validator and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section val`

Expected: empty rewards, wrong prerequisites, absent crisis branch, and incomplete dynamic modifier.

- [ ] **Step 3: Implement central and specialization rewards**

Exact strategic mapping:

```text
VAL_The_Contract_State: open VAL board, authority +5
VAL_The_Weaponry_Baron: authority +10
VAL_Price_Of_Loyalty: unlock captain-retainer decisions
VAL_Count_The_Captains: reveal negotiation posture
VAL_One_Ledger_One_Banner: unlock foreign operations

VAL_Factories_Like_Cathedrals: 365-day +10% military-factory construction idea
VAL_Keep_The_Lines_Hot: permanent +3% production-factory efficiency cap idea
VAL_Ballistics_Schools: quality arsenal flag, +1 research bonus for infantry weapons
VAL_Brokered_Steel: broad resource-network flag, foreign-operation PP cost -10
VAL_Export_Rifles_Not_Promises: supply-contract flag, authority +5

VAL_The_Mercenary_State: 10 army experience and doctrine-choice unlock
VAL_Hire_Out_War: foreign-contract decision unlock and 50 political power
VAL_Vorons_Companies: covert-intervention doctrine
VAL_Stahls_Schedules: sustained-supply doctrine
VAL_Gromovs_Assault_Tables: resource-raider doctrine
VAL_Morns_Supply_Trains: supply preparation and authority +5

VAL_The_Harvest_Of_Ash: ash-model unlock and +5% war support
VAL_Field_Surgeons: manpower-preservation model
VAL_Bread_From_Barracks: rear-mobilization model
VAL_Dead_Villages_Still_Count: finish selected ash model and authority +5

VAL_Market_Roads_North: northern-intelligence unlock and 365-day +10% infrastructure construction idea
VAL_Trading_Partners: open-market northern approach
VAL_October_Of_2160: coercive northern approach
VAL_Different_Views_On_Freedom: unlock northern operations and authority +5
```

`VAL_Ballistics_Schools` and `VAL_Brokered_Steel` are mutually exclusive. The three company doctrines are pairwise mutually exclusive. `VAL_Field_Surgeons` and `VAL_Bread_From_Barracks` are mutually exclusive. `VAL_Trading_Partners` and `VAL_October_Of_2160` are mutually exclusive. Their join focuses use OR prerequisites.

- [ ] **Step 4: Implement the exact contract-state bands**

Set backing variables to the design table:

```text
0–24: org +3%, org regain +2%, daily PP -0.10
25–49: attack/defence +3%, org +5%, regain +3%, capture +2%, planning -5%, daily PP -0.10
50–74: attack +6%, defence +5%, org +8%, regain/capture +5%, supply -3%, planning -5%, state-overload +3%
75–89: attack +10%, defence +8%, org +10%, regain/capture +8%, supply -5%, planning -10%, daily PP -0.20, state-overload +5%
90–100: attack +12%, defence +10%, org +12%, regain/capture +10%, supply -7%, planning -15%, daily PP -0.25, stability -5%, state-overload +8%
```

At 50/75/90 also set trade and military-industry income factors plus army-expense reductions to 3/5/7%. Call `force_update_dynamic_modifier = yes` only after a real authority-band change.

- [ ] **Step 5: Add the dynamic crisis branch**

Add these exact focus IDs:

```text
VAL_Offer_The_Mountain_Contract
VAL_Secure_The_Resource_Corridor
VAL_Negotiate_The_Deferred_Invoice
VAL_Let_Nodrul_Bleed
VAL_Present_The_Final_Invoice
```

The first four are pairwise mutually exclusive. The branch uses `allow_branch` requiring `VAL_Contracts_Outlive_Kings` and STP crisis phase at least rupture; each phase change calls `mark_focus_tree_layout_dirty`.

`VAL_Offer_The_Mountain_Contract` and `VAL_Secure_The_Resource_Corridor` additionally require an active saved STP civil war. `VAL_Negotiate_The_Deferred_Invoice` requires a finalized no-war outcome and active `VAL_STP_deferred_invoice_window`. `VAL_Let_Nodrul_Bleed` is the fallback preparation route. `VAL_Present_The_Final_Invoice` requires `STP_postwar_country` and modifies preparation only; it never creates, cancels, or extends the canonical war timer.

- [ ] **Step 6: Validate and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section val
python tools/validate_tc.py
git diff --check
git add -- common/national_focus/ADISCORD_national_focus_VAL.txt common/dynamic_modifiers/ADISCORD_STP_VAL_crisis_dynamic_modifiers.txt common/scripted_effects/ADISCORD_STP_VAL_crisis_core_effects.txt common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: build Kefreyt contract-state focus campaign"
```

### Task 8: Implement VAL influence, the mountain deal, and resource corridor

**Files:**
- Create: `common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt`
- Create: `common/decisions/ADISCORD_VAL_contract_decisions.txt`
- Create: `events/ADISCORD_VAL_contract_events.txt`
- Modify: `common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt`
- Modify: `common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt`
- Modify: `common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt`
- Modify: `tools/stp_val_crisis_manifest.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Owns the single `VAL_foreign_operation_active` slot, STP family exposure, northern family memory, leverage floors, deal concessions/obligations, and guarded corridor campaign.

- [ ] **Step 1: Add operation/deal validator tests**

Require five STP operation IDs and fifteen northern operation IDs. For CIN, OSF, and APH the suffixes are exactly `study_market`, `arms_brokerage`, `infrastructure_concession`, `hire_local_captain`, and `prepare_separate_terms`.

Tests must reject parallel slot ownership, an STP operation start during `VAL_STP_target_cooldown`, a resolver that does not set that cooldown for 42 days, a missing or rerollable four-value `VAL_negotiation_posture`, a VAL resolver that ignores the saved STP security/resistance posture, a deferred negotiation outside its 60-day flag or one that fails to replace 120 with 180/300/450, leverage above 40 from only one successful family, leverage above 70 without a deal/control/ownership asset, influence 3 without two successful families, repeated-family blocks without 90-day expiry, and any deal cleanup that omits resource rights, access, factory locks, or obligation flags.

- [ ] **Step 2: Run VAL and north validators and verify RED**

```powershell
python tools/validate_adiscord_stp_val_crisis.py --section val
python tools/validate_adiscord_stp_val_crisis.py --section north
```

Expected: missing shared-slot operations, exposure, leverage floors, and deal state.

- [ ] **Step 3: Implement the five STP influence operations**

At STP rupture, or at the first earlier channel opening when the value is still 0, select `VAL_negotiation_posture` exactly once: 1 cautious broker, 2 predatory concessionaire, 3 fear of direct NOD reaction, or 4 double game. Weights read VAL authority/doctrine, NOD readiness, STP viability, and actual stocks. Refusal, counteroffer, operation result, focus completion, and save/reload never clear or reroll it; only final campaign cleanup does.

Exact IDs and rules:

```text
VAL_STP_map_mountain_passes: 25 PP, 28d, intelligence over states 43/44/45/88 plus one saved STP/NOD posture clue, no leverage
VAL_STP_build_contractor_depot: 35 PP and up to 300 paid infantry equipment, 35d
VAL_STP_offer_mountain_concession: 40 PP and one civilian-factory lock, 35d
VAL_STP_buy_border_officers: 45 PP, 20 CP, 100 paid support equipment, 35d, leverage 20
VAL_STP_test_nodrul_red_line: 30 PP, 28d, intelligence only
```

Use `VAL_STP_exposure_intel`, `VAL_STP_exposure_supply`, `VAL_STP_exposure_concession`, `VAL_STP_exposure_garrison`, and `VAL_STP_exposure_nodrul`, each clamped 0–3. The first repeat adds 10 PP, the second enables a target counter-operation, and the third sets that family’s 90-day block and informs NOD. Successful map/red-line operations never add leverage.

Every final STP-operation result—success, compromise, refusal, or failure—sets `VAL_STP_target_cooldown` for exactly 42 days before calling `VAL_clear_foreign_operation`. All five STP operation starts require the cooldown to be absent. A negotiation chain sets the same cooldown only when the chain accepts, refuses, times out, loses viability, or loses its target, not between its internal offer steps.

The resolver uses `STP_security_posture` when VAL pressures the party apparatus, `STP_resistance_posture` when VAL contacts the underground during the party route, and an explicit response event for a human target. It also reads the saved VAL negotiation posture: cautious favors supply-only terms, predatory demands one extra concession and prefers a weak NOD, fear-of-NOD refuses direct intervention while `NOD_can_directly_defend_stp` is true, and double-game can contact either side but demands a resource/client asset and raises foreign exposure.

After every leverage loss, `VAL_recalculate_stp_leverage_floor` enforces 10 for each live resource-rights state, 15 for a live client garrison, and 25 for formal ownership of each of states 45/88. A regime change reduces every exposure by one and halves leverage not protected by this floor.

- [ ] **Step 4: Implement the fifteen northern operations**

For each literal country prefix `VAL_CIN`, `VAL_OSF`, and `VAL_APH`, create:

```text
study_market: 30 PP, 28d, no influence
arms_brokerage: 25 PP and up to 400 paid infantry equipment, 35d
infrastructure_concession: 45 PP and two civilian-factory locks, 35d
hire_local_captain: 35 PP, 15 CP, 80 paid support equipment, 28d, influence at least 1
prepare_separate_terms: 50 PP and one civilian-factory lock, 35d, influence at least 2 and two successful families
```

Each target stores posture 1 open market, 2 forceful control, 3 national consolidation, or 4 desperate supply search. Human targets answer an event; AI posture is selected once from current war, stockpile, relations, and NOD threat. The exact target gets a 70-day cooldown after resolution.

Track `last_family`, `repeat_streak`, and `blocked_family` separately for CIN/OSF/APH. Switching family resets streak to 1 but never removes an old timed block. Nationalization, garrison rotation, regime change, or exposed double-dealing lowers influence by one and removes the matching client.

Every listed VAL factory reservation uses the active decision or hidden obligation mission modifier `civilian_factory_use = 1` or `civilian_factory_use = 2`; no reservation is modeled as a consumer-goods percentage.

- [ ] **Step 5: Implement the mountain-deal negotiation chain**

Opening the channel reserves the common foreign slot and saves `STP_val_contract_partner`. The chain has exactly five states: channel, viability proof, concession selection, VAL offer, accept/counter/delay. The first offer times out in 35 days; only one counteroffer is allowed and times out in 21 more days. Any timeout, refusal, disappearing side, or failed viability recheck calls `VAL_clear_foreign_operation`.

Viability requires two controlled STP core states, three divisions at 60% average equipment, less than 65% surrender progress, and either two prepared nodes or 30% of prewar STP victory points.

Exact concession flags:

```text
VAL_STP_concession_resource_45
VAL_STP_concession_resource_88
VAL_STP_concession_arms_debt
VAL_STP_concession_transit
VAL_STP_concession_advisers
VAL_STP_concession_postwar_contracts
```

Supply pact requires one concession and yields 180 days. Intervention contract requires two and yields 300 days. Concession protectorate requires three, including resource rights or actual control of 45/88, and yields 450 days. Direct intervention calls `add_to_war` only after a final viability check and cannot support a party side already receiving direct NOD military support.

The no-war deferred-invoice path is available only during `VAL_STP_deferred_invoice_window`, gives no retroactive supplies or intervention, and maps one/two/three accepted concessions to 180/300/450. Acceptance clears the 60-day window and calls `VAL_STP_start_war_countdown` with the selected type, replacing the already-pending 120-day countdown; refusal or expiry clears the window and leaves 120 unchanged. Tests require the replacement to invalidate the old mission/token once Task 9 is present, so stale D-14/D-1 events from the 120-day generation cannot fire.

- [ ] **Step 6: Implement real obligations and resource-rights lifecycle**

`VAL_STP_resource_rights_active`, `VAL_STP_resource_rights_45`, and `VAL_STP_resource_rights_88` point to the saved contract partner and call engine resource rights for state 45 and/or 88. Arms debt creates three dated missions at postwar days 30, 90, and 150; each payment removes 400 infantry and 50 support from STP before adding them to VAL. One missed payment adds debt/leverage; two call the breach interface.

Transit grants military access until internal peace plus 90 days or final warning. Advisers cost VAL 20 CP, activate a hidden STP obligation mission with `modifier = { civilian_factory_use = 1 }`, apply daily PP -0.05 and a supply/planning idea until internal peace plus 180 days or warning. Postwar contracts apply paired modifiers for 166/286/436 days inside the 180/300/450 countdown.

`VAL_STP_cleanup_contract_relations` removes state 45/88 resource rights, NAP/truce when requested by the timer phase, military access, paired ideas, factory locks, obligation missions, partner target, and every temporary deal flag. Formal transfer to VAL removes the corresponding resource right immediately.

- [ ] **Step 7: Implement the guarded resource-corridor campaign**

Only an active STP civil war and the selected corridor focus can start it. Save the actual owners/controllers of 45 and 88. If one internal side owns both, save full mode and require VAL control of both for 30 days. If ownership is split, human VAL selects one state; AI chooses the reachable state with greater resource value/force ratio. Set `VAL_resource_corridor_attempted` so the second state cannot be attacked through this mechanic.

After the 30-day generation-token check, offer formal concession. Acceptance transfers only the saved target states, preserves STP cores, grants no VAL cores, and cleans resource rights. Refusal continues the limited war. The campaign never transfers control without physical occupation and never opens against a unified STP.

- [ ] **Step 8: Validate and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section val
python tools/validate_adiscord_stp_val_crisis.py --section north
python tools/validate_tc.py
git diff --check
git add -- common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt common/decisions/ADISCORD_VAL_contract_decisions.txt events/ADISCORD_VAL_contract_events.txt common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt common/scripted_triggers/ADISCORD_STP_VAL_crisis_triggers.txt common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: add Kefreyt influence and mountain contracts"
```

### Task 9: Make the final VAL–STP war unavoidable with one canonical timer

**Files:**
- Modify: `common/decisions/ADISCORD_VAL_contract_decisions.txt`
- Modify: `events/ADISCORD_VAL_contract_events.txt`
- Modify: `common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt`
- Modify: `common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt`
- Modify: `common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt`
- Modify: `tools/stp_val_crisis_manifest.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces exactly one active mission among 120/180/300/450/breached, finite token flags, D-14 and D-1 events, and `STP_VAL_begin_final_war`.

- [ ] **Step 1: Add timer ownership/token tests**

Require:

```text
STP_VAL_war_countdown_120
STP_VAL_war_countdown_180
STP_VAL_war_countdown_300
STP_VAL_war_countdown_450
STP_VAL_war_countdown_breached
```

Tests enforce one mission owner through `STP_VAL_war_countdown_category`: human postwar STP, otherwise human VAL, otherwise VAL. Require D-14 and D-1 delayed events with matching finite generation-token flags, timeout declaration, 14-day breach, and cleanup before declaration. Reject a focus-only declaration path and reject treating truce as a `diplomatic_relation`.

- [ ] **Step 2: Run the VAL validator and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section val`

Expected: missing canonical missions, tokens, warning offsets, and declaration cleanup.

- [ ] **Step 3: Implement normal countdowns**

Replace the Task 5 forward body of `VAL_STP_start_war_countdown` and consume `VAL_STP_countdown_pending`. No deal selects 120; supply pact selects 180; intervention selects 300; protectorate selects 450. Clear every prior timer/token, set the exact type variable and one token flag, activate the mission on the canonical owner, schedule D-14 and D-1 events, and notify the other country.

D-14 rechecks the token and active mission, sets `VAL_STP_final_warning_active`, removes old resource rights and expiring advisers/contracts, and publishes the final deployment warning. D-1 rechecks again: remove the non-aggression pact with `diplomatic_relation = { country = event_target:STP_postwar_country relation = non_aggression_pact active = no }`, and separately expire the truce with `set_truce = { target = event_target:STP_postwar_country days = 0 }`. Timeout repeats both operations and calls `STP_VAL_begin_final_war`.

Before wiring every timer, run a focused debug smoke test proving that `days = 0` makes `has_truce_with` false on the next tick in HOI4 1.19. If the runtime does not clear it, do not invent `remove_truce` or `relation = truce`; keep the mission/NAP as the protection mechanism and omit engine truce creation entirely. Record the chosen supported path in the validator fixture.

- [ ] **Step 4: Implement breach without extending the deadline**

Replace the Task 5 forward body of `VAL_STP_trigger_breach` and consume `VAL_STP_breach_pending`. Before final warning, a material breach clears the normal token/mission and starts a 14-day `STP_VAL_war_countdown_breached`; warning is immediate and diplomatic protection is removed on day 13. If breach occurs after D-14, call `STP_VAL_begin_final_war` immediately.

`STP_VAL_begin_final_war` removes state resource rights, NAP through `diplomatic_relation`, the confirmed supported truce path separately, military access through `diplomatic_relation`, direct civil-war intervention flags, foreign-operation slot, deal ideas, and stale war goals, calls `STP_set_crisis_phase = { value = 4 }` in the saved postwar scope, then declares VAL on `STP_postwar_country`. It never depends on `VAL_Present_The_Final_Invoice`.

- [ ] **Step 5: Add early-aggression NOD reaction**

The narrow `on_war_relation_added` handler checks literal attacker VAL and a pre-rupture STP defender. If NOD exists, is not capitulated or in a defensive war, has at least 70% equipment, and is not Pyrrhic, it either joins the exact STP side with `add_to_war` or, while a limited campaign is active, receives the choice to end that campaign or send a paid material package. It never creates reserves or revives a defeated NOD.

- [ ] **Step 6: Validate and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section val
python tools/validate_tc.py
git diff --check
git add -- common/decisions/ADISCORD_VAL_contract_decisions.txt events/ADISCORD_VAL_contract_events.txt common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt common/scripted_effects/ADISCORD_STP_VAL_crisis_war_effects.txt common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: enforce the final Kefreyt Stelander war"
```

### Task 10: Replace the unsafe northern test peace with a guarded campaign

**Files:**
- Modify: `common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt`
- Modify: `common/decisions/ADISCORD_VAL_contract_decisions.txt`
- Modify: `events/ADISCORD_VAL_contract_events.txt`
- Modify: `common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt`
- Modify: `common/on_actions/00_on_actions.txt`
- Modify: `common/decisions/ADISCORD_test_wars_decisions.txt`
- Modify: `common/decisions/categories/ADISCORD_test_wars_categories.txt`
- Modify: `common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt`
- Modify: `localisation/russian/ADISCORD_test_wars_l_russian.yml`
- Modify: `tools/stp_val_crisis_manifest.py`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces full/partial northern modes, one 210-day mission, per-target locks, permanent attempted flag, contamination guard, and addressed cleanup.

- [ ] **Step 1: Add northern eligibility and peace tests**

Require full mode at CIN influence at least 2 and OSF influence at least 2, partial CIN or OSF mode only when exactly one eligible prepared target exists, literal targets 59 and 61, 210-day mission, 30-day control tokens, `VAL_northern_campaign_attempted`, and irreversible contamination for that campaign.

Tests reject subject/faction/guaranteed/external-war starts, automatic APH war entry, transfers without saved owner plus VAL control plus participant plus one-shot lock, and any remaining old global capitulation block or VAL test-war decisions. They also require the edited `ADISCORD_test_wars_l_russian.yml` to remain UTF-8 BOM with one `l_russian:` header.

- [ ] **Step 2: Run the north validator and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section north`

Expected: missing modes/guards plus detection of the old unsafe handler and test decisions.

- [ ] **Step 3: Implement exact start windows**

All targets must exist, be independent, non-capitulated, control their required start states, have no external war, faction, or guarantee, and pass the same checks immediately before declaration.

Human VAL can start only while there is no final warning and either:

```text
active balanced STP civil war: each side controls at least two STP core states and neither exceeds 50% surrender
fresh long deal: 300- or 450-day countdown began at most 30 days ago
```

AI uses 35% surrender, keeps 40% of divisions and 35% supply reserve against STP, and never starts during 120/180 windows.

- [ ] **Step 4: Implement full and partial modes**

Full mode saves CIN and OSF participants, declares addressed wars/adds them to the same campaign without a permanent faction, and targets states 59 and 61. APH receives only a saved posture and a post-success event.

Partial CIN mode targets only 59. Partial OSF mode targets only 61. The non-target country is untouched. Every mode sets `VAL_northern_campaign_attempted` before declaring and activates one 210-day mission.

- [ ] **Step 5: Implement 30-day control and guarded transfer**

`on_state_control_changed` schedules a token event only when VAL newly controls a saved target. After 30 days, recheck active campaign, matching mode/token, saved original owner, VAL participation, opponent participation, no contamination, VAL control, and absent per-target lock. Then offer the target a separate concession.

Acceptance or qualifying capitulation transfers only 59 from CIN and/or 61 from OSF, preserves original cores, and sets the corresponding one-shot lock. Full APH follow-up occurs only after both locks. Timeout white-peaces unresolved saved pairs but preserves an already accepted partial concession.

- [ ] **Step 6: Contaminate unexpected wars and handle timer collision**

The narrow war-relation hook compares each entrant to VAL plus the saved CIN/OSF participant set. An unexpected country sets `VAL_northern_campaign_contaminated` and permanently disables special transfers for this run; it does not eject the entrant.

If breach/D-14 occurs during the northern campaign, human VAL chooses addressed northern withdrawal or the timed idea `VAL_northern_two_front_overstretch` with `supply_consumption_factor = 0.15` and `planning_speed = -0.10` until the northern campaign ends. AI continues only while controlling at least one target and holding total strength ratio at least 1.5; otherwise it withdraws. The final STP war timer never pauses.

- [ ] **Step 7: Remove only the superseded unsafe content**

After the new resolver passes its tests, delete the exact old northern `on_capitulation` block from `common/on_actions/00_on_actions.txt`. Remove `VAL_start_test_war_with_STP` and `VAL_start_test_war_with_CIN` plus their category/localisation references, preserving the unrelated APH test decision. Do not modify state history files.

- [ ] **Step 8: Validate and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section north
python tools/validate_tc.py
git diff --check
git add -- common/scripted_effects/ADISCORD_STP_VAL_contract_effects.txt common/decisions/ADISCORD_VAL_contract_decisions.txt events/ADISCORD_VAL_contract_events.txt common/on_actions/01_ADISCORD_STP_VAL_crisis_on_actions.txt common/on_actions/00_on_actions.txt common/decisions/ADISCORD_test_wars_decisions.txt common/decisions/categories/ADISCORD_test_wars_categories.txt common/ideas/ADISCORD_STP_VAL_crisis_ideas.txt localisation/russian/ADISCORD_test_wars_l_russian.yml tools/stp_val_crisis_manifest.py tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: guard Kefreyt northern campaign peace"
```

### Task 11: Add posture-driven AI that reserves resources and changes plans

**Files:**
- Create: `common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt`
- Modify: `common/decisions/ADISCORD_STP_crisis_decisions.txt`
- Modify: `common/decisions/ADISCORD_VAL_contract_decisions.txt`
- Modify: `common/decisions/ADISCORD_NOD_crisis_decisions.txt`
- Modify: `events/ADISCORD_STP_crisis_events.txt`
- Modify: `events/ADISCORD_VAL_contract_events.txt`
- Modify: `events/ADISCORD_NOD_crisis_events.txt`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces static mutually exclusive AI blocks enabled by posture flags; decisions remain resource-gated and event resolvers remain authoritative.

- [ ] **Step 1: Add AI invariants**

Tests require five STP courses, four VAL courses, and five NOD courses; `abort_when_not_enabled = yes`; no accumulated `add_ai_strategy`; no early VAL war strategy; and operation weights that become zero below each course’s reserve.

- [ ] **Step 2: Run the AI validator and verify RED**

Run: `python tools/validate_adiscord_stp_val_crisis.py --section ai`

Expected: missing posture blocks, reserves, and adaptive operation weights.

- [ ] **Step 3: Implement STP courses and fallbacks**

```text
cautious Shabrat: reserve 60 PP, 15 CP, 400 infantry; palace/market/suspicion reduction; no intervention request
military infiltration: reserve 40 PP, 30 CP, 1000 infantry; officers/garrisons/mountains; intervention only if party strength exceeds 1.1
mass movement: reserve 30 PP, 10 CP, 1200 infantry; street/mountains; stop visible operations at suspicion 75
controlled party: reserve 60 PP, 25 CP, 800 infantry; intelligence/targeted raids/rotation; seek NOD mandate
purge party: reserve 35 PP, 15 CP, 500 infantry; raids/police/palace; stop new purges below 70% army equipment
```

Each course is selected at side commitment and held through one health stage unless Shabrat is lost, officers collapse, equipment crosses the stated floor, or an external war begins. An unaffordable priority falls back to intelligence or saving, never a random expensive operation.

- [ ] **Step 4: Implement VAL courses and fallbacks**

```text
contract broker: reserve 60 PP, 20 CP, 1500 infantry; accepts viable side with two nodes; supplies only against strong free NOD
resource raider: reserve 50 PP, 35 CP and fully equipped strike force; corridor only at force ratio 1.25 and active civil war
patient invader: reserve 75 PP, 40 CP, 2000 infantry; refuses civil-war entry and uses deals for preparation
northern broker: reserve 50 PP, 1000 infantry; full campaign at CIN+OSF influence 2, partial at exactly one prepared target
```

Lock course for 70 days. Permit change only at war start/end, STP outcome, loss of the required force ratio, or invalid target. The AI deal score includes real concessions, NOD posture, partner viability, and remaining equipment; identical saves need not accept every offer.

- [ ] **Step 5: Implement NOD courses**

Use these exact reserves and fallbacks:

```text
guardian: 75 PP, 30 CP, 1000 infantry; defend corridor and party; full STP intervention only with no other war, otherwise paid material support
YPR: 50 PP, 20 CP, 1500 infantry; reinforce 15/19; lower STP intervention one level, return to guardian if force ratio fails
COF: 40 PP, 15 CP, 1000 infantry; reinforce state 14; material STP support only until peace, then re-evaluate
Beshay: 35 PP, 10 CP, 800 infantry; select BHG state 5 or eligible independent BBV state 7; may end crisis for exposed Shabrat, otherwise ultimatum fallback
wait: 75 PP, 1200 infantry; build stock and borders; material support only until army equipment reaches 85%
```

Static strategies reinforce only the matching border and target. Limited-war desire is high only while the corresponding escalation/campaign flag is active. Suppress routine ally calls with an `ai_strategy` entry using `type = diplo_action_desire`, the saved limited-war opponent as `id`, `target = call_allies`, and `value = -9999`; do not use an invalid literal `call_allies = -9999` field. STP defense uses the support-level resolver rather than generic faction call.

- [ ] **Step 6: Validate AI behavior statically and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section ai
python tools/validate_tc.py
git diff --check
git add -- common/ai_strategy/ADISCORD_STP_VAL_crisis_ai.txt common/decisions/ADISCORD_STP_crisis_decisions.txt common/decisions/ADISCORD_VAL_contract_decisions.txt common/decisions/ADISCORD_NOD_crisis_decisions.txt events/ADISCORD_STP_crisis_events.txt events/ADISCORD_VAL_contract_events.txt events/ADISCORD_NOD_crisis_events.txt tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: add adaptive crisis AI strategies"
```

### Task 12: Build the read-only decision-category panels and Russian presentation

**Files:**
- Create: `interface/ADISCORD_STP_VAL_crisis.gui`
- Create: `common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt`
- Create: `common/scripted_localisation/ADISCORD_STP_VAL_crisis_scripted_loc.txt`
- Create: `localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml`
- Modify: `common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt`
- Modify: `common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt`
- Modify: `common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt`
- Modify: `localisation/russian/ADISCORD_STP_party_elections_l_russian.yml`
- Modify: `localisation/russian/ADISCORD_national_focuses_l_russian.yml`
- Modify: `localisation/russian/nsb_characters_l_russian.yml`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Produces `ADISCORD_STP_crisis_panel` and `ADISCORD_VAL_contract_panel`, both `context_type = decision_category`, with no effects or state-changing buttons.

- [ ] **Step 1: Add GUI/localisation/GFX tests**

Tests require:

```text
STP_crisis_operations -> ADISCORD_STP_crisis_panel -> ADISCORD_STP_crisis_panel_window
VAL_contract_campaign -> ADISCORD_VAL_contract_panel -> ADISCORD_VAL_contract_panel_window
```

Require matching category `scripted_gui` references, `visible_when_empty = yes`, `context_type = decision_category`, no `effects`, no GUI mutation, no `original_tag = STP`, no duplicate GUI/defined-text/localisation keys, strict UTF-8 BOM, all texture paths present, 68×68 spirit icons, 78×88 outcome cards, and 156×210 successor portraits.

- [ ] **Step 2: Run GUI and localisation validators and verify RED**

```powershell
python tools/validate_adiscord_stp_val_crisis.py --section gui
python tools/validate_adiscord_stp_val_crisis.py --section localisation
```

Expected: missing panels, getters, keys, and category bindings.

- [ ] **Step 3: Bind panels to decision categories**

Use the TFR China category-panel pattern without editing `interface/countrydecisionview.gui`. `STP_crisis_operations` is allowed only for literal tag STP and visible only with `STP_main_campaign_side`. `VAL_contract_campaign` is allowed only for literal tag VAL and visible after `VAL_One_Ledger_One_Banner`. Both stay visible while empty.

The scripted GUI files contain only `visible`, `triggers`, and read-only `properties`; there are no open flags, click effects, variable setters, or calculations.

- [ ] **Step 4: Build compact 580×470 panels**

STP panel shows stage portrait/health, readiness bar, suspicion bar, qualitative NOD/VAL assessments, active major/aux operation, observed countermeasure, and four outcome cards with confirmed/unknown/compromised text. It never displays security posture ID, hidden weights, or exact success chance.

VAL panel shows contract-authority band, STP phase, NOD assessment, word-level CIN/OSF/APH influence, state 45/88 status, current deal, canonical timer tier/status, common foreign-slot target, and selected future-war concept. Long text stays in tooltips; no nested scroll area is added inside the decisions list.

- [ ] **Step 5: Add exact read-only scripted localisation getters**

Create:

```text
STPGetReadinessBand
STPGetSuspicionBand
STPGetNODAssessment
STPGetVALAssessment
STPGetActiveMajorOperation
STPGetActiveAuxOperation
STPGetObservedCountermeasure
STPGetBloodlessOutcomeIntel
STPGetShabratWarOutcomeIntel
STPGetSotnikovOutcomeIntel
STPGetPartyOutcomeIntel
VALGetContractAuthorityBand
VALGetSTPCrisisPhase
VALGetNODAssessment
VALGetCINInfluence
VALGetOSFInfluence
VALGetAPHInfluence
VALGetState45Status
VALGetState88Status
VALGetDealStatus
VALGetCountdownStatus
VALGetForeignOperationStatus
VALGetWarConcept
```

Each uses descending thresholds and an `always = yes` fallback. Readiness, suspicion, and authority are rendered as whole 0–100 values with a literal percent sign, not the 0–1 `|%` formatter.

- [ ] **Step 6: Localize every gameplay surface**

Write concise Russian names/descriptions/tooltips for all new events, focuses, decisions, missions, spirits, ideas, leader names, GUI fields, outcome text, and cleanup warnings. Correct the legacy STP/VAL focus descriptions and remove obsolete “Голос площади” health-source language. Keep every changed Russian YAML in UTF-8 BOM with one `l_russian:` header.

- [ ] **Step 7: Validate and commit**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py --section gui
python tools/validate_adiscord_stp_val_crisis.py --section localisation
python tools/validate_tc.py
git diff --check
git add -- interface/ADISCORD_STP_VAL_crisis.gui common/scripted_guis/ADISCORD_STP_VAL_crisis_scripted_gui.txt common/scripted_localisation/ADISCORD_STP_VAL_crisis_scripted_loc.txt localisation/russian/ADISCORD_STP_VAL_crisis_l_russian.yml common/decisions/categories/ADISCORD_STP_VAL_crisis_categories.txt common/scripted_localisation/ADISCORD_STP_state_face_scripted_loc.txt common/scripted_localisation/ADISCORD_STP_leader_health_scripted_loc.txt localisation/russian/ADISCORD_STP_party_elections_l_russian.yml localisation/russian/ADISCORD_national_focuses_l_russian.yml localisation/russian/nsb_characters_l_russian.yml tools/validate_adiscord_stp_val_crisis.py tools/test_validate_adiscord_stp_val_crisis.py
git commit -m "feat: add Stelander Kefreyt crisis decision panels"
```

### Task 13: Retire legacy conflicts, run the full matrix, and inspect fresh logs

**Files:**
- Modify: `events/ADISCORD_events_STP.txt`
- Modify: `common/decisions/ADISCORD_decisions_STP.txt`
- Modify: `common/decisions/categories/ADISCORD_decision_categories_STP.txt`
- Modify: `common/scripted_localisation/ADISCORD_STP_party_elections_scripted_loc.txt`
- Modify: `common/scripted_localisation/ADISCORD_countrydevelopment.txt`
- Modify: `tools/validate_adiscord_stp_val_crisis.py`
- Modify: `tools/test_validate_adiscord_stp_val_crisis.py`

**Interfaces:**
- Leaves old save IDs as inert compatibility stubs, removes duplicate defined text/debug UI, and proves the feature with static gates plus fresh-game scenarios.

- [ ] **Step 1: Add integration and performance assertions**

The validator must:

- parse braces rather than split strings when checking the mercenary stub;
- permit `STP_state_face_stage` only in migration/wrapper whitelists;
- require suspicion migration before defaults and schema assignment last;
- require VAL authority reconstruction from completed central/specialization focuses before the schema assignment, plus idempotence guards;
- require both hidden STP posture selectors to be guarded by value 0 and forbid non-terminal resets or rerolls;
- reject `on_daily`, unrestricted `every_country`, GUI mutations, unsupported focus `cancel_effect`, direct non-core canonical-variable mutation, and global capitulation suppression;
- require all crisis global targets, token flags, factory locks, access, NAP/truce, resource rights, participant flags, and active operations in a cleanup manifest;
- require exactly one definition of `WhoTFDoWeSupportLeader`;
- require old `stp.1`/`stp.2` to be harmless compatibility forwarders or hidden no-op events;
- verify every focus/event/decision/idea/GUI/localisation reference.

- [ ] **Step 2: Retire only conflicting legacy behavior**

Remove the active BOP debug decisions while preserving their IDs as hidden debug-only stubs if a saved decision reference needs them. Keep `STP_inner_party_opinions_bop` inert for save parsing and ensure startup removes it. Convert `stp.1` and `stp.2` to hidden forwarders into the new crisis namespace without completing obsolete `STP_Side_With_Maksim` or `STP_Side_With_The_Party`. Remove the duplicate `WhoTFDoWeSupportLeader` definition from the narrower STP file and retain the shared definition.

Do not connect `news.1`; it transfers unrelated states and is outside this crisis.

- [ ] **Step 3: Run all static gates**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py
python tools/validate_tc.py --limit 300
git diff --check
```

Expected: all unit tests pass, feature validator exits 0, total-conversion sections are zero aside from explicitly pre-existing non-fatal mirror warnings, and diff check is empty.

- [ ] **Step 4: Run focused debug scenarios in-game**

Use a fresh debug session and cover:

1. ideal bloodless Shabrat coup;
2. prepared Shabrat civil war;
3. lost Shabrat and viable Sotnikov uprising;
4. party victory with NOD support;
5. party after excessive purges and party while completely ignoring active AI-resistance operations;
6. supply-only VAL deal;
7. direct VAL intervention under the expensive deal;
8. VAL refusal to a collapsing side;
9. victorious, stalemated, and defeated NOD;
10. early physical capture and guarded concession of 45/88;
11. late VAL war after the bloodless coup;
12. guarded northern limited peace;
13. ordinary war with CIN, OSF, or APH that does not invoke special peace;
14. save/reload during initialization, every health stage, rupture, civil war, postwar countdown, warning, and final war;
15. infantry/support conservation before escrow, after split, and after a cache is exposed;
16. correct VAL/NOD exit from the civil war plus removal of temporary access;
17. faction and `autonomy_shadow_state` restoration or break for every successor outcome;
18. both GUI panels at UI scale 1.0 and 1.25;
19. temporary side receives no Ivanov calendar, main tree, inlay, or prewar GUI;
20. victory by original STP and by temporary side, with the correct postwar tree and later VAL targeting the saved winner;
21. split after the player creates and deletes extra divisions: current army is divided by engine, arbitrary units survive, free stockpile and escrow do not duplicate;
22. crisis-focus manual cancellation is unavailable; Ivanov’s death cancels an unfinished focus and clears its sticky flag;
23. state 45/88 resource rights clear on breach, final warning, war, owner transfer, and emergency cleanup;
24. unexpected third-party entry contaminates the northern campaign, blocks 59/61 transfer, and leaves ordinary war resolution;
25. D-14 warning, pre-D diplomatic cleanup, timeout declaration, and stale delayed-token rejection;
26. bloodless coup plus successful and failed no-war party consolidations all create `STP_postwar_country` and start a countdown;
27. existing and pre-disbanded Capital Guard cases both avoid a free duplicate and preserve returned stockpile;
28. common foreign slot remains occupied through negotiation, a second counteroffer is impossible, and every selected concession creates its real obligation;
29. states 45/88 under one internal owner and split owners select the correct full or one-region addressed corridor opponent;
30. full, partial-CIN, and partial-OSF northern modes, 210-day timeout, attempted lock, and breach/final-warning collision;
31. leverage/exposure fall after discovery, regime change, stabilization, and family-block expiry but never below real-asset floors;
32. fresh `error.log` and `game.log` after each scenario group, separating known old noise from new feature errors.

Also run the legacy migration cases: suspicion `0.42 -> 42`, face 3 -> health 3, mercenary stub removed, and a second load leaves the migrated STP values unchanged; for VAL, test base authority, central-focus authority, and mixed central/specialization authority, then reload each case and confirm the reconstructed value does not change. Save/reload once after both hidden STP postures have been selected and confirm the same security and resistance strategy values survive without reroll.

- [ ] **Step 5: Observe AI batches**

Run at least 24 hands-off seeds through the internal outcome and final VAL chain. Record internal outcome, civil-war duration, NOD posture, deal level, VAL course, northern attempt, calendar days, access/faction/autonomy cleanup, and equipment conservation. Confirm:

- at least three NOD strategies appear and none exceeds 60% of runs;
- AI bloodless Shabrat succeeds in no more than 15%;
- no internal outcome exceeds 70%;
- Ivanov always dies on day 267, side commitment completes by day 140, and rupture/no-war transfer starts by day 281;
- at least 90% of AI civil wars finish within 540 days without forced annexation;
- VAL never uses a meaningless early scripted war;
- identical-looking offers are not universally accepted;
- no-deal warning is D-14 and war day is 120 ±3, while deal missions are exactly 180/300/450;
- the final STP–VAL war always starts when its mission expires;
- equipment escrow, faction, autonomy, and temporary access match the recorded outcome;
- special northern peace never fires outside its campaign;
- negotiation and northern operation never overlap, and exposure/leverage do not rise monotonically in every run;
- AI selects partial North when exactly one target is prepared and avoids a northern start before a short STP window;
- on northern-timeout/final-war collision AI withdraws addressedly or continues only with the required 1.5 advantage.

- [ ] **Step 6: Inspect fresh logs**

Record the run start time, then verify both log timestamps are newer. Search:

```powershell
$hoiLogs = Join-Path $env:USERPROFILE "Documents\Paradox Interactive\Hearts of Iron IV\logs"
Get-Item (Join-Path $hoiLogs "error.log"),(Join-Path $hoiLogs "game.log") | Select-Object Name,Length,LastWriteTime
rg -n -i "ADISCORD_STP_VAL|STP_crisis|VAL_contract|scripted.gui|unknown.window|could not find sprite|error loading texture|locali[sz]ation|unexpected token|invalid effect|invalid trigger" (Join-Path $hoiLogs "error.log") (Join-Path $hoiLogs "game.log")
```

Fix every new matching parser/runtime/localisation/GFX error and rerun the affected static and gameplay scenario.

- [ ] **Step 7: Re-run the complete gate after every runtime fix**

```powershell
python -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python tools/validate_adiscord_stp_val_crisis.py
python tools/validate_tc.py --limit 300
git diff --check
```

Do not treat the pre-runtime gate as final evidence; this post-log run must be the one recorded in the implementation report.

- [ ] **Step 8: Final diff audit and commit**

Inspect `git status --short`, `git diff --stat`, and every touched-file diff. Confirm unrelated dirty files remain unstaged. Then:

```powershell
$ownedCrisisFiles = python tools/validate_adiscord_stp_val_crisis.py --print-owned-files
git add -- $ownedCrisisFiles
git commit -m "test: validate Stelander Kefreyt crisis campaign"
```

Compare the staged list against `OWNED_FEATURE_FILES` and the reviewed runtime-fix paths before committing. Do not stage unrelated pre-existing user changes; never use `git add -A` or a broad directory path.

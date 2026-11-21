"""Party coverage and collapse support contracts; native UI needs manual checking."""

from collections import Counter
from pathlib import Path
import re
import unittest

from PIL import Image

from tools.lib.campaign_selection import ATLAS, campaign_roster
from tools.tests.test_adiscord_stp_preparation import block, scalar, matches_conditions, selected_effects, walk
from tools.validators.validate_adiscord_division_templates import parse_clausewitz
from tools.validators.validate_adiscord_english_localisation import ENTRY


ROOT = Path(__file__).resolve().parents[2]
TAGS = (
    "NAM", "STP", "STS", "SRP", "VAL", "SHL", "RUS", "IVN", "IVC",
    "WRK", "WKR", "TVA", "VAD", "NOD", "AZH", "EFL", "SLF",
)
NATION_TARGET = "event_target:ADISCORD_vorkerland_nation"
# A route profile is named after the roster it renames. The WRK roster serves
# whichever country is Vorkerland, so its profiles select that country.
PROFILE_COUNTRIES = {"WRK": NATION_TARGET}


def parsed(path):
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def focus_reward(tree, focus_id):
    entries = parsed(ROOT / "common/national_focus" / tree)
    focuses = [row.value for row in entries if row.key == "shared_focus" and isinstance(row.value, list)]
    focuses.extend(row.value for tree in entries if tree.key == "focus_tree"
                   for row in tree.value if row.key == "focus")
    focus, = (body for body in focuses if scalar(body, "id") == focus_id)
    return block(focus, "completion_reward")


def country_event(filename, event_id):
    events = parsed(ROOT / "events" / filename)
    event, = (e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == event_id)
    return event


class PartyRepresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        groups = block(parsed(ROOT / "common/ideologies/00_ideologies.txt"), "ideologies")
        cls.groups = {entry.key for entry in groups}
        cls.ideology_groups = {
            subtype.key: group.key
            for group in groups
            for subtype in block(group.value, "types")
        }
        cls.characters = {}
        cls.character_paths = {}
        for path in (ROOT / "common/characters").glob("*.txt"):
            for character in block(parsed(path), "characters"):
                cls.characters[character.key] = character.value
                cls.character_paths[character.key] = path
        cls.histories = {
            tag: parsed(next((ROOT / "history/countries").glob(f"{tag} - *.txt")))
            for tag in TAGS
        }
        cls.localisation = {}
        for language in ("russian", "english"):
            entries = {}
            for path in (ROOT / "localisation" / language).glob("*.yml"):
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    match = ENTRY.fullmatch(line)
                    if match:
                        entries.setdefault(match[1], []).append((path, match[2]))
            cls.localisation[language] = entries

    def test_every_party_has_a_recruited_leader_or_scripted_resistance_leader(self):
        for tag, history in self.histories.items():
            with self.subTest(tag=tag):
                recruited = [entry.value for entry in history if entry.key == "recruit_character"]
                self.assertEqual(len(recruited), len(set(recruited)))
                represented = {
                    self.ideology_groups[scalar(role.value, "ideology")]
                    for character in recruited
                    for role in self.characters[character]
                    if role.key == "country_leader"
                }
                if tag == "STS":
                    effects = parsed(ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
                    command = block(effects, "STP_cw_establish_resistance_command")
                    self.assertIn("STP_maksim_shabrat", str(command))
                    represented.add("chauvinism")
                self.assertEqual(represented, self.groups)

    def test_representatives_have_unique_recruitment_valid_portraits_and_localised_names(self):
        sprites = set()
        for path in (ROOT / "interface").glob("*.gfx"):
            sprites.update(re.findall(r'\bname\s*=\s*"(GFX_Portrait_Forul_Generic_\d+)"', path.read_text(encoding="utf-8-sig")))
        recruitment = Counter(
            entry.value
            for history in self.histories.values()
            for entry in history
            if entry.key == "recruit_character"
        )
        for name, character in self.characters.items():
            if "_party_representative_" not in name:
                continue
            with self.subTest(character=name):
                self.assertEqual(recruitment[name], 1)
                tag = name.split("_", 1)[0]
                role = block(character, "country_leader")
                group = self.ideology_groups[scalar(role, "ideology")]
                ruling = scalar(block(self.histories[tag], "set_politics"), "ruling_party")
                self.assertNotEqual(group, ruling)
                self.assertNotIn("advisor", {entry.key for entry in character})
                portrait = scalar(block(block(character, "portraits"), "civilian"), "large")
                self.assertIn(portrait, sprites)
                self.assertFalse(self.character_paths[name].read_bytes().startswith(b"\xef\xbb\xbf"))
                for language, entries in self.localisation.items():
                    self.assertEqual(len(entries.get(name, [])), 1, (language, name))
                    path, value = entries[name][0]
                    self.assertTrue(value.strip())
                    self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_party_short_and_long_names_are_complete_in_both_languages(self):
        for language, entries in self.localisation.items():
            for tag in TAGS:
                for group in self.groups:
                    for suffix in ("", "_long"):
                        key = f"{tag}_{group}_party{suffix}"
                        with self.subTest(language=language, key=key):
                            self.assertEqual(len(entries.get(key, [])), 1)
                            self.assertTrue(entries[key][0][1].strip())

    def test_status_roster_covers_the_live_ideologies_and_uses_the_same_badge_and_text_predicates(self):
        loc = parsed(ROOT / "common/scripted_localisation/ADISCORD_ideologies.txt")
        resolvers = {scalar(entry.value, "name"): entry.value for entry in loc}
        scripts = block(parsed(ROOT / "common/scripted_guis/CountryView_ScriptedGui.txt"), "scripted_gui")
        gui = block(scripts, "ADISCORD_party_markers_gui")
        self.assertEqual(scalar(gui, "parent_window_token"), "politics_tab")
        self.assertFalse({"dynamic_lists", "effects", "dirty"} & {entry.key for entry in gui})
        for group in self.groups:
            suffix = group.capitalize()
            names = resolvers[f"GetADiscordPartyName{suffix}"]
            self.assertTrue(any(row.key == "text" and
                                scalar(row.value, "localization_key") == f"country_culture|{group}_party"
                                for row in names))
            name_rows = [row.value for row in names if row.key == "text"]
            if group == "technocracy":
                panel = resolvers["GetPartyLocTechnocracy"]
                panel_first = next(row.value for row in panel if row.key == "text")
                for board in (name_rows.pop(0), panel_first):
                    self.assertEqual(scalar(block(board, "trigger"), "tag"), "NAM")
                    self.assertEqual(scalar(block(board, "trigger"), "has_country_flag"), "NAM_corp_takeover")
                    key = scalar(board, "localization_key")
                    self.assertEqual(key, "NAM_board_technocracy_party")
                    for entries in self.localisation.values():
                        self.assertTrue(entries[key][0][1].split(maxsplit=1)[1].strip())
            self.assertEqual(scalar(block(name_rows[0], "trigger"), "has_government"), group)
            rows = resolvers[f"GetADiscordPartyStatus{suffix}"]
            for status in ("leader", "member", "banned"):
                name = f"ADISCORD_party_{group}_{status}"
                row = next(entry.value for entry in rows if entry.key == "text"
                           and scalar(entry.value, "localization_key") == f"ADISCORD_party_{status}")
                self.assertEqual(scalar(block(row, "trigger"), name), "yes")
                self.assertEqual(scalar(block(block(gui, "triggers"), f"party_{group}_{status}_visible"), name), "yes")
            for entries in self.localisation.values():
                self.assertEqual(entries[f"{group}_party"][0][1], "$" + group + "$")
                self.assertEqual(entries[f"ADISCORD_party_{group}_tt"][0][1], f"[GetADiscordPartyHover{suffix}]")
                banned = entries[f"ADISCORD_party_{group}_banned_hover"][0][1]
                self.assertTrue(banned.startswith("§R$ADISCORD_party_banned$§!"))
                self.assertIn(f"[GetADiscordPartyName{suffix}]", banned)
                self.assertIn(f"party_popularity@{group}", banned)

        etatists = resolvers["GetADiscordPartyNameEtatism"]
        for key in ("IMD_etatism_party", "STP_ch_leader_3", "STP_pf_security_name"):
            row, = (entry.value for entry in etatists if entry.key == "text"
                    and scalar(entry.value, "localization_key") == key)
            self.assertEqual(scalar(block(row, "trigger"), "ADISCORD_party_etatism_member"), "yes")

    def test_party_badges_leave_hover_to_the_native_colour_legend(self):
        def widget(entries, kind, name):
            result, = (e.value for e in entries if e.key == kind and scalar(e.value, "name") == name)
            return result

        native = block(parsed(ROOT / "interface/countrypoliticsview.gui"), "guiTypes")
        politics = widget(native, "containerWindowType", "countrypoliticsview")
        legend = widget(politics, "containerWindowType", "chart_explanation")
        native_grid = widget(legend, "gridBoxType", "parties_grid")
        native_row = widget(native, "containerWindowType", "political_party_info_entry")
        fill = widget(native_row, "iconType", "color_block")
        view = block(parsed(ROOT / "interface/ADISCORD_CountryView.gui"), "guiTypes")
        overlay = widget(view, "containerWindowType", "ADISCORD_party_markers")
        groups = [e.key for e in block(parsed(ROOT / "common/ideologies/00_ideologies.txt"), "ideologies")]
        pitch = int(scalar(block(native_grid, "slotsize"), "height"))
        origin = {axis: int(scalar(block(legend, "position"), axis)) for axis in ("x", "y")}
        origin["y"] += int(scalar(block(legend, "margin"), "top"))
        self.assertEqual(scalar(block(overlay, "size"), "width"), "0")
        self.assertEqual(scalar(block(overlay, "size"), "height"), "0")
        self.assertEqual(scalar(overlay, "clipping"), "no")
        self.assertEqual({e.key for e in overlay if isinstance(e.value, list)},
                         {"position", "size", "iconType"})
        self.assertEqual({axis: int(scalar(block(overlay, "position"), axis)) for axis in ("x", "y")}, origin)
        for status in ("member", "leader"):
            path = ROOT / "gfx/interface/party_status_system" / f"party_status_coalition_{status}.png"
            with Image.open(path) as image:
                self.assertEqual(image.size, (16, 16))
                self.assertEqual(image.mode, "RGBA")
                self.assertGreater(image.getchannel("A").histogram()[0], image.width * image.height // 5)
        for i, group in enumerate(groups):
            for axis in ("x", "y"):
                offset = i * pitch if axis == "y" else 0
                fill_start = (int(scalar(block(native_grid, "position"), axis)) +
                              int(scalar(block(fill, "position"), axis)) + offset)
                for status in ("banned", "member", "leader"):
                    badge = widget(overlay, "iconType", f"party_{group}_{status}")
                    badge_start = int(scalar(block(badge, "position"), axis))
                    if status == "banned":
                        self.assertEqual(badge_start, fill_start)
                    else:
                        self.assertEqual(badge_start + 8, fill_start + 6)
                        self.assertNotIn("scale", {entry.key for entry in badge})
                    self.assertEqual(scalar(badge, "alwaystransparent"), "yes")
        self.assertEqual(len([e for e in overlay if e.key == "iconType"]), 3 * len(groups))
        self.assertFalse(any(e.key == "name" and e.value in {
            "ADISCORD_parties_launcher", "ADISCORD_parties_window", "ADISCORD_parties_toggle",
            "ADISCORD_party_marker_anchor",
        } for e in walk(native + view) if isinstance(e.value, str)))

    def test_fixed_badges_follow_current_country_arrays_and_government(self):
        triggers = parsed(ROOT / "common/scripted_triggers/ideology_scripted_triggers.txt")

        def matches(rows, ruler, arrays):
            results = []
            for entry in rows:
                if entry.key == "is_in_array":
                    binding, = entry.value
                    results.append(binding.value in arrays.get(binding.key, set()))
                elif entry.key == "has_government":
                    results.append(entry.value == ruler)
                elif entry.key == "NOT":
                    results.append(not matches(entry.value, ruler, arrays))
                else:
                    self.fail(f"Unsupported party condition {entry.key}")
            return all(results)

        for ruler in self.groups:
            partner = next(group for group in self.groups if group != ruler)
            for phase in ("legal", "banned", "coalition"):
                banned = self.groups - {ruler, partner} if phase == "banned" else set()
                cabinet = {ruler, partner} if phase == "coalition" else set()
                arrays = {
                    "ADISCORD_banned_parties": {"token:" + group for group in banned},
                    "ADISCORD_cabinet_parties": {"token:" + group for group in cabinet},
                }
                for group in self.groups:
                    expected = {"banned": group in banned,
                                "member": group in cabinet and group != ruler,
                                "leader": group in cabinet and group == ruler}
                    for status, visible in expected.items():
                        with self.subTest(ruler=ruler, phase=phase, party=group, status=status):
                            self.assertEqual(matches(block(triggers, f"ADISCORD_party_{group}_{status}"),
                                                     ruler, arrays), visible)

    def test_itoran_revolt_reads_the_current_ban_before_distributing_recruits(self):
        effects = parsed(ROOT / "common/scripted_effects/ADISCORD_IVN_scripted_effects.txt")
        revolt = block(block(effects, "IVN_start_marches_revolt"), "if")
        deductions = [entry.value for entry in revolt if entry.key == "if"
                      and any(e.key == "add_manpower" and e.value == "-5000" for e in walk(entry.value))]
        self.assertEqual(len(deductions), 1)
        ban = block(block(deductions[0], "limit"), "is_in_array")
        self.assertEqual(scalar(ban, "ADISCORD_banned_parties"), "token:chauvinism")
        self.assertEqual(scalar(block(deductions[0], "IVC"), "add_manpower"), "-5000")

    def party_actions(self, body, party=None):
        actions = []
        for entry in body:
            if entry.key == "set_temp_variable":
                for binding in entry.value:
                    if binding.key == "ADISCORD_party":
                        party = binding.value
            elif entry.key in {"ADISCORD_admit_coalition_party", "ADISCORD_remove_coalition_party",
                             "ADISCORD_ban_party", "ADISCORD_legalise_party"}:
                self.assertIsNotNone(party)
                actions.append((entry.key, party))
            elif isinstance(entry.value, list):
                actions.extend(self.party_actions(entry.value, party))
        return actions

    def test_starting_bans_belong_to_the_fresh_campaign_and_have_named_legend_rows(self):
        expected = {"MON": "humanism", "NAM": "humanism", "SHL": "anarchism"}
        hooks = block(parsed(ROOT / "common/on_actions/00_ADISCORD_on_actions.txt"), "on_actions")
        startup = block(block(hooks, "on_startup"), "effect")
        setup, = (e.value for e in startup if e.key == "if" and
                  any(x.key == "set_global_flag" and x.value == "ADISCORD_starting_technology_profiles_applied"
                      for x in e.value))
        condition = block(setup, "limit")
        self.assertEqual(scalar(condition, "has_global_flag"), "ADISCORD_fresh_campaign_contract_v1")
        self.assertEqual(scalar(block(condition, "NOT"), "has_global_flag"), "ADISCORD_starting_technology_profiles_applied")
        playable = set(campaign_roster()) - {ATLAS}
        bans = [(country.key, action, token) for country in setup if country.key in playable
                for action, token in self.party_actions(country.value)]
        self.assertCountEqual(bans, [(tag, "ADISCORD_ban_party", "token:" + group) for tag, group in expected.items()])
        self.assertEqual(sum(e.key == "ADISCORD_ban_party" for e in walk(startup)), len(expected))
        restricted = {
            "STP": ("hedonism", "chauvinism"),
            "VAL": ("etatism", "pragmatism"),
            "RUS": ("etatism", "anarchism"),
        }
        for tag, (ruler, opposition) in restricted.items():
            with self.subTest(country=tag):
                history = self.histories[tag]
                self.assertEqual(scalar(block(history, "set_politics"), "ruling_party"), ruler)
                recorded = [binding.value for row in history if row.key == "add_to_array"
                            for binding in row.value if binding.key == "ADISCORD_banned_parties"]
                banned = self.groups - {ruler, opposition}
                self.assertCountEqual(recorded, ["token:" + group for group in banned])
                self.assertEqual(len(recorded), 6)
                for group in banned:
                    for loc in self.localisation.values():
                        self.assertIn(f"{tag}_{group}_party", loc)
        for tag, group in expected.items():
            for loc in self.localisation.values():
                for suffix in ("", "_long"):
                    self.assertEqual(len(loc[f"{tag}_{group}_party{suffix}"]), 1)

        change = block(block(hooks, "on_government_change"), "effect")
        unban, = (e.value for e in change if e.key == "if" and any(x.key == "remove_from_array" for x in e.value))
        self.assertEqual(scalar(block(unban, "remove_from_array"), "ADISCORD_banned_parties"), "current_party_ideology_group")

    def test_svetlogorye_recognition_and_etatist_register_change_the_named_parties(self):
        tree = "ADISCORD_NAM_postwar.txt"
        recognition = focus_reward(tree, "NAM_recognition")
        self.assertEqual(self.party_actions(recognition), [
            ("ADISCORD_legalise_party", "token:chauvinism"),
            ("ADISCORD_admit_coalition_party", "token:chauvinism"),
        ])
        committees = [entry.value for entry in parsed(ROOT / "common/national_focus" / tree)
                      if entry.key == "shared_focus" and scalar(entry.value, "id") == "NAM_pw_constitutional_committee"]
        committee, = committees
        self.assertEqual(scalar(block(committee, "allow_branch"), "NAM_prewar_service_mandate"), "yes")
        # The committee also carries the folded iron-ending reform; the decree stays its first `if`.
        decree = next(e.value for e in block(committee, "completion_reward") if e.key == "if")
        self.assertEqual(scalar(block(decree, "limit"), "has_government"), "etatism")
        self.assertEqual(self.party_actions(decree), [
            ("ADISCORD_ban_party", "token:anarchism"),
            ("ADISCORD_ban_party", "token:pragmatism"),
        ])
        for entry, number in ((decree, 413), (focus_reward(tree, "NAM_pw_district_hospitals"), 414)):
            event_id = f"ADISCORD_nam_resource_war.{number}"
            # The hospitals fire the scene from the reward's single hidden effect (C.1 layout).
            self.assertIn(event_id, [scalar(e.value, "id") for e in walk(entry) if e.key == "country_event"])
            scene = country_event("ADISCORD_nam_resource_war_events.txt", event_id)
            self.assertEqual(scalar(scene, "fire_only_once"), "yes")
            self.assertEqual(scalar(scene, "is_triggered_only"), "yes")
            self.assertEqual([e.key for e in block(scene, "option")], ["name"])
            for loc in self.localisation.values():
                for key in (scalar(scene, "title"), scalar(scene, "desc"), scalar(block(scene, "option"), "name")):
                    self.assertIn(key, loc)

    def test_all_country_cards_expose_party_status_through_gameplay(self):
        sources = {
            "STP": block(parsed(ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                         "STP_ch_update_cabinet_parties"),
            "IVN": focus_reward("ADISCORD_IVN_focus.txt", "IVN_parliament_coalition_pragmatists"),
            "SHL": focus_reward("ADISCORD_SHL_focus.txt", "SHL_council_of_cities"),
            "NAM": focus_reward("ADISCORD_NAM_postwar.txt", "NAM_recognition"),
            "RUS": focus_reward("ADISCORD_national_focus_RUS.txt", "RUS_scientists_council"),
            "WRK": focus_reward("ADISCORD_Vorkerland_prewar.txt", "WRK_committee_bagley_executive"),
            "VAL": country_event("ADISCORD_VAL_contract_events.txt", "val_rework.275"),
            "MON": country_event("ADISCORD_MON_events.txt", "ADISCORD_mon_court.1"),
        }
        self.assertEqual(set(sources), set(campaign_roster()) - {ATLAS})
        for tag, body in sources.items():
            with self.subTest(tag=tag):
                self.assertTrue(any(e.key == "ADISCORD_admit_coalition_party" for e in walk(body)))

    def test_new_party_choices_target_the_parties_named_on_the_legend(self):
        admit = "ADISCORD_admit_coalition_party"
        ban = "ADISCORD_ban_party"
        for file, event_id, expected in [
            ("ADISCORD_MON_events.txt", "ADISCORD_mon_court.1", {
                "houses": [(admit, "token:hedonism")],
                "staff": [(admit, "token:etatism"), (ban, "token:pragmatism")],
                "throne": [],
            }),
            ("ADISCORD_VAL_contract_events.txt", "val_rework.275", {
                "seat": [(admit, "token:pragmatism")], "trains": [],
            }),
            ("ADISCORD_VAL_contract_events.txt", "val_council.42", {
                "close": [(ban, "token:etatism")], "a": [],
            }),
            ("ADISCORD_vorkerland_events.txt", "ADISCORD_vorkerland_preparation.1", {
                "worker": [], "army": [(admit, "token:etatism")], "technical": [(admit, "token:technocracy")],
            }),
        ]:
            with self.subTest(event=event_id):
                event = country_event(file, event_id)
                choices = {scalar(e.value, "name").rsplit(".", 1)[1]: self.party_actions(e.value)
                           for e in event if e.key == "option"}
                self.assertEqual(choices, expected)
                for entry in walk(event):
                    if entry.key in {"name", "title", "desc", "custom_effect_tooltip"} and isinstance(entry.value, str):
                        for loc in self.localisation.values():
                            self.assertIn(entry.value, loc)

        for loc in self.localisation.values():
            for group in ("hedonism", "etatism", "pragmatism", "chauvinism"):
                self.assertEqual(len(loc[f"MON_{group}_party"]), 1)
                self.assertEqual(len(loc[f"MON_{group}_party_long"]), 1)

    def test_cabinet_offers_and_regime_changes_follow_their_campaign_hooks(self):
        mon = "ADISCORD_mon_court.1"
        directory = ROOT / "common/on_actions"
        opening = block(parsed(directory / "00_ADISCORD_on_actions.txt"), "on_actions")
        startup = block(block(opening, "on_startup"), "effect")
        court, = (e.value for e in walk(startup) if e.key == "MON"
                  and any(x.key == "id" and x.value == mon for x in walk(e.value)))
        player = block(court, "if")
        self.assertEqual(scalar(block(player, "limit"), "is_ai"), "no")
        self.assertEqual(scalar(block(player, "country_event"), "days"), "3")
        crisis = parsed(directory / "02_ADISCORD_rin_oath_crisis_on_actions.txt")
        wake, = (e.value for e in walk(crisis) if e.key == "MON")
        self.assertEqual([e.key for e in wake], ["ADISCORD_release_non_participating_minor_optimization", "country_event"])
        self.assertEqual(scalar(block(wake, "country_event"), "id"), mon)
        self.assertEqual(scalar(country_event("ADISCORD_MON_events.txt", mon), "fire_only_once"), "yes")

        reward = focus_reward("ADISCORD_national_focus_VAL.txt", "VAL_Morns_Supply_Trains")
        offer, = (e.value for e in reward if e.key == "if" and any(x.key == "country_event" for x in e.value))
        self.assertEqual(scalar(block(offer, "limit"), "VAL_morn_cabinet_offer_current"), "yes")
        self.assertEqual(scalar(block(offer, "country_event"), "id"), "val_rework.275")
        effects = parsed(ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt")
        for name in ("VAL_council_take_power", "VAL_enter_stelander_defeat", "VAL_council_revanchist_coup"):
            government = block(block(effects, name), "if")
            keys = [e.key for e in government]
            self.assertLess(keys.index("ADISCORD_end_party_coalition"), keys.index("set_politics"))
        regimes = block(effects, "VAL_peace_install_regime")
        self.assertEqual(scalar(regimes, "ADISCORD_end_party_coalition"), "yes")
        for outcome in (e.value for e in regimes if e.key in {"if", "else_if"}):
            civilian = any(e.key == "VAL_peace_regime_cabinet" for e in block(outcome, "limit"))
            self.assertEqual(bool(self.party_actions(outcome)), civilian)
        vorkerland = parsed(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        self.assertEqual(scalar(block(vorkerland, "ADISCORD_vorkerland_begin_collapse"), "ADISCORD_end_party_coalition"), "yes")

    def test_nam_opposition_leaders_keep_their_identity_through_the_takeover(self):
        weber = "NAM_Yaroslav_Weber"
        karamyshev = "NAM_Rostislav_Karamyshev"
        cabinet = parsed(ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt")
        history = self.histories["NAM"]
        for person, ideology in ((weber, "humanism_ideology"), (karamyshev, "chauvinism_ideology")):
            self.assertEqual(scalar(block(self.characters[person], "country_leader"), "ideology"), ideology)
            recruit, = (i for i, e in enumerate(history) if e.key == "recruit_character" and e.value == person)
            promote, = (i for i, e in enumerate(history) if e.key == "promote_character"
                        and scalar(e.value, "character") == person and scalar(e.value, "ideology") == ideology)
            self.assertLess(recruit, promote)
        takeover = block(cabinet, "NAM_corp_takeover")
        opening, = (e.value for e in takeover if e.key == "if" and
                    any(a.key == "NAM_board_seat_opposition_leaders" for a in e.value))
        self.assertEqual(scalar(block(block(opening, "limit"), "NOT"), "has_country_flag"), "NAM_board_opened")
        seats = block(cabinet, "NAM_board_seat_opposition_leaders")
        for alive_weber in (False, True):
            for alive_karamyshev in (False, True):
                facts = {("NAM", "has_character", weber): alive_weber,
                         ("NAM", "has_character", karamyshev): alive_karamyshev}
                chosen = [e for _, e in selected_effects(seats, facts, "NAM")]
                self.assertEqual([scalar(e.value, "character") for e in chosen if e.key == "promote_character"],
                                 [weber] if alive_weber else [])
                roles = [e.value for e in chosen if e.key == "add_country_leader_role"]
                self.assertEqual([scalar(b, "character") for b in roles], [karamyshev] if alive_karamyshev else [])
                if roles:
                    self.assertEqual(scalar(block(roles[0], "country_leader"), "ideology"), "etatism_ideology")

    def test_partition_night_settles_only_the_surviving_island_leader(self):
        effects = parsed(ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt")
        tree = "ADISCORD_NAM_exile_corporate.txt"
        final = "NAM_island_partition_succession"
        partition = [row.value for row in focus_reward(tree, "NAM_board_partition_night") if row.key == "hidden_effect"]
        self.assertEqual(scalar(partition[0], final), "yes")
        triggers = parsed(ROOT / "common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt")
        chair_rules = block(triggers, "NAM_board_chairman_rules")
        for branch in (row.value for row in block(effects, final) if row.key in ("if", "else_if")):
            self.assertEqual(scalar(block(branch, "limit"), "NAM_board_chairman_rules"), "yes")
        chairmen = [scalar(entry.value, "character") for entry in block(chair_rules, "OR")]
        self.assertCountEqual(chairmen, ["NAM_Mark_Olshansky", "NAM_Aristarkh_Vyazemtsev", "NAM_Taisiya_Valts",
                                        "NAM_Saveliy_Kruze", "NAM_Rodion_Kalyonov", "NAM_Nazar_Guryev",
                                        "NAM_Lidiya_Velyaminova"])
        self.assertFalse(matches_conditions(chair_rules, {("NAM", "ruling_leader"): "NAM_party_representative_technocracy"}, "NAM"))
        weber = "NAM_Yaroslav_Weber"
        karamyshev = "NAM_Rostislav_Karamyshev"
        for chairman in chairmen:
            for humanists, empire, successor, party in (
                ("last_debtor", "posthumous_signature", chairman, "technocracy"),
                ("last_debtor", "escheated_throne", karamyshev, "etatism"),
                ("treaty_two_judases", "posthumous_signature", weber, "humanism"),
            ):
                with self.subTest(chairman=chairman, humanists=humanists, empire=empire):
                    facts = {("NAM", "ruling_leader"): chairman, ("NAM", "has_character", weber): True,
                             ("NAM", "has_character", karamyshev): True}
                    facts["NAM", "NAM_board_chairman_rules", "yes"] = matches_conditions(chair_rules, facts, "NAM")
                    for choice in (humanists, empire):
                        focus = "NAM_board_" + choice
                        hidden = [row.value for row in focus_reward(tree, focus) if row.key == "hidden_effect"]
                        # The settlement call stays alone in the first hidden_effect; a kill
                        # fires its story event from a second one.
                        action, = hidden[0]
                        if choice in {"last_debtor", "posthumous_signature"}:
                            self.assertEqual(len(hidden), 2, focus)
                            event, = hidden[1]
                            self.assertEqual(event.key, "country_event", focus)
                        else:
                            self.assertEqual(len(hidden), 1, focus)
                        choice_effects = block(effects, action.key)
                        if choice in {"last_debtor", "posthumous_signature"}:
                            for _, step in selected_effects(choice_effects, facts, "NAM"):
                                if step.key == "retire_character":
                                    facts["NAM", "has_character", step.value] = False
                        else:
                            self.assertNotIn("retire_character", {step.key for step in walk(choice_effects)})
                        facts["NAM", "has_completed_focus", focus] = True
                    self.assertEqual(facts["NAM", "has_character", weber], successor == weber)
                    self.assertEqual(facts["NAM", "has_character", karamyshev], successor == karamyshev)
                    outcome = [step for _, step in selected_effects(block(effects, final), facts, "NAM")]
                    if successor == chairman:
                        self.assertFalse(any(step.key in {"set_politics", "add_country_leader_role",
                                                          "drop_cosmetic_tag", "remove_ideas"} for step in outcome))
                    else:
                        self.assertEqual(scalar(block(outcome, "set_politics"), "ruling_party"), party)
                        promotion = block(outcome, "promote_character")
                        self.assertEqual(scalar(promotion, "character"), successor)
                        self.assertEqual(self.ideology_groups[scalar(promotion, "ideology")], party)
                        facts["NAM", "has_character", successor] = False
                        self.assertFalse(list(selected_effects(block(effects, final), facts, "NAM")))

    def test_story_cabinets_apply_changes_to_the_country_receiving_the_seats(self):
        admit = "ADISCORD_admit_coalition_party"
        legalise = "ADISCORD_legalise_party"
        remove = "ADISCORD_remove_coalition_party"
        directory = ROOT / "common/scripted_effects"
        nam = parsed(directory / "ADISCORD_nam_resource_war_effects.txt")
        takeover = block(nam, "NAM_corp_takeover")
        keys = [entry.key for entry in takeover]
        self.assertLess(keys.index("ADISCORD_end_party_coalition"), keys.index("set_politics"))
        self.assertEqual(scalar(takeover, "clear_array"), "ADISCORD_banned_parties")
        self.assertLess(keys.index("clear_array"), keys.index("set_politics"))
        self.assertEqual(scalar(block(takeover, "set_politics"), "ruling_party"), "technocracy")
        roles = {scalar(e.value, "character"): scalar(block(e.value, "country_leader"), "ideology")
                 for e in walk(takeover) if e.key == "add_country_leader_role"}
        promotions = {scalar(e.value, "character"): scalar(e.value, "ideology")
                      for e in walk(block(nam, "NAM_board_install_chairman")) if e.key == "promote_character"}
        self.assertEqual(len(roles), 7)
        self.assertEqual(set(roles.values()), {"techno_corporatism"})
        self.assertEqual(promotions, roles)
        treaty = focus_reward("ADISCORD_NAM_exile_corporate.txt", "NAM_board_treaty_two_judases")
        self.assertEqual(scalar(block(treaty, "hidden_effect"), "NAM_island_compact_with_humanists"), "yes")
        self.assertEqual(self.party_actions(block(nam, "NAM_island_compact_with_humanists")),
                         [(legalise, "token:humanism"), (admit, "token:humanism")])
        self.assertEqual(self.party_actions(block(nam, "NAM_island_spare_karamyshev")), [])
        for tree, focus_id, expected in [
            ("ADISCORD_SHL_focus.txt", "SHL_council_of_cities", [(admit, "token:hedonism")]),
            ("ADISCORD_national_focus_RUS.txt", "RUS_scientists_council",
             [(legalise, "token:technocracy"), (admit, "token:technocracy")]),
            ("ADISCORD_national_focus_RUS.txt", "RUS_black_army_oath",
             [(legalise, "token:chauvinism"), (admit, "token:chauvinism")]),
            ("ADISCORD_Vorkerland_wkr.txt", "WKR_siege_republic_of_front_soviets", [(admit, "token:anarchism")]),
        ]:
            with self.subTest(focus=focus_id):
                reward = focus_reward(tree, focus_id)
                self.assertEqual(self.party_actions(reward), expected)
                if focus_id in ("RUS_scientists_council", "RUS_black_army_oath"):
                    grant, = (e.value for e in reward if e.key == "if" and self.party_actions(e.value))
                    self.assertEqual(scalar(block(grant, "limit"), "RUS_khan_governing"), "yes")
                self.assertFalse(any(row.key == "ADISCORD_ban_party" for row in walk(reward)))

        vorkerland = parsed(directory / "ADISCORD_vorkerland_effects.txt")
        artels = "TVA_seat_independent_artels"
        self.assertEqual(self.party_actions(block(vorkerland, artels)), [(admit, "token:anarchism")])
        charter = focus_reward("ADISCORD_Vorkerland_tva.txt", "TVA_protocol_collegium_charter")
        self.assertEqual(scalar(charter, artels), "yes")
        events = parsed(ROOT / "events/ADISCORD_vorkerland_events.txt")
        mandate_id = "ADISCORD_vorkerland_directorate_cw.5"
        mandate, = (row.value for row in events if row.key == "country_event"
                    and scalar(row.value, "id") == mandate_id)
        seats = {scalar(option.value, "name"): any(entry.key == artels for entry in option.value)
                 for option in mandate if option.key == "option"}
        self.assertEqual(seats, {mandate_id + ".a": True, mandate_id + ".b": False, mandate_id + ".c": True})

        formed = block(block(block(vorkerland, "ADISCORD_vorkerland_form_joint_government"), "if"), "VAD")
        self.assertEqual(self.party_actions(formed), [(admit, "token:anarchism")])
        reunified = block(vorkerland, "ADISCORD_vorkerland_settle_unification_under_vad")
        self.assertEqual(self.party_actions(reunified), [(admit, "token:anarchism")])
        empire = block(vorkerland, "ADISCORD_vorkerland_initialize_world_empire")
        self.assertEqual(scalar(empire, "ADISCORD_end_party_coalition"), "yes")
        monopoly = focus_reward("ADISCORD_Vorkerland_world_empire.txt", "WRK_empire_state_union")
        bans = block(block(monopoly, "hidden_effect"), "for_each_loop")
        self.assertEqual(scalar(bans, "array"), "global.ideology_groups")
        self.assertEqual(scalar(bans, "value"), "ADISCORD_party")
        self.assertEqual(scalar(bans, "ADISCORD_ban_party"), "yes")

        transfers = block(parsed(directory / "ADISCORD_IVN_scripted_effects.txt"), "IVN_cw_transfer_reserves")
        for entry in transfers:
            if entry.key != "if":
                continue
            guarantees = [row.value for row in block(entry.value, "limit") if row.key == "has_idea"]
            if guarantees:
                recipient = block(entry.value, "event_target:IVN_cw_recipient")
                expected = [(admit, "token:etatism")] if "IVN_cw_military_guarantees" in guarantees else []
                self.assertEqual(self.party_actions(recipient), expected)
        self.assertEqual(self.party_actions(transfers), [(admit, "token:etatism")])

    def test_steland_cabinet_is_updated_on_appointments_and_government_handoffs(self):
        update = "STP_ch_update_cabinet_parties"
        effects = parsed(ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        regency = block(block(effects, update), "if")
        self.assertEqual(scalar(block(regency, "limit"), "has_country_flag"), "STP_ch_protectorate_leader")
        self.assertEqual(scalar(regency, "ADISCORD_end_party_coalition"), "yes")
        court, = (e.value for e in block(effects, update) if e.key == "else_if"
                  and scalar(block(e.value, "limit"), "has_government") == "hedonism")
        ministry = block(court, "if")
        self.assertEqual(scalar(block(ministry, "limit"), "has_variable"), "STP_ch_security_ministry")
        self.assertEqual(self.party_actions(court), [
            ("ADISCORD_legalise_party", "token:etatism"),
            ("ADISCORD_admit_coalition_party", "token:etatism"),
            ("ADISCORD_remove_coalition_party", "token:etatism"),
        ])
        for candidate in range(1, 7):
            leader = block(effects, f"STP_ch_leader_{candidate}")
            keys = [entry.key for entry in leader]
            self.assertLess(keys.index("set_politics"), keys.index(update))
        events = parsed(ROOT / "events/ADISCORD_STP_events.txt")
        cabinet, = (entry.value for entry in events if entry.key == "country_event"
                    and scalar(entry.value, "id") == "ADISCORD_STP_pc.23")
        for option in (entry.value for entry in cabinet if entry.key == "option"):
            name = scalar(option, "name")
            with self.subTest(option=name):
                self.assertEqual(any(row.key == update for row in walk(option)),
                                 name.endswith((".apparatus", ".delegates")))
        decisions = parsed(ROOT / "common/decisions/ADISCORD_STP_decisions.txt")
        for name in ("security_ministry_1", "security_ministry_2", "economy_ministry_1", "economy_ministry_2"):
            decision, = (row.value for row in walk(decisions) if row.key == f"STP_ch_appoint_{name}")
            actions = list(walk(block(decision, "complete_effect")))
            self.assertEqual(any(row.key == update for row in actions), name != "economy_ministry_2")

    def test_initial_support_sums_to_one_hundred_without_unanimous_rule(self):
        for tag, history in self.histories.items():
            with self.subTest(tag=tag):
                support = {entry.key: float(entry.value) for entry in block(history, "set_popularities")}
                self.assertEqual(sum(support.values()), 100)
                self.assertTrue(all(0 <= value < 100 for value in support.values()))

    def test_route_names_only_target_non_story_representatives_and_have_callers(self):
        effects = {}
        for path in (ROOT / "common/scripted_effects").glob("*.txt"):
            effects.update({entry.key: entry.value for entry in parsed(path)})
        profiles = {
            key: body for key, body in effects.items()
            if re.fullmatch(r"[A-Z]{3}_party_representatives_\w+", key)
        }
        self.assertEqual(len(profiles), 39)
        self.assertTrue({"NAM_party_representatives_exile_radical", "NAM_party_representatives_exile_humanist"}.isdisjoint(profiles))
        names_by_country = {}
        for name, body in profiles.items():
            tag = name[:3]
            with self.subTest(profile=name):
                self.assertEqual(scalar(block(block(body, "if"), "limit"), "tag"), PROFILE_COUNTRIES.get(tag, tag))
                callers = [key for key, value in effects.items() if key != name and any(entry.key == name for entry in walk(value))]
                self.assertTrue(callers, name)
                hidden = block(block(body, "if"), "hidden_effect")
                renames = [entry.value for entry in hidden if entry.key == "if"]
                self.assertTrue(renames)
                self.assertEqual(len(renames), len(hidden))
                expected_names = {
                    f"{name}_{group}" for group in self.groups
                    if f"{name}_{group}" in self.localisation["russian"]
                }
                self.assertCountEqual(
                    [scalar(block(rename, "set_character_name"), "name") for rename in renames],
                    expected_names,
                )
                for rename in renames:
                    action = block(rename, "set_character_name")
                    character = scalar(action, "character")
                    guard = block(rename, "limit")
                    self.assertEqual(scalar(guard, "has_character"), character)
                    ruling = block(block(guard, "NOT"), "has_country_leader")
                    self.assertEqual(scalar(ruling, "character"), character)
                    # has_country_leader defaults to the ruling character.
                    self.assertFalse(any(entry.key == "ruling_only" and entry.value != "yes" for entry in ruling))
                    self.assertTrue(character.startswith(tag + "_party_representative_"))
                    self.assertIn(character, self.characters)
                    key = scalar(action, "name")
                    self.assertEqual(key, name + "_" + character.split("_party_representative_")[1])
                    for language, entries in self.localisation.items():
                        self.assertEqual(len(entries.get(key, [])), 1, (language, key))
                    value = self.localisation["russian"][key][0][1]
                    self.assertNotIn(value, names_by_country.setdefault(tag, set()))
                    names_by_country[tag].add(value)

    def test_vorkerland_unifier_holds_the_roster_its_route_names_address(self):
        effects = {
            entry.key: entry.value
            for entry in parsed(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        }
        adoption = effects["ADISCORD_vorkerland_adopt_retired_roster"]
        transfer = block(block(block(adoption, "WRK"), "every_character"), "set_nationality")
        self.assertEqual(scalar(transfer, "target_country"), NATION_TARGET)
        for winner in ("wkr", "vad", "tva"):
            with self.subTest(winner=winner):
                steps = [entry.key for entry in effects[f"ADISCORD_vorkerland_unify_under_{winner}"]]
                # The roster moves once the target names the winner, before the
                # delayed settlement applies the route names.
                self.assertLess(steps.index("save_global_event_target_as"),
                                steps.index("ADISCORD_vorkerland_adopt_retired_roster"))
                self.assertLess(steps.index("ADISCORD_vorkerland_adopt_retired_roster"),
                                steps.index("country_event"))

    def test_nam_collapse_reduces_support_once_before_the_announcement(self):
        effects = parsed(ROOT / "common/scripted_effects/ADISCORD_nam_resource_war_effects.txt")
        declaration = block(effects, "NAM_ladder_declare_independence")
        facts = {
            ("NAM", "exists", "yes"): True,
            ("NAM", "has_global_flag", "ADISCORD_fresh_campaign_contract_v1"): True,
        }
        first = block(declaration, "if")
        self.assertTrue(matches_conditions(block(first, "limit"), facts, "NAM"))
        support = {entry.key: float(entry.value) for entry in block(first, "set_popularities")}
        initial = float(scalar(block(self.histories["NAM"], "set_popularities"), "etatism"))
        self.assertEqual(initial, 65)
        self.assertEqual(support["etatism"], 45)
        self.assertEqual(sum(support.values()), 100)
        self.assertLess([entry.key for entry in first].index("set_popularities"), [entry.key for entry in first].index("country_event"))
        self.assertTrue(any(
            entry.key == "set_country_flag" and entry.value == "NAM_independence_declared"
            for entry in first
        ))
        facts[("NAM", "has_country_flag", "NAM_independence_declared")] = True
        self.assertFalse(matches_conditions(block(first, "limit"), facts, "NAM"))


if __name__ == "__main__":
    unittest.main()

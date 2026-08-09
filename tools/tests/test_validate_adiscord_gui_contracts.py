import re
import unittest
from pathlib import Path

from tools.validators import validate_adiscord_economy_ai as economy_validator
from tools.validators.validate_adiscord_economy_ai import policy_selector_issues


ROOT = Path(__file__).resolve().parents[2]
GUI_NODE_RE = re.compile(
    r'(?P<type>[A-Za-z_][A-Za-z0-9_]*Type)\s*=\s*\{'
    r'|(?P<name>name\s*=\s*"(?P<name_value>[^"]+)")'
    r'|(?P<open>\{)'
    r'|(?P<close>\})'
)


def named_gui_nodes(text):
    stack = []
    pending_type = None
    nodes = []

    for match in GUI_NODE_RE.finditer(text):
        if match.group('type'):
            pending_type = match.group('type')
            stack.append({'type': pending_type, 'name': None})
            pending_type = None
        elif match.group('open'):
            stack.append({'type': None, 'name': None})
        elif match.group('close'):
            if stack:
                stack.pop()
        elif match.group('name') and stack and stack[-1]['type']:
            stack[-1]['name'] = match.group('name_value')
            parent_names = tuple(
                node['name'] for node in stack[:-1] if node['type'] and node['name']
            )
            nodes.append((stack[-1]['type'], stack[-1]['name'], parent_names))

    return nodes


def gui_node_body(text, name):
    """Return one balanced GUI type block whose own name matches *name*."""

    bodies = []
    for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*Type\s*=\s*\{", text):
        opening = text.find("{", match.start())
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    body = text[opening + 1 : index]
                    own_name = re.search(r'\bname\s*=\s*"([^"]+)"', body)
                    if own_name and own_name.group(1) == name:
                        bodies.append(body)
                    break
        else:
            raise AssertionError(f"unclosed GUI node while looking for {name}")
    if len(bodies) != 1:
        raise AssertionError(f"expected one GUI node {name}, found {len(bodies)}")
    return bodies[0]


def localisation_value(text, key):
    match = re.search(
        rf'(?m)^\s*{re.escape(key)}:\d*\s+"((?:[^"\\]|\\.)*)"\s*$',
        text,
    )
    if not match:
        raise AssertionError(f"missing localisation key {key}")
    return match.group(1)


def named_assignment_body(text, assignment, name, identity_key='name'):
    bodies = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(assignment)}\s*=\s*\{{", text):
        opening = text.find("{", match.start())
        depth = 0
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    body = text[opening + 1 : index]
                    assigned_name = re.search(
                        rf"\b{re.escape(identity_key)}\s*=\s*([A-Za-z0-9_.-]+)",
                        body,
                    )
                    if assigned_name and assigned_name.group(1) == name:
                        bodies.append(body)
                    break
        else:
            raise AssertionError(f"unclosed {assignment} while looking for {name}")
    if len(bodies) != 1:
        raise AssertionError(
            f"expected one {assignment} named {name}, found {len(bodies)}"
        )
    return bodies[0]


def _walk_clausewitz(entries):
    for entry in entries:
        yield entry
        if isinstance(entry.value, list):
            yield from _walk_clausewitz(entry.value)


def _direct_clausewitz(entries, key):
    return [entry for entry in entries if entry.key == key]


def _direct_scalar(entries, key):
    values = [
        entry.value
        for entry in entries
        if entry.key == key and isinstance(entry.value, str)
    ]
    return values[0] if len(values) == 1 else None


def _unique_direct_block(entries, key):
    matches = [
        entry
        for entry in entries
        if entry.key == key and isinstance(entry.value, list)
    ]
    return matches[0].value if len(matches) == 1 else None


def _scripted_gui_dashboard_sections(text):
    try:
        ast = economy_validator.parse_clausewitz(text)
    except ValueError:
        return None
    roots = [
        entry
        for entry in ast
        if entry.key == 'scripted_gui' and isinstance(entry.value, list)
    ]
    if len(roots) != 1:
        return None
    dashboards = [
        entry
        for entry in roots[0].value
        if entry.key == 'ADISCORD_economy_dashboard_script'
        and isinstance(entry.value, list)
    ]
    if len(dashboards) != 1:
        return None
    dashboard = dashboards[0].value
    sections = {
        section: _unique_direct_block(dashboard, section)
        for section in ('effects', 'triggers', 'properties')
    }
    sections['all_effects'] = [
        effect
        for owner in roots[0].value
        if isinstance(owner.value, list)
        for effect_section in owner.value
        if effect_section.key == 'effects' and isinstance(effect_section.value, list)
        for effect in effect_section.value
    ]
    return sections


def _gui_position(body):
    match = re.search(
        r'\bposition\s*=\s*\{\s*x\s*=\s*(-?\d+)\s+y\s*=\s*(-?\d+)\s*\}',
        body,
    )
    return tuple(map(int, match.groups())) if match else None


def _gui_size(body):
    explicit = re.search(
        r'\bsize\s*=\s*\{\s*(?:x|width)\s*=\s*(\d+)\s+'
        r'(?:y|height)\s*=\s*(\d+)\s*\}',
        body,
    )
    if explicit:
        return tuple(map(int, explicit.groups()))
    width = re.search(r'\bmaxWidth\s*=\s*(\d+)', body)
    height = re.search(r'\bmaxHeight\s*=\s*(\d+)', body)
    if width and height:
        return int(width.group(1)), int(height.group(1))
    return None


def economy_policy_ui_issues(gui, scripted_gui, scripted_loc):
    """Return semantic Task 9 UI graph and geometry violations.

    The checks deliberately bind the rendered controls to their direct
    scripted-GUI owners.  Comments, quoted diagnostic strings, and unrelated
    economy mechanics are not treated as policy actions.
    """

    issues = []
    policies = ('tax', 'army', 'research', 'social')
    directions = ('decrease', 'increase')
    mode_vars = {
        'tax': 'ADISCORD_economy_tax_burden_mode',
        'army': 'ADISCORD_economy_army_spending_mode',
        'research': 'ADISCORD_economy_research_spending_mode',
        'social': 'ADISCORD_economy_social_spending_mode',
    }
    cooldown_vars = {
        'tax': 'ADISCORD_economy_tax_change_cooldown',
        'army': 'ADISCORD_economy_army_budget_change_cooldown',
        'research': 'ADISCORD_economy_research_budget_change_cooldown',
        'social': 'ADISCORD_economy_social_budget_change_cooldown',
    }
    effects = {
        ('tax', 'decrease'): 'ADISCORD_economy_decrease_tax_burden',
        ('tax', 'increase'): 'ADISCORD_economy_increase_tax_burden',
        ('army', 'decrease'): 'ADISCORD_economy_decrease_army_spending',
        ('army', 'increase'): 'ADISCORD_economy_increase_army_spending',
        ('research', 'decrease'): 'ADISCORD_economy_decrease_research_spending',
        ('research', 'increase'): 'ADISCORD_economy_increase_research_spending',
        ('social', 'decrease'): 'ADISCORD_economy_decrease_social_spending',
        ('social', 'increase'): 'ADISCORD_economy_increase_social_spending',
    }
    enabled = {
        key: value.replace('ADISCORD_economy_decrease_', 'ADISCORD_economy_can_decrease_')
        .replace('ADISCORD_economy_increase_', 'ADISCORD_economy_can_increase_')
        for key, value in effects.items()
    }

    node_list = named_gui_nodes(gui)
    node_names = [name for _, name, _ in node_list]
    duplicate_nodes = sorted(
        name for name in set(node_names) if node_names.count(name) > 1
    )
    if duplicate_nodes:
        issues.append(f'GUI node names are duplicated: {duplicate_nodes}')
    policy_rows = [
        match.group(1)
        for name in node_names
        if (match := re.fullmatch(
            r'ADISCORD_economy_(tax|army|research|social|construction)_row',
            name,
        ))
    ]
    if policy_rows != list(policies):
        issues.append(f'policy row order/identity is {policy_rows!r}')

    expected_buttons = {
        f'ADISCORD_economy_{policy}_{direction}'
        for policy in policies
        for direction in directions
    }
    policy_buttons = {
        name
        for kind, name, _ in node_list
        if kind == 'buttonType'
        and re.fullmatch(
            r'ADISCORD_economy_(?:tax|army|research|social|construction)_(?:decrease|increase)',
            name,
        )
    }
    if policy_buttons != expected_buttons:
        issues.append('GUI does not expose exactly eight canonical policy buttons')

    sections = _scripted_gui_dashboard_sections(scripted_gui)
    if not sections or any(sections[section] is None for section in sections):
        issues.append('dashboard scripted-GUI sections are missing or duplicated')
        return issues
    effect_entries = sections['effects']
    ownership_effect_entries = sections['all_effects']
    trigger_entries = sections['triggers']
    property_entries = sections['properties']

    protected_targets = set(effects.values())
    target_invocations = []
    for owner in ownership_effect_entries:
        if not isinstance(owner.value, list):
            continue
        for operation in owner.value:
            if operation.key in protected_targets:
                target_invocations.append(
                    (operation.key, owner.key, operation.value, True)
                )
            if isinstance(operation.value, list):
                for nested in _walk_clausewitz(operation.value):
                    if nested.key in protected_targets:
                        target_invocations.append(
                            (nested.key, owner.key, nested.value, False)
                        )
    for (policy, direction), target in effects.items():
        expected_owner = f'ADISCORD_economy_{policy}_{direction}_click'
        matches = [call for call in target_invocations if call[0] == target]
        if matches != [(target, expected_owner, 'yes', True)]:
            issues.append(
                f'{target} is not called exactly once by its canonical click owner'
            )

    gui_buttons = {
        name for kind, name, _ in node_list if kind == 'buttonType'
    }
    click_owner_names = [
        entry.key
        for entry in ownership_effect_entries
        if entry.key.endswith('_click') and isinstance(entry.value, list)
    ]
    duplicate_clicks = sorted(
        name for name in set(click_owner_names) if click_owner_names.count(name) > 1
    )
    if duplicate_clicks:
        issues.append(f'scripted click owners are duplicated: {duplicate_clicks}')
    owned_clicks = {name[:-6] for name in click_owner_names}
    missing_owners = sorted(gui_buttons - owned_clicks)
    dead_owners = sorted(owned_clicks - gui_buttons)
    if missing_owners:
        issues.append(f'GUI buttons lack direct click owners: {missing_owners}')
    if dead_owners:
        issues.append(f'scripted clicks lack GUI buttons: {dead_owners}')

    expected_clicks = {f'{name}_click' for name in expected_buttons}
    live_policy_clicks = {
        entry.key
        for entry in effect_entries
        if re.fullmatch(
            r'ADISCORD_economy_(?:tax|army|research|social|construction)_(?:decrease|increase)_click',
            entry.key,
        )
    }
    if live_policy_clicks != expected_clicks:
        issues.append('scripted GUI does not own exactly eight policy clicks')

    row_rects = []
    command_parent = (
        'ADISCORD_economy_dashboard_window',
        'ADISCORD_economy_command_panel',
    )
    for policy in policies:
        row_name = f'ADISCORD_economy_{policy}_row'
        row_nodes = [
            (kind, parents)
            for kind, name, parents in node_list
            if name == row_name
        ]
        if row_nodes != [('instantTextboxType', command_parent)]:
            issues.append(f'{row_name} has the wrong command-panel parent')
        try:
            row = gui_node_body(gui, row_name)
        except AssertionError as error:
            issues.append(str(error))
            continue
        row_pos = _gui_position(row)
        row_size = _gui_size(row)
        if row_pos is None or row_size is None:
            issues.append(f'{policy} row lacks explicit geometry')
            continue
        x, y = row_pos
        width, height = row_size
        if width < 440 or height < 36:
            issues.append(f'{policy} row is not a useful full-row hover surface')
        if not (0 <= x and 0 <= y and x + width <= 480 and y + height <= 420):
            issues.append(f'{policy} row leaves the command panel')
        if f'pdx_tooltip = "ADISCORD_economy_{policy}_controls_tt"' not in row:
            issues.append(f'{policy} row lacks its current-policy tooltip')
        row_rects.append((policy, x, y, width, height))

        children = []
        for child_name in (
            f'ADISCORD_economy_{policy}_scale',
            f'ADISCORD_economy_{policy}_decrease',
            f'ADISCORD_economy_{policy}_increase',
        ):
            expected_kind = (
                'containerWindowType' if child_name.endswith('_scale') else 'buttonType'
            )
            child_nodes = [
                (kind, parents)
                for kind, name, parents in node_list
                if name == child_name
            ]
            if child_nodes != [(expected_kind, command_parent)]:
                issues.append(f'{child_name} has the wrong command-panel parent')
            try:
                child = gui_node_body(gui, child_name)
            except AssertionError as error:
                issues.append(str(error))
                continue
            child_pos = _gui_position(child)
            child_size = _gui_size(child)
            if child_pos is None or child_size is None:
                issues.append(f'{child_name} lacks explicit geometry')
                continue
            children.append((child_name, *child_pos, *child_size))
        for child_name, child_x, child_y, child_w, child_h in children:
            if not (
                x <= child_x
                and y <= child_y
                and child_x + child_w <= x + width
                and child_y + child_h <= y + height
            ):
                issues.append(f'{child_name} is outside its owning row')

        for level, marker_x in enumerate((0, 24, 48, 72, 96), start=1):
            marker_name = f'ADISCORD_economy_{policy}_step_{level}'
            marker_nodes = [
                (kind, parents)
                for kind, name, parents in node_list
                if name == marker_name
            ]
            if marker_nodes != [
                ('iconType', (
                    'ADISCORD_economy_dashboard_window',
                    'ADISCORD_economy_command_panel',
                    f'ADISCORD_economy_{policy}_scale',
                ))
            ]:
                issues.append(f'{marker_name} is missing, duplicated, or disconnected')
                continue
            marker = gui_node_body(gui, marker_name)
            if _gui_position(marker) != (marker_x, 0):
                issues.append(f'{marker_name} has the wrong level position')
            if 'alwaystransparent = yes' in marker:
                issues.append(f'{marker_name} cannot receive hover input')
            if f'pdx_tooltip = "ADISCORD_economy_{policy}_level_{level}_tt"' not in marker:
                issues.append(f'{marker_name} lacks its level tooltip')

        for direction in directions:
            button = f'ADISCORD_economy_{policy}_{direction}'
            click = _direct_clausewitz(effect_entries, f'{button}_click')
            if not (
                len(click) == 1
                and isinstance(click[0].value, list)
                and len(click[0].value) == 1
                and click[0].value[0].key == effects[(policy, direction)]
                and click[0].value[0].value == 'yes'
            ):
                issues.append(f'{button} does not delegate once to its targeted effect')
            gate = _direct_clausewitz(trigger_entries, f'{button}_click_enabled')
            if not (
                len(gate) == 1
                and isinstance(gate[0].value, list)
                and len(gate[0].value) == 1
                and gate[0].value[0].key == enabled[(policy, direction)]
                and gate[0].value[0].value == 'yes'
            ):
                issues.append(f'{button} has the wrong direct availability owner')

            title = 'Army' if policy == 'army' else policy.title()
            reason_selector = (
                f'GetADISCORDEconomy{title}{direction.title()}PreviewLoc'
            )
            issues.extend(
                economy_validator.policy_selector_issues(
                    scripted_loc,
                    reason_selector,
                    mode_vars[policy],
                    cooldown_vars[policy],
                    direction,
                )
            )
            effect_selector = (
                f'GetADISCORDEconomy{title}{direction.title()}EffectLoc'
            )
            issues.extend(
                economy_validator.policy_effect_selector_issues(
                    scripted_loc,
                    effect_selector,
                    f'ADISCORD_economy_{policy}_{direction}_target_level',
                    f'ADISCORD_economy_{policy}_effects',
                )
            )

        marker_owner = _direct_clausewitz(
            trigger_entries, f'ADISCORD_economy_{policy}_active_marker_visible'
        )
        if not (
            len(marker_owner) == 1
            and isinstance(marker_owner[0].value, list)
        ):
            issues.append(f'{policy} active marker has no unique trigger owner')
        else:
            tokens = [
                value
                for entry in _walk_clausewitz(marker_owner[0].value)
                for value in (entry.key, entry.value)
                if isinstance(value, str)
            ]
            if mode_vars[policy] not in tokens:
                issues.append(f'{policy} active marker uses the wrong mode')
            for position in ('0', '24', '48', '72', '96'):
                if position not in tokens:
                    issues.append(f'{policy} active marker misses position {position}')
        marker_property = _direct_clausewitz(
            property_entries, f'ADISCORD_economy_{policy}_active_marker'
        )
        if len(marker_property) != 1:
            issues.append(f'{policy} active marker lacks a unique property owner')

    ordered_rects = sorted(row_rects, key=lambda item: item[2])
    if [item[0] for item in ordered_rects] != list(policies):
        issues.append('policy rows do not preserve vertical order')
    for previous, current in zip(ordered_rects, ordered_rects[1:]):
        if previous[2] + previous[4] > current[2]:
            issues.append(f'{previous[0]} and {current[0]} rows overlap')

    for source_name, source in (
        ('GUI', gui),
        ('scripted GUI', scripted_gui),
        ('scripted localisation', scripted_loc),
    ):
        try:
            tokens = [
                value
                for entry in _walk_clausewitz(
                    economy_validator.parse_clausewitz(source)
                )
                for value in (entry.key, entry.value)
                if isinstance(value, str)
            ]
        except ValueError:
            issues.append(f'{source_name} does not parse')
            continue
        if any(
            token.startswith('ADISCORD_economy_construction_')
            or token.startswith('GetADISCORDConstruction')
            for token in tokens
        ):
            issues.append(f'{source_name} retains a construction-policy UI alias')

    return issues


class CountryPoliticsGuiContractTests(unittest.TestCase):
    def test_hoi4_119_faction_widgets_have_required_types_and_parents(self):
        text = (ROOT / 'interface' / 'countrypoliticsview.gui').read_text(
            encoding='utf-8-sig'
        )
        nodes = set(named_gui_nodes(text))

        required = {
            ('iconType', 'pol_faction_icon', ('countrypoliticsview',)),
            ('containerWindowType', 'faction', ('countrypoliticsview', 'ruling_party_info')),
            (
                'containerWindowType',
                'no_faction',
                ('countrypoliticsview', 'ruling_party_info', 'faction'),
            ),
            (
                'containerWindowType',
                'original_in_faction',
                ('countrypoliticsview', 'ruling_party_info', 'faction'),
            ),
            (
                'containerWindowType',
                'in_faction',
                ('countrypoliticsview', 'ruling_party_info', 'faction'),
            ),
            (
                'instantTextboxType',
                'manage_exiled_collaborations_governments',
                ('countrypoliticsview',),
            ),
            (
                'iconType',
                'icon_exiled_collaborations_governments',
                ('countrypoliticsview',),
            ),
            ('iconType', 'icon_occupied_territories', ('countrypoliticsview',)),
            ('iconType', 'icon_manage_subjects', ('countrypoliticsview',)),
        }

        self.assertEqual(required - nodes, set())

    def test_development_panel_is_bottom_anchored_and_law_list_reserves_room(self):
        development_text = (
            ROOT / 'interface' / 'ADISCORD_CountryView.gui'
        ).read_text(encoding='utf-8-sig')
        politics_text = (
            ROOT / 'interface' / 'countrypoliticsview.gui'
        ).read_text(encoding='utf-8-sig')

        self.assertRegex(
            development_text,
            r'(?s)name\s*=\s*"ADISCORD_development_category_society_type"'
            r'.{0,500}?position\s*=\s*\{\s*x\s*=\s*-10\s+y\s*=\s*-315\s*\}'
            r'.{0,200}?size\s*=\s*\{\s*width\s*=\s*594\s+height\s*=\s*315\s*\}'
            r'.{0,200}?Orientation\s*=\s*LOWER_LEFT',
        )
        self.assertRegex(
            politics_text,
            r'(?s)name\s*=\s*"ideas"'
            r'.{0,500}?position\s*=\s*\{\s*x\s*=\s*0\s+y\s*=\s*545\s*\}'
            r'.{0,200}?size\s*=\s*\{\s*width\s*=\s*570\s+height\s*=\s*-315\s*\}',
        )


class DiplomacyGuiContractTests(unittest.TestCase):
    def test_national_spirit_row_reserves_full_idea_icon_height(self):
        text = (ROOT / 'interface' / 'countrydiplomacyview.gui').read_text(
            encoding='utf-8-sig'
        )

        self.assertRegex(
            text,
            r'(?s)name\s*=\s*"national_spirit_info"'
            r'.{0,200}?position\s*=\s*\{\s*x\s*=\s*17\s+y\s*=\s*285\s*\}'
            r'.{0,100}?size\s*=\s*\{\s*width\s*=\s*530\s+height\s*=\s*80\s*\}',
        )
        self.assertRegex(
            text,
            r'(?s)name\s*=\s*"national_spirit_container"'
            r'.{0,200}?position\s*=\s*\{\s*x\s*=\s*-380\s+y\s*=\s*-5\s*\}'
            r'.{0,100}?size\s*=\s*\{\s*width\s*=\s*375\s+height\s*=\s*84\s*\}',
        )
        self.assertRegex(
            text,
            r'(?s)name\s*=\s*"national_spirit_ideas_grid"'
            r'.{0,200}?position\s*=\s*\{\s*x\s*=\s*3\s+y\s*=\s*2\s*\}',
        )
        for grid_name, width in (
            ('national_spirit_ideas_grid', 360),
            ('nat_spirit_ideas_grid_over_defined', 330),
        ):
            self.assertRegex(
                text,
                rf'(?s)name\s*=\s*"{grid_name}"'
                rf'.{{0,200}}?size\s*=\s*\{{\s*width\s*=\s*{width}\s+height\s*=\s*80\s*\}}',
            )

        for pane_name, x in (('relations_info', 11), ('diplomatic_actions', 272)):
            self.assertRegex(
                text,
                rf'(?s)name\s*=\s*"{pane_name}"'
                rf'.{{0,200}}?position\s*=\s*\{{\s*x\s*=\s*{x}\s+y\s*=\s*365\s*\}}',
            )


class NationalFocusGuiContractTests(unittest.TestCase):
    def test_hoi4_119_focus_item_has_overlay_icon(self):
        text = (ROOT / 'interface' / 'nationalfocusview.gui').read_text(
            encoding='utf-8-sig'
        )
        nodes = set(named_gui_nodes(text))

        self.assertIn(
            ('iconType', 'overlay', ('national_focus_item',)),
            nodes,
        )


class EconomyDefinedTextFixtureTests(unittest.TestCase):
    VALID = """
defined_text = {
 name = GetADISCORDEconomyTaxDecreasePreviewLoc
 text = { trigger = { check_variable = { var = ADISCORD_economy_tax_burden_mode value = 1 compare = less_than_or_equals } } localization_key = ADISCORD_economy_policy_blocked_minimum }
 text = { trigger = { check_variable = { var = ADISCORD_economy_tax_change_cooldown value = 0 compare = greater_than } } localization_key = ADISCORD_economy_policy_blocked_cooldown }
 text = { trigger = { NOT = { ADISCORD_economy_should_show_player_ui = yes } } localization_key = ADISCORD_economy_policy_blocked_scope }
 text = { localization_key = ADISCORD_economy_policy_preview_available }
}
"""

    def issues(self, text):
        return policy_selector_issues(
            text,
            "GetADISCORDEconomyTaxDecreasePreviewLoc",
            "ADISCORD_economy_tax_burden_mode",
            "ADISCORD_economy_tax_change_cooldown",
            "decrease",
        )

    def test_defined_text_requires_ordered_trigger_to_reason_mapping(self):
        self.assertEqual(self.issues(self.VALID), [])
        swapped = self.VALID.replace(
            "ADISCORD_economy_policy_blocked_minimum",
            "ADISCORD_economy_policy_blocked_maximum",
        )
        wrong_trigger = self.VALID.replace(
            "var = ADISCORD_economy_tax_change_cooldown value = 0 compare = greater_than",
            "NOT = { ADISCORD_economy_should_show_player_ui = yes }",
        )
        dead = self.VALID.replace(
            " text = { trigger = { check_variable",
            " text = { localization_key = ADISCORD_economy_policy_preview_available }\n text = { trigger = { check_variable",
            1,
        )
        disconnected = self.VALID.replace(
            "name = GetADISCORDEconomyTaxDecreasePreviewLoc",
            "name = DisconnectedSelector",
        ) + "\ndefined_text = { name = GetADISCORDEconomyTaxDecreasePreviewLoc text = { localization_key = ADISCORD_economy_policy_preview_available } }"
        nested_dead_wrapper = f"ADISCORD_dead = {{ {self.VALID} }}"
        negated_boundary = self.VALID.replace(
            "trigger = { check_variable = { var = ADISCORD_economy_tax_burden_mode value = 1 compare = less_than_or_equals } }",
            "trigger = { NOT = { check_variable = { var = ADISCORD_economy_tax_burden_mode value = 1 compare = less_than_or_equals } } }",
            1,
        )
        contradictory_boundary = self.VALID.replace(
            "trigger = { check_variable = { var = ADISCORD_economy_tax_burden_mode value = 1 compare = less_than_or_equals } }",
            "trigger = { check_variable = { var = ADISCORD_economy_tax_burden_mode value = 1 compare = less_than_or_equals } always = no }",
            1,
        )
        for invalid in (
            swapped,
            wrong_trigger,
            dead,
            disconnected,
            nested_dead_wrapper,
            negated_boundary,
            contradictory_boundary,
        ):
            self.assertTrue(self.issues(invalid))


class EconomyDashboardGuiContractTests(unittest.TestCase):
    def setUp(self):
        self.gui = (ROOT / 'interface' / 'ADISCORD_economy.gui').read_text(
            encoding='utf-8-sig'
        )
        self.gfx = (ROOT / 'interface' / 'ADISCORD_economy.gfx').read_text(
            encoding='utf-8-sig'
        )
        self.scripted_gui = (
            ROOT / 'common' / 'scripted_guis' / 'ADISCORD_economy_scripted_gui.txt'
        ).read_text(encoding='utf-8-sig')
        self.scripted_loc = (
            ROOT
            / 'common'
            / 'scripted_localisation'
            / 'ADISCORD_economy_scripted_loc.txt'
        ).read_text(encoding='utf-8-sig')
        self.localisation = (
            ROOT / 'localisation' / 'russian' / 'ADISCORD_economy_l_russian.yml'
        ).read_text(encoding='utf-8-sig')
        self.events = (
            ROOT / 'events' / 'ADISCORD_economy_events.txt'
        ).read_text(encoding='utf-8-sig')
        self.nodes = set(named_gui_nodes(self.gui))

    def test_policy_ui_graph_geometry_and_selectors_are_connected(self):
        self.assertEqual(
            economy_policy_ui_issues(
                self.gui, self.scripted_gui, self.scripted_loc
            ),
            [],
        )

    def test_policy_ui_graph_rejects_stable_invalid_mutations(self):
        self.assertEqual(
            economy_policy_ui_issues(
                self.gui, self.scripted_gui, self.scripted_loc
            ),
            [],
            'live Task 9 UI must be valid before testing mutations',
        )

        def replace_once(text, old, new):
            self.assertIn(old, text, f'mutation source is absent: {old}')
            return text.replace(old, new, 1)

        def move_single_line_node_to_gui_root(text, node_name):
            match = re.search(
                rf'(?m)^\s*[A-Za-z_][A-Za-z0-9_]*Type\s*=\s*\{{[^\r\n]*'
                rf'name\s*=\s*"{re.escape(node_name)}"[^\r\n]*\}}\s*$',
                text,
            )
            self.assertIsNotNone(match, f'mutation node is absent: {node_name}')
            node = match.group(0).strip()
            without_node = text[:match.start()] + text[match.end():]
            root_close = without_node.rfind('\n}')
            self.assertGreater(root_close, 0, 'GUI root close is absent')
            return (
                without_node[:root_close]
                + f'\n\t{node}\n'
                + without_node[root_close:]
            )

        research_effect_1 = (
            'text = { trigger = { check_variable = { var = '
            'ADISCORD_economy_research_increase_target_level value = 1 '
            'compare = less_than_or_equals } } localization_key = '
            'ADISCORD_economy_research_effects_1 }'
        )
        research_effect_2 = (
            'text = { trigger = { check_variable = { var = '
            'ADISCORD_economy_research_increase_target_level value = 2 '
            'compare = less_than_or_equals } } localization_key = '
            'ADISCORD_economy_research_effects_2 }'
        )

        gui_mutations = {
            'rows swapped': replace_once(
                replace_once(
                    self.gui,
                    'name = "ADISCORD_economy_tax_row"',
                    'name = "ADISCORD_economy_row_swap_temp"',
                ),
                'name = "ADISCORD_economy_army_row"',
                'name = "ADISCORD_economy_tax_row"',
            ).replace(
                'name = "ADISCORD_economy_row_swap_temp"',
                'name = "ADISCORD_economy_army_row"',
                1,
            ),
            'row overlap': replace_once(
                self.gui,
                'name = "ADISCORD_economy_army_row" position = { x = 20 y = 87 }',
                'name = "ADISCORD_economy_army_row" position = { x = 20 y = 60 }',
            ),
            'arrow outside owner': replace_once(
                self.gui,
                'name = "ADISCORD_economy_tax_increase" position = { x = 424 y = 47 }',
                'name = "ADISCORD_economy_tax_increase" position = { x = 450 y = 47 }',
            ),
            'marker made hover-transparent': replace_once(
                self.gui,
                'name = "ADISCORD_economy_tax_step_1" position = { x = 0 y = 0 }',
                'name = "ADISCORD_economy_tax_step_1" position = { x = 0 y = 0 } alwaystransparent = yes',
            ),
            'unowned orphan button': replace_once(
                self.gui,
                'name = "ADISCORD_economy_dashboard_close"',
                'name = "ADISCORD_economy_policy_orphan"',
            ),
            'duplicate policy node': replace_once(
                self.gui,
                'name = "ADISCORD_economy_tax_increase"',
                'name = "ADISCORD_economy_tax_decrease"',
            ),
            'policy button disconnected at GUI root': move_single_line_node_to_gui_root(
                self.gui, 'ADISCORD_economy_tax_decrease'
            ),
        }
        scripted_gui_mutations = {
            'wrong targeted effect': replace_once(
                self.scripted_gui,
                'ADISCORD_economy_tax_decrease_click = { ADISCORD_economy_decrease_tax_burden = yes }',
                'ADISCORD_economy_tax_decrease_click = { ADISCORD_economy_decrease_army_spending = yes }',
            ),
            'wrong availability trigger': replace_once(
                self.scripted_gui,
                'ADISCORD_economy_tax_decrease_click_enabled = { ADISCORD_economy_can_decrease_tax_burden = yes }',
                'ADISCORD_economy_tax_decrease_click_enabled = { ADISCORD_economy_can_decrease_army_spending = yes }',
            ),
            'ninth construction action': replace_once(
                self.scripted_gui,
                'ADISCORD_economy_social_increase_click = { ADISCORD_economy_increase_social_spending = yes }',
                'ADISCORD_economy_social_increase_click = { ADISCORD_economy_increase_social_spending = yes }\n'
                '\t\t\tADISCORD_economy_construction_increase_click = { ADISCORD_economy_increase_research_spending = yes }',
            ),
            'research marker reads army mode': self.scripted_gui.replace(
                'var = ADISCORD_economy_research_spending_mode',
                'var = ADISCORD_economy_army_spending_mode',
            ),
            'duplicate policy click across owners': replace_once(
                self.scripted_gui,
                'ADISCORD_economy_topbar_button_click = { ADISCORD_economy_open_window = yes }',
                'ADISCORD_economy_topbar_button_click = { ADISCORD_economy_open_window = yes }\n'
                '\t\t\tADISCORD_economy_tax_decrease_click = { ADISCORD_economy_decrease_tax_burden = yes }',
            ),
            'non-policy click invokes a ninth targeted effect': replace_once(
                self.scripted_gui,
                'ADISCORD_economy_dashboard_close_click = { ADISCORD_economy_close_window = yes }',
                'ADISCORD_economy_dashboard_close_click = { '
                'ADISCORD_economy_close_window = yes '
                'ADISCORD_economy_decrease_tax_burden = yes }',
            ),
        }
        scripted_loc_mutations = {
            'effect selector reads wrong direction': replace_once(
                self.scripted_loc,
                'var = ADISCORD_economy_research_increase_target_level value = 1',
                'var = ADISCORD_economy_research_decrease_target_level value = 1',
            ),
            'effect selector uses legacy key': replace_once(
                self.scripted_loc,
                'localization_key = ADISCORD_economy_research_effects_1',
                'localization_key = ADISCORD_economy_construction_effects_1',
            ),
            'reason selector hidden in wrapper': replace_once(
                self.scripted_loc,
                'name = GetADISCORDEconomyTaxDecreasePreviewLoc',
                'name = DeadTaxPreviewLoc',
            )
            + '\nADISCORD_dead_preview_owner = { defined_text = { '
            'name = GetADISCORDEconomyTaxDecreasePreviewLoc '
            'text = { localization_key = ADISCORD_economy_policy_preview_available } } }\n',
            'reason boundary is negated': replace_once(
                self.scripted_loc,
                'trigger = { check_variable = { var = '
                'ADISCORD_economy_tax_burden_mode value = 1 '
                'compare = less_than_or_equals } } localization_key = '
                'ADISCORD_economy_policy_blocked_minimum',
                'trigger = { NOT = { check_variable = { var = '
                'ADISCORD_economy_tax_burden_mode value = 1 '
                'compare = less_than_or_equals } } } localization_key = '
                'ADISCORD_economy_policy_blocked_minimum',
            ),
            'reason boundary is unsatisfiable': replace_once(
                self.scripted_loc,
                'trigger = { check_variable = { var = '
                'ADISCORD_economy_tax_burden_mode value = 1 '
                'compare = less_than_or_equals } } localization_key = '
                'ADISCORD_economy_policy_blocked_minimum',
                'trigger = { check_variable = { var = '
                'ADISCORD_economy_tax_burden_mode value = 1 '
                'compare = less_than_or_equals } always = no } '
                'localization_key = ADISCORD_economy_policy_blocked_minimum',
            ),
            'effect selector repeats the wrong threshold': replace_once(
                self.scripted_loc,
                research_effect_1,
                research_effect_1.replace('value = 1', 'value = 5', 1),
            ),
            'effect selector swaps level keys': replace_once(
                replace_once(
                    self.scripted_loc,
                    research_effect_1,
                    research_effect_1.replace(
                        'ADISCORD_economy_research_effects_1',
                        'ADISCORD_economy_research_effects_2',
                        1,
                    ),
                ),
                research_effect_2,
                research_effect_2.replace(
                    'ADISCORD_economy_research_effects_2',
                    'ADISCORD_economy_research_effects_1',
                    1,
                ),
            ),
        }

        for name, invalid_gui in gui_mutations.items():
            with self.subTest(gui_mutation=name):
                self.assertTrue(economy_validator.parse_clausewitz(invalid_gui))
                self.assertTrue(
                    economy_policy_ui_issues(
                        invalid_gui, self.scripted_gui, self.scripted_loc
                    )
                )
        for name, invalid_scripted_gui in scripted_gui_mutations.items():
            with self.subTest(scripted_gui_mutation=name):
                self.assertTrue(
                    economy_validator.parse_clausewitz(invalid_scripted_gui)
                )
                self.assertTrue(
                    economy_policy_ui_issues(
                        self.gui, invalid_scripted_gui, self.scripted_loc
                    )
                )
        for name, invalid_scripted_loc in scripted_loc_mutations.items():
            with self.subTest(scripted_loc_mutation=name):
                self.assertTrue(economy_validator.parse_clausewitz(invalid_scripted_loc))
                self.assertTrue(
                    economy_policy_ui_issues(
                        self.gui, self.scripted_gui, invalid_scripted_loc
                    )
                )

    def test_schema_twelve_policy_rows_are_tax_military_research_social(self):
        rows = re.findall(
            r'name\s*=\s*"ADISCORD_economy_(tax|army|construction|research|social)_row"',
            self.gui,
        )
        self.assertEqual(rows, ['tax', 'army', 'research', 'social'])
        regulators = set(
            re.findall(
                r'name\s*=\s*"(ADISCORD_economy_(?:tax|army|research|social)_(?:decrease|increase))"',
                self.gui,
            )
        )
        expected = {
            f'ADISCORD_economy_{policy}_{direction}'
            for policy in ('tax', 'army', 'research', 'social')
            for direction in ('decrease', 'increase')
        }
        self.assertEqual(regulators, expected)
        self.assertNotIn('ADISCORD_economy_construction_row', self.gui)
        for regulator in expected:
            self.assertEqual(self.scripted_gui.count(f'{regulator}_click ='), 1)
            self.assertEqual(self.scripted_gui.count(f'{regulator}_click_enabled ='), 1)

    def test_policy_rows_and_arrows_have_usable_hitboxes(self):
        for policy in ('tax', 'army', 'research', 'social'):
            row = gui_node_body(self.gui, f'ADISCORD_economy_{policy}_row')
            width = re.search(r'\bmaxWidth\s*=\s*(\d+)', row)
            height = re.search(r'\bmaxHeight\s*=\s*(\d+)', row)
            self.assertIsNotNone(width, policy)
            self.assertIsNotNone(height, policy)
            self.assertGreaterEqual(int(width.group(1)), 330, policy)
            self.assertGreaterEqual(int(height.group(1)), 36, policy)
            self.assertRegex(row, r'\bpdx_tooltip\s*=\s*"ADISCORD_economy_[^"]+"')

            for direction in ('decrease', 'increase'):
                arrow = gui_node_body(
                    self.gui, f'ADISCORD_economy_{policy}_{direction}'
                )
                size = re.search(
                    r'\bsize\s*=\s*\{\s*(?:x|width)\s*=\s*(\d+)\s+'
                    r'(?:y|height)\s*=\s*(\d+)\s*\}',
                    arrow,
                )
                self.assertIsNotNone(size, f'{policy} {direction} lacks explicit hitbox')
                self.assertGreaterEqual(int(size.group(1)), 32, f'{policy} {direction}')
                self.assertGreaterEqual(int(size.group(2)), 28, f'{policy} {direction}')

    def test_policy_arrows_preview_next_level_and_precise_disabled_reason(self):
        title_names = {
            'tax': 'Tax',
            'army': 'Army',
            'research': 'Research',
            'social': 'Social',
        }
        policy_variables = {
            'tax': ('ADISCORD_economy_tax_burden_mode', 'ADISCORD_economy_tax_change_cooldown'),
            'army': ('ADISCORD_economy_army_spending_mode', 'ADISCORD_economy_army_budget_change_cooldown'),
            'research': ('ADISCORD_economy_research_spending_mode', 'ADISCORD_economy_research_budget_change_cooldown'),
            'social': ('ADISCORD_economy_social_spending_mode', 'ADISCORD_economy_social_budget_change_cooldown'),
        }
        for policy, title in title_names.items():
            for level in range(1, 6):
                step = gui_node_body(
                    self.gui, f'ADISCORD_economy_{policy}_step_{level}'
                )
                self.assertIn(
                    f'pdx_tooltip = "ADISCORD_economy_{policy}_level_{level}_tt"',
                    step,
                )
            for direction in ('decrease', 'increase'):
                key = f'ADISCORD_economy_{policy}_{direction}_tt'
                tooltip = localisation_value(self.localisation, key)
                self.assertIn(
                    f'?ADISCORD_economy_{policy}_{direction}_target_level|0',
                    tooltip,
                )
                self.assertIn(
                    f'?ADISCORD_economy_{policy}_{direction}_weekly_balance_delta|=+1',
                    tooltip,
                )
                selector = (
                    f'GetADISCORDEconomy{title}{direction.title()}PreviewLoc'
                )
                self.assertIn(f'[{selector}]', tooltip)
                selector_block = named_assignment_body(
                    self.scripted_loc, 'defined_text', selector
                )
                mode_var, cooldown_var = policy_variables[policy]
                self.assertFalse(
                    policy_selector_issues(
                        self.scripted_loc,
                        selector,
                        mode_var,
                        cooldown_var,
                        direction,
                    )
                )
                boundary_reason = (
                    'ADISCORD_economy_policy_blocked_minimum'
                    if direction == 'decrease'
                    else 'ADISCORD_economy_policy_blocked_maximum'
                )
                for reason in (
                    boundary_reason,
                    'ADISCORD_economy_policy_blocked_cooldown',
                    'ADISCORD_economy_policy_blocked_scope',
                ):
                    self.assertIn(reason, selector_block)
                    self.assertRegex(self.localisation, rf'(?m)^\s*{reason}:')

    def test_primary_economy_values_have_short_and_delayed_explanations(self):
        contracts = {
            'ADISCORD_economy_kpi_treasury': (
                'ADISCORD_economy_treasury_tt',
                'ADISCORD_economy_treasury_delayed_tt',
                (
                    'ADISCORD_economy_weekly_income',
                    'ADISCORD_economy_weekly_expenses',
                    'ADISCORD_economy_safe_reserve',
                    'ADISCORD_economy_deficit_runway',
                ),
            ),
            'ADISCORD_economy_risk_debt': (
                'ADISCORD_economy_debt_tt',
                'ADISCORD_economy_debt_delayed_tt',
                (
                    'ADISCORD_economy_debt',
                    'ADISCORD_economy_weekly_interest',
                    'ADISCORD_economy_interest_share_income',
                    'ADISCORD_economy_debt_state',
                    'ADISCORD_economy_debt_emergency_streak',
                    'ADISCORD_economy_debt_default_streak',
                ),
            ),
            'ADISCORD_economy_risk_inflation': (
                'ADISCORD_economy_inflation_tt',
                'ADISCORD_economy_inflation_delayed_tt',
                (
                    'ADISCORD_economy_inflation',
                    'ADISCORD_economy_inflation_delta_temp',
                    'ADISCORD_economy_inflation_expense_multiplier',
                    'GetADISCORDInflationEffectsLoc',
                ),
            ),
        }
        for node_name, (short_key, delayed_key, required) in contracts.items():
            node = gui_node_body(self.gui, node_name)
            self.assertIn(f'pdx_tooltip = "{short_key}"', node)
            self.assertIn(f'pdx_tooltip_delayed = "{delayed_key}"', node)
            delayed = localisation_value(self.localisation, delayed_key)
            for token in required:
                self.assertIn(token, delayed, delayed_key)
        self.assertIn('4', localisation_value(self.localisation, 'ADISCORD_economy_debt_delayed_tt'))
        self.assertIn('13', localisation_value(self.localisation, 'ADISCORD_economy_debt_delayed_tt'))

    def test_debt_notification_uses_dynamic_human_event_not_recurring_custom_popup(self):
        self.assertNotIn('ADISCORD_economy_auto_loan_popup_window', self.gui)
        self.assertNotIn('ADISCORD_economy_auto_loan_popup_ok', self.gui)
        self.assertNotIn('ADISCORD_economy_auto_loan_popup_script', self.scripted_gui)
        self.assertNotIn('ADISCORD_economy_auto_loan_popup_ok_click', self.scripted_gui)
        event = named_assignment_body(
            self.events, 'country_event', 'ADISCORD_economy.3', identity_key='id'
        )
        self.assertIn('is_triggered_only = yes', event)
        self.assertIn('title = ADISCORD_economy.3.t', event)
        self.assertIn('desc = ADISCORD_economy.3.d', event)
        self.assertIn('name = ADISCORD_economy.3.a', event)
        description = localisation_value(
            self.localisation, 'ADISCORD_economy.3.d'
        )
        for selector in (
            'GetADISCORDEconomyDebtNotificationCauseLoc',
            'GetADISCORDEconomyDebtNotificationStateLoc',
            'GetADISCORDEconomyDebtNotificationNextRiskLoc',
        ):
            self.assertIn(f'[{selector}]', description)
            self.assertIn(f'name = {selector}', self.scripted_loc)
        for variable in (
            'ADISCORD_economy_pending_debt_notification_amount',
            'ADISCORD_economy_debt',
            'ADISCORD_economy_weekly_interest',
            'ADISCORD_economy_interest_share_income',
        ):
            self.assertIn(variable, description)

    def test_debt_notification_selectors_bind_exact_state_semantics(self):
        analyzer = getattr(economy_validator, 'debt_notification_selector_issues', None)
        self.assertIsNotNone(analyzer, 'missing parsed debt-notification selector validator')
        if analyzer is None:
            return
        self.assertEqual(analyzer(self.scripted_loc), [])
        mutations = {
            'kind five uses first-loan text': self.scripted_loc.replace(
                'value = 5 compare = equals } } localization_key = ADISCORD_economy_debt_notification_kind_default',
                'value = 5 compare = equals } } localization_key = ADISCORD_economy_debt_notification_kind_first_loan',
                1,
            ),
            'state four comparator reversed': self.scripted_loc.replace(
                'ADISCORD_economy_pending_debt_notification_new_state value = 4 compare = greater_than_or_equals } } localization_key = ADISCORD_economy_debt_notification_state_default',
                'ADISCORD_economy_pending_debt_notification_new_state value = 4 compare = less_than } } localization_key = ADISCORD_economy_debt_notification_state_default',
                1,
            ),
            'next state four falls back to healthy': self.scripted_loc.replace(
                'ADISCORD_economy_pending_debt_notification_new_state value = 4 compare = greater_than_or_equals } } localization_key = ADISCORD_economy_debt_notification_next_default',
                'ADISCORD_economy_pending_debt_notification_new_state value = 4 compare = greater_than_or_equals } } localization_key = ADISCORD_economy_debt_notification_next_healthy',
                1,
            ),
            'kind fallback made conditional': self.scripted_loc.replace(
                'text = { localization_key = ADISCORD_economy_debt_notification_kind_fallback }',
                'text = { trigger = { always = yes } localization_key = ADISCORD_economy_debt_notification_kind_fallback }',
                1,
            ),
            'state branches swapped': self.scripted_loc.replace(
                'text = { trigger = { check_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = 4 compare = greater_than_or_equals } } localization_key = ADISCORD_economy_debt_notification_state_default }\n'
                '\ttext = { trigger = { check_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = 3 compare = greater_than_or_equals } } localization_key = ADISCORD_economy_debt_notification_state_emergency }',
                'text = { trigger = { check_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = 3 compare = greater_than_or_equals } } localization_key = ADISCORD_economy_debt_notification_state_emergency }\n'
                '\ttext = { trigger = { check_variable = { var = ADISCORD_economy_pending_debt_notification_new_state value = 4 compare = greater_than_or_equals } } localization_key = ADISCORD_economy_debt_notification_state_default }',
                1,
            ),
            'next selector duplicated': self.scripted_loc.replace(
                'defined_text = {\n\tname = GetADISCORDEconomyDebtNotificationNextRiskLoc',
                'defined_text = { name = GetADISCORDEconomyDebtNotificationNextRiskLoc text = { localization_key = ADISCORD_economy_debt_notification_next_healthy } }\n\n'
                'defined_text = {\n\tname = GetADISCORDEconomyDebtNotificationNextRiskLoc',
                1,
            ),
            'kind selector has a second wrong name': self.scripted_loc.replace(
                'name = GetADISCORDEconomyDebtNotificationKindLoc',
                'name = GetADISCORDEconomyDebtNotificationKindLoc\n'
                '\tname = BrokenDebtNotificationSelector',
                1,
            ),
            'kind selector has a duplicate name': self.scripted_loc.replace(
                'name = GetADISCORDEconomyDebtNotificationKindLoc',
                'name = GetADISCORDEconomyDebtNotificationKindLoc\n'
                '\tname = GetADISCORDEconomyDebtNotificationKindLoc',
                1,
            ),
        }
        for selector in (
            'GetADISCORDEconomyDebtNotificationKindLoc',
            'GetADISCORDEconomyDebtNotificationCauseLoc',
            'GetADISCORDEconomyDebtNotificationStateLoc',
            'GetADISCORDEconomyDebtNotificationNextRiskLoc',
        ):
            mutations[f'{selector} rejects extra direct identity field'] = (
                self.scripted_loc.replace(
                    f'name = {selector}',
                    f'name = {selector}\n\talways = no',
                    1,
                )
            )
        for name, invalid in mutations.items():
            with self.subTest(selector_mutation=name):
                self.assertNotEqual(invalid, self.scripted_loc)
                self.assertTrue(economy_validator.parse_clausewitz(invalid))
                self.assertTrue(analyzer(invalid))

    def test_visible_diagnostic_money_slogan_is_absent(self):
        visible_keys = set(
            re.findall(
                r'(?:text|buttonText)\s*=\s*"(ADISCORD_economy_[^"]+)"',
                self.gui,
            )
        )
        visible_text = []
        for key in visible_keys:
            match = re.search(
                rf'(?m)^\s*{re.escape(key)}:\d*\s+"((?:[^"\\]|\\.)*)"\s*$',
                self.localisation,
            )
            if match:
                normalized = re.sub(
                    r'[^a-zа-яё]+', ' ', match.group(1).casefold()
                ).strip()
                visible_text.append((key, normalized))
        slogan = re.compile(
            r'(?:деньги\s+считаются\s+(?:автоматически|сами)|'
            r'money\s+is\s+calculated\s+automatically)',
            re.IGNORECASE,
        )
        offenders = {key: text for key, text in visible_text if slogan.search(text)}
        self.assertFalse(offenders, f'visible diagnostic slogans: {offenders}')

    def test_topbar_uses_icon_and_numeric_value(self):
        self.assertIn(
            (
                'iconType',
                'ADISCORD_economy_topbar_icon',
                ('ADISCORD_economy_topbar_window',),
            ),
            self.nodes,
        )
        self.assertIn(
            (
                'instantTextboxType',
                'ADISCORD_economy_topbar_value',
                ('ADISCORD_economy_topbar_window',),
            ),
            self.nodes,
        )
        self.assertNotRegex(
            self.gui,
            r'buttonText\s*=\s*"ADISCORD_economy_topbar_treasury_text"',
        )

    def test_treasury_sprite_has_a_real_temporary_asset(self):
        self.assertIn('name = "GFX_ADISCORD_treasury_icon"', self.gfx)
        self.assertIn(
            'texturefile = "gfx/interface/ADISCORD_economy_gui/treasury_icon.dds"',
            self.gfx,
        )
        self.assertTrue(
            (
                ROOT
                / 'gfx'
                / 'interface'
                / 'ADISCORD_economy_gui'
                / 'treasury_icon.dds'
            ).is_file()
        )

    def test_four_budget_rows_use_arrows_and_five_step_markers(self):
        for policy in ('tax', 'army', 'research', 'social'):
            self.assertRegex(
                self.gui,
                rf'name\s*=\s*"ADISCORD_economy_{policy}_decrease"'
                rf'[\s\S]{{0,200}}spriteType\s*=\s*"button_left"',
            )
            self.assertRegex(
                self.gui,
                rf'name\s*=\s*"ADISCORD_economy_{policy}_increase"'
                rf'[\s\S]{{0,200}}spriteType\s*=\s*"button_right"',
            )
            for level in range(1, 6):
                self.assertIn(f'ADISCORD_economy_{policy}_step_{level}', self.gui)
            self.assertIn(f'ADISCORD_economy_{policy}_active_marker', self.gui)
        self.assertNotRegex(self.gui, r'buttonText\s*=\s*"[+-]"')

    def test_active_markers_bind_to_all_five_mode_positions(self):
        for policy in ('tax', 'army', 'research', 'social'):
            self.assertIn(
                f'ADISCORD_economy_{policy}_active_marker_visible',
                self.scripted_gui,
            )
            self.assertIn(
                f'ADISCORD_economy_{policy}_active_marker_x_position',
                self.scripted_gui,
            )
            for position in (0, 24, 48, 72, 96):
                self.assertRegex(
                    self.scripted_gui,
                    rf'var\s*=\s*ADISCORD_economy_{policy}_active_marker_x_position'
                    rf'\s+value\s*=\s*{position}',
                )

    def test_each_budget_step_exposes_its_own_level_tooltip(self):
        contracts = {
            'tax': (
                'ADISCORD_economy_tax_burden_mode',
                'GetADISCORDTaxBurdenEffectsLoc',
            ),
            'army': (
                'ADISCORD_economy_army_spending_mode',
                'GetADISCORDArmySpendingEffectsLoc',
            ),
            'research': (
                'ADISCORD_economy_research_spending_mode',
                'GetADISCORDResearchSpendingEffectsLoc',
            ),
            'social': (
                'ADISCORD_economy_social_spending_mode',
                'GetADISCORDSocialSpendingEffectsLoc',
            ),
        }
        for policy, (mode_var, effect_loc) in contracts.items():
            for level in range(1, 6):
                step_name = f'ADISCORD_economy_{policy}_step_{level}'
                step_line = gui_node_body(self.gui, step_name)
                self.assertNotIn('alwaystransparent = yes', step_line)
                self.assertIn(
                    f'pdx_tooltip = "ADISCORD_economy_{policy}_level_{level}_tt"',
                    step_line,
                )
                tooltip_match = re.search(
                    rf'(?m)^\s*ADISCORD_economy_{policy}_level_{level}_tt:\d*\s+"([^"]*)"',
                    self.localisation,
                )
                self.assertIsNotNone(tooltip_match)
                self.assertIn(f'уровень {level}/5', tooltip_match.group(1))
                # HOI4 does not recursively resolve $KEY$ aliases in these
                # scripted-GUI icon tooltips. Keep the hovered level fully
                # self-contained so the player never sees a raw loc key.
                self.assertNotIn('$ADISCORD_', tooltip_match.group(1))
                self.assertIn('§W', tooltip_match.group(1))

            marker_name = f'ADISCORD_economy_{policy}_active_marker'
            marker_line = gui_node_body(self.gui, marker_name)
            self.assertNotIn('alwaystransparent = yes', marker_line)
            self.assertIn(
                f'pdx_tooltip = "ADISCORD_economy_{policy}_controls_tt"',
                marker_line,
            )

            tooltip_match = re.search(
                rf'(?m)^\s*ADISCORD_economy_{policy}_controls_tt:\d*\s+"([^"]*)"',
                self.localisation,
            )
            self.assertIsNotNone(tooltip_match)
            tooltip = tooltip_match.group(1)
            self.assertIn(f'?{mode_var}|0', tooltip)
            self.assertIn(f'[{effect_loc}]', tooltip)
            self.assertNotIn('Сравнение 1–5', tooltip)
            self.assertIn(f'name = {effect_loc}', self.scripted_loc)

    def test_increase_arrows_use_visible_absolute_positioning(self):
        for policy in ('tax', 'army', 'research', 'social'):
            increase_line = gui_node_body(
                self.gui, f'ADISCORD_economy_{policy}_increase'
            )
            self.assertIn('spriteType = "button_right"', increase_line)
            self.assertIn('position = { x = 424 ', increase_line)
            self.assertNotIn('orientation = upper_right', increase_line)

    def test_compact_dashboard_keeps_manual_borrowing_in_treasury_operations(self):
        contracts = {
            'internal_bonds': (
                'ADISCORD_economy_gui_try_issue_internal_bonds',
                'ADISCORD_economy_can_issue_internal_bonds',
            ),
            'external_loan': (
                'ADISCORD_economy_gui_try_take_external_loan',
                'ADISCORD_economy_can_take_external_loan',
            ),
        }
        for action, (effect, trigger) in contracts.items():
            node_name = f'ADISCORD_economy_action_{action}'
            self.assertIn(
                (
                    'buttonType',
                    node_name,
                    ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_operations_panel'),
                ),
                self.nodes,
            )
            self.assertIn(f'{node_name}_click = {{ {effect} = yes }}', self.scripted_gui)
            self.assertIn(
                f'{node_name}_click_enabled = {{ {trigger} = yes }}',
                self.scripted_gui,
            )
            self.assertIn(
                f'pdx_tooltip = "ADISCORD_economy_action_{action}_tt"',
                next(line for line in self.gui.splitlines() if f'name = "{node_name}"' in line),
            )

        internal_bonds_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_action_internal_bonds_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        external_loan_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_action_external_loan_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for tooltip in (internal_bonds_tt, external_loan_tt):
            self.assertIn('?ADISCORD_economy_treasury|0', tooltip)
            self.assertIn('?ADISCORD_economy_treasury_cap|0', tooltip)
            self.assertIn('?ADISCORD_economy_debt|0', tooltip)
            self.assertIn('?ADISCORD_economy_interest_rate|1', tooltip)
            self.assertIn('?ADISCORD_economy_weekly_interest|2', tooltip)
            self.assertIn('?ADISCORD_economy_interest_share_income|1', tooltip)
            self.assertIn('?ADISCORD_economy_debt_state|0', tooltip)
            self.assertNotIn('debt_capacity', tooltip)
            self.assertIn('инфляц', tooltip.lower())
        self.assertIn('?ADISCORD_economy_creditworthiness|0', external_loan_tt)
        self.assertIn('[GetADISCORDInternalBondsAvailabilityLoc]', internal_bonds_tt)
        self.assertIn('[GetADISCORDExternalLoanAvailabilityLoc]', external_loan_tt)
        for name in (
            'GetADISCORDInternalBondsAvailabilityLoc',
            'GetADISCORDExternalLoanAvailabilityLoc',
        ):
            self.assertIn(f'name = {name}', self.scripted_loc)
        for key in (
            'ADISCORD_economy_loan_blocked_interest_share_internal',
            'ADISCORD_economy_loan_blocked_interest_share_external',
            'ADISCORD_economy_loan_blocked_cooldown',
            'ADISCORD_economy_loan_blocked_treasury_room',
            'ADISCORD_economy_loan_blocked_creditworthiness',
            'ADISCORD_economy_loan_blocked_default',
            'ADISCORD_economy_loan_available_internal',
            'ADISCORD_economy_loan_available_external',
        ):
            self.assertRegex(self.localisation, rf'(?m)^\s*{key}:')

        triggers = (
            ROOT / 'common' / 'scripted_triggers' / 'ADISCORD_economy_triggers.txt'
        ).read_text(encoding='utf-8-sig')
        for trigger_name in (
            'ADISCORD_economy_can_issue_internal_bonds',
            'ADISCORD_economy_can_take_external_loan',
        ):
            match = re.search(
                rf'(?ms)^\s*{trigger_name}\s*=\s*\{{(.*?)^\}}',
                triggers,
            )
            self.assertIsNotNone(match)
            self.assertNotIn('has_tech =', match.group(1))
        self.assertNotIn('ADISCORD_economy_loan_blocked_technology', self.scripted_loc)
        self.assertNotRegex(
            self.localisation,
            r'(?m)^\s*ADISCORD_economy_loan_blocked_technology:',
        )

    def test_rare_treasury_actions_are_hidden_behind_one_explicit_second_layer(self):
        self.assertIn(
            (
                'buttonType',
                'ADISCORD_economy_operations_open',
                ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_command_panel'),
            ),
            self.nodes,
        )
        self.assertIn(
            (
                'containerWindowType',
                'ADISCORD_economy_operations_panel',
                ('ADISCORD_economy_dashboard_window',),
            ),
            self.nodes,
        )

        actions = (
            'internal_bonds',
            'external_loan',
            'repay_debt',
            'restructure_debt',
            'stabilization',
            'war_taxes',
        )
        for action in actions:
            node_name = f'ADISCORD_economy_action_{action}'
            self.assertIn(
                (
                    'buttonType',
                    node_name,
                    ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_operations_panel'),
                ),
                self.nodes,
            )
            self.assertNotIn(
                (
                    'buttonType',
                    node_name,
                    ('ADISCORD_economy_dashboard_window', 'ADISCORD_economy_command_panel'),
                ),
                self.nodes,
            )

        self.assertRegex(
            self.scripted_gui,
            r'ADISCORD_economy_operations_open_click\s*=\s*\{'
            r'[\s\S]*?ADISCORD_economy_show_operations\s+value\s*=\s*1'
            r'[\s\S]*?ADISCORD_economy_update_gui\s*=\s*yes',
        )
        self.assertRegex(
            self.scripted_gui,
            r'ADISCORD_economy_operations_close_click\s*=\s*\{'
            r'[\s\S]*?ADISCORD_economy_show_operations\s+value\s*=\s*0'
            r'[\s\S]*?ADISCORD_economy_update_gui\s*=\s*yes',
        )
        self.assertRegex(
            self.scripted_gui,
            r'ADISCORD_economy_operations_panel_visible\s*=\s*\{'
            r'[\s\S]*?ADISCORD_economy_show_operations\s+value\s*=\s*1',
        )

    def test_headline_kpis_show_cash_flow_before_secondary_risks(self):
        for node, text_key, tooltip in (
            ('ADISCORD_economy_kpi_treasury', 'ADISCORD_economy_kpi_treasury', 'ADISCORD_economy_treasury_tt'),
            ('ADISCORD_economy_kpi_income', 'ADISCORD_economy_kpi_income', 'ADISCORD_economy_income_tt'),
            ('ADISCORD_economy_kpi_expenses', 'ADISCORD_economy_kpi_expenses', 'ADISCORD_economy_expenses_tt'),
            ('ADISCORD_economy_kpi_balance', 'ADISCORD_economy_kpi_balance', 'ADISCORD_economy_budget_breakdown_tt'),
        ):
            line = next(
                line for line in self.gui.splitlines() if f'name = "{node}"' in line
            )
            self.assertIn(f'text = "{text_key}"', line)
            self.assertIn(f'pdx_tooltip = "{tooltip}"', line)

        self.assertNotIn('name = "ADISCORD_economy_kpi_debt"', self.gui)
        self.assertNotIn('name = "ADISCORD_economy_kpi_risk"', self.gui)

    def test_secondary_risks_have_visible_rows_and_dedicated_explanations(self):
        for node, text_key, tooltip in (
            ('ADISCORD_economy_risk_debt', 'ADISCORD_economy_risk_debt', 'ADISCORD_economy_debt_tt'),
            ('ADISCORD_economy_risk_inflation', 'ADISCORD_economy_risk_inflation', 'ADISCORD_economy_inflation_tt'),
            ('ADISCORD_economy_risk_overload', 'ADISCORD_economy_risk_overload', 'ADISCORD_economy_stretched_tt'),
            ('ADISCORD_economy_risk_war_fatigue', 'ADISCORD_economy_risk_war_fatigue', 'ADISCORD_economy_war_fatigue_tt'),
        ):
            line = next(
                line for line in self.gui.splitlines() if f'name = "{node}"' in line
            )
            self.assertIn(f'text = "{text_key}"', line)
            self.assertIn(f'pdx_tooltip = "{tooltip}"', line)

        summary_line = next(
            line
            for line in self.gui.splitlines()
            if 'name = "ADISCORD_economy_player_summary"' in line
        )
        self.assertIn('pdx_tooltip = "ADISCORD_economy_summary_tt"', summary_line)

        debt_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_debt_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_debt|0',
            '?ADISCORD_economy_interest_rate|1',
            '?ADISCORD_economy_weekly_interest|2',
            '?ADISCORD_economy_interest_share_income|1',
            '?ADISCORD_economy_debt_state|0',
            '[GetADISCORDDebtEffectsLoc]',
            '10/25/40%',
            '4/13',
        ):
            self.assertIn(required, debt_tt)
        self.assertNotIn('debt_capacity', debt_tt)

        inflation_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_inflation_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_inflation|1',
            '?ADISCORD_economy_inflation_delta_temp|=+2',
            '[GetADISCORDInflationEffectsLoc]',
            '10/25/50/75%',
        ):
            self.assertIn(required, inflation_tt)

        inflation_delayed_tt = localisation_value(
            self.localisation, 'ADISCORD_economy_inflation_delayed_tt'
        )
        for required in (
            'ADISCORD_economy_emission_pressure',
            'ADISCORD_economy_deficit_pressure',
            'ADISCORD_economy_price_shock',
        ):
            self.assertIn(required, inflation_delayed_tt)

        self.assertIn('name = GetADISCORDDebtEffectsLoc', self.scripted_loc)
        self.assertIn('name = GetADISCORDInflationEffectsLoc', self.scripted_loc)

        overload_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_stretched_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_stretched_score|0',
            '?ADISCORD_economy_debt_pressure|0',
            '?ADISCORD_economy_demographic_fatigue_score|0',
            '?ADISCORD_economy_workforce_drain_level|0',
            '?ADISCORD_economy_fiscal_stress|0',
            '[GetADISCORDStateLoadEffectsLoc]',
            '20/40/60/80',
        ):
            self.assertIn(required, overload_tt)

        fatigue_tt = re.search(
            r'(?m)^\s*ADISCORD_economy_war_fatigue_tt:\d*\s+"([^"]*)"',
            self.localisation,
        ).group(1)
        for required in (
            '?ADISCORD_economy_war_fatigue_score|0',
            '?ADISCORD_economy_monthly_casualties_delta_k|0',
            '[GetADISCORDWarFatigueEffectsLoc]',
            '[GetADISCORDDemobilizationStatusLoc]',
            '15/30/50/75',
        ):
            self.assertIn(required, fatigue_tt)
        self.assertIn('name = GetADISCORDStateLoadEffectsLoc', self.scripted_loc)
        self.assertIn('name = GetADISCORDWarFatigueEffectsLoc', self.scripted_loc)
        self.assertIn('name = GetADISCORDDemobilizationStatusLoc', self.scripted_loc)

    def test_left_panel_text_zones_do_not_overlap(self):
        self.assertNotIn('ADISCORD_economy_automation_note', self.gui)
        for name, y, height in (
            ('ADISCORD_economy_player_summary', 14, 86),
            ('ADISCORD_economy_player_advice', 108, 94),
            ('ADISCORD_economy_risk_title', 214, 22),
            ('ADISCORD_economy_risk_debt', 242, 24),
            ('ADISCORD_economy_risk_inflation', 270, 24),
            ('ADISCORD_economy_risk_overload', 298, 24),
            ('ADISCORD_economy_risk_war_fatigue', 326, 24),
            ('ADISCORD_economy_buildings_summary', 378, 24),
        ):
            self.assertRegex(
                self.gui,
                rf'name\s*=\s*"{name}"'
                rf'[\s\S]{{0,160}}position\s*=\s*\{{\s*x\s*=\s*14\s+y\s*=\s*{y}\s*\}}'
                rf'[\s\S]{{0,160}}maxHeight\s*=\s*{height}',
            )

    def test_removed_tab_layout_localisation_does_not_return(self):
        for dead_key in (
            'ADISCORD_economy_tab_overview',
            'ADISCORD_economy_tab_budget',
            'ADISCORD_economy_tab_operations',
            'ADISCORD_economy_dashboard_accounting_block',
            'ADISCORD_economy_dashboard_budget_block',
            'ADISCORD_economy_dashboard_income_block',
            'ADISCORD_economy_dashboard_expenses_block',
            'ADISCORD_economy_debt_operations_title',
            'ADISCORD_economy_monetary_operations_title',
            'ADISCORD_economy_investment_operations_title',
            'ADISCORD_economy_dashboard_buildings_block',
            'ADISCORD_economy_last_month_accounting_tt',
            'ADISCORD_economy_tax_burden_tt',
            'ADISCORD_economy_army_spending_tt',
            'ADISCORD_economy_construction_spending_tt',
            'ADISCORD_economy_emergency_title',
            'ADISCORD_economy_emergency_hint',
        ):
            self.assertNotRegex(self.localisation, rf'(?m)^\s*{dead_key}:')

    def test_treasury_guidance_uses_cyrillic_capable_fonts(self):
        for hint_name in (
            'ADISCORD_economy_main_help',
            'ADISCORD_economy_operations_main_hint',
            'ADISCORD_economy_operations_hint',
        ):
            hint_line = next(
                line
                for line in self.gui.splitlines()
                if f'name = "{hint_name}"' in line
            )
            self.assertIn('font = "hoi_16mbs"', hint_line)
            self.assertNotIn('font = "hoi_14mbs"', hint_line)

    def test_treasury_operations_hint_is_actionable_and_read_only(self):
        self.assertRegex(
            self.localisation,
            r'(?m)^\s*ADISCORD_economy_operations_main_hint:\d*\s+"\[GetADISCORDTreasuryOperationsHintLoc\]"',
        )
        self.assertIn('name = GetADISCORDTreasuryOperationsHintLoc', self.scripted_loc)
        for key in (
            'ADISCORD_economy_operations_hint_deficit',
            'ADISCORD_economy_operations_hint_debt',
            'ADISCORD_economy_operations_hint_inflation',
            'ADISCORD_economy_operations_hint_reserve',
            'ADISCORD_economy_operations_hint_safe',
        ):
            self.assertRegex(self.localisation, rf'(?m)^\s*{key}:')
            self.assertIn(f'localization_key = {key}', self.scripted_loc)
        self.assertIn('ADISCORD_economy_safe_reserve', self.scripted_loc)
        for forbidden in ('every_country', 'every_owned_state', 'all_owned_state'):
            self.assertNotIn(forbidden, self.scripted_loc)


class RuntimePulseTests(unittest.TestCase):
    def test_economy_weekly_pulse_uses_the_light_settlement(self):
        text = (ROOT / 'common' / 'on_actions' / '00_ADISCORD_on_actions.txt').read_text(
            encoding='utf-8-sig'
        )

        self.assertRegex(
            text,
            r'(?s)\bon_weekly\s*=\s*\{.*?ADISCORD_economy_should_weekly_update\s*=\s*yes'
            r'.*?ADISCORD_economy_weekly_update\s*=\s*yes',
        )
        self.assertNotRegex(
            text,
            r'(?s)\bon_weekly\s*=\s*\{.*?ADISCORD_economy_weekly_player_refresh\s*=\s*yes',
        )


if __name__ == '__main__':
    unittest.main()

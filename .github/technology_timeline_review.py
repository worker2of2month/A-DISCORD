from pathlib import Path
import re

SYSTEM = Path('tools/builders/build_adiscord_technology_system.py')
UI = Path('tools/builders/build_adiscord_technology_ui_assets.py')
TESTS = Path('tools/tests/test_build_adiscord_technology_system.py')
UI_TESTS = Path('tools/tests/test_adiscord_technology_ui.py')
VALIDATOR = Path('tools/validators/validate_adiscord_tech_doctrine.py')


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


def add_tests():
    text = TESTS.read_text()
    addition = r'''
    @staticmethod
    def _named_gui_block(text: str, kind: str, name: str) -> str:
        for match in re.finditer(rf"\b{kind}\s*=\s*\{{", text):
            block = validator.extract_block(text, match.start())
            if re.search(rf'\bname\s*=\s*"{re.escape(name)}"', block):
                return block
        raise AssertionError(f"Missing {kind}: {name}")

    def test_native_grid_cross_axis_is_centered_beneath_each_branch_title(self) -> None:
        for folder in generator.FOLDER_BACKGROUNDS:
            rendered = generator.render_folder(folder)
            horizontal = folder in generator.HORIZONTAL_FOLDERS
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = self._named_gui_block(rendered, "gridboxtype", branch.techs[0].id + "_tree")
                size = re.search(r"size = \{ width = (\d+) height = (\d+) \}", grid)
                cross_size = int(size[2 if horizontal else 1])
                # Native cross-axis slot zero lies at the gridbox centre.
                centers = [
                    cross_size / 2 + generator.technology_grid_position(branch, i)[0] * 70
                    for i in range(len(branch.techs))
                ]
                half_card = 42 if horizontal else 102
                with self.subTest(folder=folder, branch=branch.key):
                    self.assertEqual((min(centers) + max(centers)) / 2, cross_size / 2)
                    self.assertGreaterEqual(min(centers) - half_card, 0)
                    self.assertLessEqual(max(centers) + half_card, cross_size)

    def test_horizontal_ruler_dates_match_every_technology_start_year(self) -> None:
        for branch in generator.BRANCHES:
            if not generator.HORIZONTAL_FOLDERS.intersection(branch.folders):
                continue
            for index, tech in enumerate(branch.techs):
                text = generator.render_technology(branch, index)
                year = int(re.search(r"\bstart_year = (\d+)", text)[1])
                with self.subTest(technology=tech.id):
                    self.assertEqual(
                        generator.technology_time_slot(branch, index),
                        generator.YEAR_TO_Y[year] * 3,
                    )

    def test_year_label_centres_align_with_native_technology_cells(self) -> None:
        for folder in generator.FOLDER_BACKGROUNDS:
            rendered = generator.render_folder(folder)
            horizontal = folder in generator.HORIZONTAL_FOLDERS
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = self._named_gui_block(rendered, "gridboxtype", branch.techs[0].id + "_tree")
                origin = re.search(r"position = \{ x = (-?\d+) y = (-?\d+) \}", grid)
                for index, year in enumerate(branch.years):
                    label_id = str(year) if horizontal else f"{branch.key}_{year}"
                    label = self._named_gui_block(
                        rendered, "instantTextBoxType", f"ADISCORD_{folder}_year_{label_id}"
                    )
                    pos = re.search(r"position = \{ x = (-?\d+) y = (-?\d+) \}", label)
                    extent = int(re.search(
                        r"maxWidth = (\d+)" if horizontal else r"maxHeight = (\d+)", label
                    )[1])
                    axis = 1 if horizontal else 2
                    cell_center = int(origin[axis]) + generator.technology_time_slot(branch, index) * 70 + 35
                    with self.subTest(folder=folder, technology=branch.techs[index].id):
                        self.assertEqual(int(pos[axis]) + extent / 2, cell_center)
                        self.assertIn(f'text = "{year}"', label)

    def test_ui_validator_rejects_swapped_dates_displaced_labels_and_wrong_titles(self) -> None:
        original = "\n".join(generator.render_folder(folder) for folder in generator.FOLDER_BACKGROUNDS)
        label_a = self._named_gui_block(original, "instantTextBoxType", "ADISCORD_industry_folder_year_production_2150")
        label_b = self._named_gui_block(original, "instantTextBoxType", "ADISCORD_industry_folder_year_production_2155")
        swapped = original.replace(label_a, label_a.replace('text = "2150"', 'text = "2155"'))
        swapped = swapped.replace(label_b, label_b.replace('text = "2155"', 'text = "2150"'))
        displaced = original.replace(label_a, re.sub(r"position = \{ x = -?\d+", "position = { x = 999", label_a))
        title = self._named_gui_block(original, "instantTextBoxType", "ADISCORD_branch_production")
        wrong_title = original.replace(title, title.replace("ADISCORD_TECH_BRANCH_PRODUCTION", "ADISCORD_TECH_BRANCH_RECONSTRUCTION"))
        grid = self._named_gui_block(original, "gridboxtype", "ADISCORD_tech_standardized_machine_tools_tree")
        displaced_grid = original.replace(grid, re.sub(r"position = \{ x = -?\d+", "position = { x = 999", grid))
        mutations = (
            ("swapped", swapped), ("displaced", displaced), ("wrong_title", wrong_title),
            ("displaced_grid", displaced_grid),
            ("missing", original.replace(label_a, "")),
            ("duplicate", original.replace(label_a, label_a + label_a)),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "interface/countrytechtreeview.gui"
            path.parent.mkdir()
            path.write_text(original, encoding="utf-8")
            with patch.object(validator, "ROOT", root):
                self.assertEqual(validator.check_technology_ui_years(), [])
                for name, broken in mutations:
                    with self.subTest(mutation=name):
                        path.write_text(broken, encoding="utf-8")
                        self.assertTrue(validator.check_technology_ui_years())

    def test_gui_regeneration_from_repository_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "interface/countrytechtreeview.gui"
            output.parent.mkdir()
            output.write_bytes((ROOT / "interface/countrytechtreeview.gui").read_bytes())
            with patch.object(generator, "ROOT", root), patch.object(
                generator, "BASE_GAME", root / "uninstalled_game"
            ):
                generator.write_gui()
                first = output.read_bytes()
                generator.write_gui()
                self.assertEqual(output.read_bytes(), first)
            with patch.object(validator, "ROOT", root):
                self.assertEqual(validator.check_technology_ui_years(), [])

'''
    text = replace_once(text, 'class CompactTechnologyTreeContractTests(unittest.TestCase):\n',
                        'class CompactTechnologyTreeContractTests(unittest.TestCase):\n' + addition)
    TESTS.write_text(text)
    text = UI_TESTS.read_text()
    addition = r'''
    def test_tree_skin_is_idempotent_for_generated_and_mixed_input(self) -> None:
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(encoding="utf-8")
        self.assertEqual(builder.apply_tree_skin(gui), gui)
        old, (new, _) = next(iter(builder.TREE_SPRITE_REPLACEMENTS.items()))
        mixed = gui.replace(f'"{new}"', f'"{old}"', 1)
        self.assertEqual(builder.apply_tree_skin(mixed), gui)

    def test_tree_skin_still_rejects_missing_or_duplicate_widgets(self) -> None:
        gui = (ROOT / "interface/countrytechtreeview.gui").read_text(encoding="utf-8")
        sprite = builder.FOLDER_TAB_CONTRACTS[0].target_name
        for broken in (
            gui.replace(f'"{sprite}"', '"missing_sprite"', 1),
            gui + f'\nquadTextureSprite = "{sprite}"\n',
        ):
            with self.subTest(occurrences=broken.count(f'"{sprite}"')):
                with self.assertRaises(ValueError):
                    builder.apply_tree_skin(broken)

'''
    text = replace_once(text, '    def test_tree_skin_uses_tree_and_detail_roles(',
                        addition + '    def test_tree_skin_uses_tree_and_detail_roles(')
    UI_TESTS.write_text(text)


def apply_fix():
    text = SYSTEM.read_text()
    text = replace_once(text, 'GRID_SLOT = 70\n', 'GRID_SLOT = 70\nYEAR_LABEL_WIDTH = 56\nYEAR_LABEL_HEIGHT = 22\n')
    start = text.index('def graph_distances(')
    end = text.index('\ndef technology_time_slot(', start)
    replacement = '''def horizontal_visual_slots(branch: Branch) -> tuple[int, ...]:
    """Keep every node under its actual research year, including fork arms."""

    slots = tuple(
        chronological_grid_slot(year, horizontal=True)
        for year in branch.years
    )
    for source, targets in enumerate(BRANCH_GRAPHS[branch.key].successors):
        for target in targets:
            if slots[source] >= slots[target]:
                raise ValueError(
                    f"{branch.key}: non-chronological visual edge {source}->{target}"
                )
    return slots

'''
    text = text[:start] + replacement + text[end:]
    start = text.index('def technology_grid_position(')
    end = text.index('\ndef render_research_completion_effects(', start)
    replacement = '''def technology_grid_position(branch: Branch, index: int) -> tuple[int, int]:
    """Return signed cross-axis slots and chronological time slots.

    Native technology grids centre cross-axis slot zero inside the gridbox.
    ``UP`` spends position.x across and position.y down; ``LEFT`` swaps those
    screen axes. Both therefore need signed lane offsets around the midpoint
    of the occupied lanes, not offsets measured from the box's upper-left.
    """

    graph = BRANCH_GRAPHS[branch.key]
    multiplier = (
        HORIZONTAL_LANE_SLOT_MULTIPLIER
        if HORIZONTAL_FOLDERS.intersection(branch.folders)
        else LANE_SLOT_MULTIPLIER
    )
    doubled_slot = (
        2 * graph.lanes[index] - min(graph.lanes) - max(graph.lanes)
    ) * multiplier
    if doubled_slot % 2:
        raise ValueError(f"{branch.key}: lane spacing cannot centre integer grid slots")
    return doubled_slot // 2, technology_time_slot(branch, index)

'''
    text = text[:start] + replacement + text[end:]
    text = replace_once(text, '(max(graph.lanes) + 1) * HORIZONTAL_LANE_SLOT_MULTIPLIER * GRID_SLOT',
                        '(max(graph.lanes) - min(graph.lanes) + 1)\n                * HORIZONTAL_LANE_SLOT_MULTIPLIER * GRID_SLOT')
    start = text.index('    year_labels = (', text.index('def render_folder('))
    end = text.index('    for label, year, year_x, year_y in year_labels:', start)
    replacement = '''    if horizontal:
        year_labels = [
            (
                str(year), year,
                GRID_X + chronological_grid_slot(year, horizontal=True) * GRID_SLOT
                + (GRID_SLOT - YEAR_LABEL_WIDTH) // 2,
                84,
            )
            for year in YEARS
        ]
    else:
        year_labels = [
            (
                f"{branch.key}_{year}", year, grid_x - 62,
                grid_y + technology_time_slot(branch, branch.years.index(year)) * GRID_SLOT
                + (GRID_SLOT - YEAR_LABEL_HEIGHT) // 2,
            )
            for branch, grid_x, grid_y, _, _ in branch_layouts
            for year in sorted(set(branch.years))
        ]
'''
    text = text[:start] + replacement + text[end:]
    text = replace_once(text, r'"\t\t\t\t\tmaxWidth = 56"', r'f"\t\t\t\t\tmaxWidth = {YEAR_LABEL_WIDTH}"')
    text = replace_once(text, r'"\t\t\t\t\tmaxHeight = 22"', r'f"\t\t\t\t\tmaxHeight = {YEAR_LABEL_HEIGHT}"')
    text = replace_once(text, r'"\t\t\t\t\tformat = left"', '''f"\\t\\t\\t\\t\\tformat = {'center' if horizontal else 'left'}"''')
    text = replace_once(text,
        '            replacements.append((start, end, render_folder(name)))',
        '''            # Replace indentation with the generated block instead of adding
            # another prefix on every repository-GUI regeneration.
            line_start = text.rfind("\\n", 0, start) + 1
            if text[line_start:start].strip():
                raise ValueError(f"Technology folder {name} must begin on its own line")
            replacements.append((line_start, end, render_folder(name)))''')
    SYSTEM.write_text(text)

    text = UI.read_text()
    text = replace_once(text,
        'def apply_tree_skin(text: str) -> str:\n    for contract, (_, _, count) in zip(FOLDER_TAB_CONTRACTS, FOLDER_TABS):\n',
        '''def apply_tree_skin(text: str) -> str:
    # The system builder can start from the already skinned repository GUI.
    # Normalise each token before the strict count check so mixed regenerated
    # folders remain valid without accepting missing or duplicate widgets.
    for contract, (_, _, count) in zip(FOLDER_TAB_CONTRACTS, FOLDER_TABS):
        text = text.replace(f'"{contract.target_name}"', f'"{contract.source_name}"')
''')
    text = replace_once(text,
        r'''        r'#SpriteType\s*=\s*"GFX_technology_info_bg"'
        r'(?P<gap>\s*)'
        r'SpriteType\s*=\s*"GFX_tiled_window_thin_border2"' '' '.rstrip(),
        r'''        r'(?:#SpriteType\s*=\s*"GFX_technology_info_bg"'
        r'|SpriteType\s*=\s*"GFX_ADISCORD_technology_info")'
        r'(?P<gap>\s*)'
        r'#?SpriteType\s*=\s*"GFX_tiled_window_thin_border2"' '' '.rstrip())
    text = replace_once(text,
        '    for old, (new, expected) in TREE_SPRITE_REPLACEMENTS.items():\n',
        '''    for old, (new, expected) in TREE_SPRITE_REPLACEMENTS.items():
        text = text.replace(f'"{new}"', f'"{old}"')
''')
    text = replace_once(text,
        '''(r'font\\s*=\\s*"hoi4_typewriter16_inverted"', 'font = "hoi4_typewriter16"'),''',
        '''(r'font\\s*=\\s*"hoi4_typewriter16(?:_inverted)?"', 'font = "hoi4_typewriter16"'),''')
    UI.write_text(text)

    text = VALIDATOR.read_text()
    old = '        technology_grid_position as generated_technology_grid_position,'
    assert text.count(old) == 2
    text = text.replace(old, old + '\n        render_folder as render_generated_technology_folder,')
    helper = r'''def technology_layout_elements(text: str) -> dict[str, list[tuple[str, ...]]]:
    """Collect generated labels, headings and grids without whitespace sensitivity."""

    elements: dict[str, list[tuple[str, ...]]] = {}
    for match in re.finditer(r"\b(?:instantTextBoxType|gridboxtype)\s*=\s*\{", text):
        block = extract_block(text, match.start())
        name_match = re.search(r'\bname\s*=\s*"(ADISCORD_[^"]+)"', block)
        if name_match is None:
            continue
        name = name_match.group(1)
        tokens = tuple(re.findall(r'"[^"]*"|[{}=]|[^\s{}=]+', block))
        elements.setdefault(name, []).append(tokens)
    return elements


'''
    text = replace_once(text, 'def check_technology_ui_years()', helper + 'def check_technology_ui_years()')
    addition = '''        expected_elements = technology_layout_elements(render_generated_technology_folder(folder))
        actual_elements = technology_layout_elements(folder_block)
        for name in sorted(expected_elements.keys() | actual_elements.keys()):
            if name not in expected_elements:
                issues.append(f"{folder} has unexpected generated layout element {name}")
            elif name not in actual_elements:
                issues.append(f"{folder} is missing generated layout element {name}")
            elif len(actual_elements[name]) != 1:
                issues.append(f"{folder} has duplicate generated layout element {name}")
            elif actual_elements[name] != expected_elements[name]:
                issues.append(f"{folder}: {name} does not match its generated text or geometry")
'''
    text = replace_once(text, '        for year in sorted(EXPECTED_TECH_UI_YEARS):\n',
                        addition + '        for year in sorted(EXPECTED_TECH_UI_YEARS):\n')
    VALIDATOR.write_text(text)

    text = TESTS.read_text()
    text = replace_once(text,
        r'r"position\s*=\s*\{\s*x\s*=\s*(\d+)\s*y\s*=\s*(\d+)"',
        r'r"position\s*=\s*\{\s*x\s*=\s*(-?\d+)\s*y\s*=\s*(-?\d+)"')
    text = replace_once(text, '0: (2, 0),\n                3: (4, 15),\n                15: (2, 57),',
                        '0: (0, 0),\n                3: (2, 9),\n                15: (0, 57),')
    text = replace_once(text,
        'self.assertEqual(x, 2 * generator.BRANCH_GRAPHS["small_arms"].lanes[index])',
        'self.assertEqual(x, 2 * (generator.BRANCH_GRAPHS["small_arms"].lanes[index] - 1))')
    text = replace_once(text, 'def test_horizontal_programmes_share_visual_fork_and_merge_columns(self)',
                        'def test_horizontal_programmes_retain_authored_fork_and_merge_years(self)')
    for group in ('fork_targets', 'merge_parents'):
        text = replace_once(text,
            '{generator.technology_time_slot(branch, ' + group + '[0])},',
            '{generator.YEAR_TO_Y[branch.years[index]] * 3 for index in ' + group + '},')
    start = text.index('    def test_every_node_fits_inside_its_own_declared_gridbox(')
    end = text.index('    def test_consecutive_rungs_leave_room_for_their_connector(', start)
    replacement = r'''    def test_every_node_fits_inside_its_own_declared_gridbox(self) -> None:
        for folder in generator.FOLDER_BACKGROUNDS:
            rendered = generator.render_folder(folder)
            horizontal = folder in generator.HORIZONTAL_FOLDERS
            for branch in (b for b in generator.BRANCHES if folder in b.folders):
                grid = self._named_gui_block(
                    rendered, "gridboxtype", branch.techs[0].id + "_tree"
                )
                size = re.search(r"size = \{ width = (\d+) height = (\d+) \}", grid)
                width, height = int(size[1]), int(size[2])
                for index, tech in enumerate(branch.techs):
                    x, y = generator.technology_grid_position(branch, index)
                    if horizontal:
                        across, down = y * 70 + 35, height / 2 + x * 70
                    else:
                        across, down = width / 2 + x * 70, y * 70 + 35
                    with self.subTest(folder=folder, technology=tech.id):
                        self.assertGreaterEqual(across, 0)
                        self.assertLessEqual(across, width)
                        self.assertGreaterEqual(down, 0)
                        self.assertLessEqual(down, height)

'''
    text = text[:start] + replacement + text[end:]
    text = replace_once(text, 'label_rows[("advanced_materials", 2155)], 148)',
                        'label_rows[("advanced_materials", 2155)], 154)')
    text = replace_once(text, 'label_rows[("advanced_materials", 2173)], 568)',
                        'label_rows[("advanced_materials", 2173)], 574)')
    text = replace_once(text, 'label_rows[(branch.key, branch.years[index])], node_top + 18)',
                        'label_rows[(branch.key, branch.years[index])], node_top + 24)')
    TESTS.write_text(text)

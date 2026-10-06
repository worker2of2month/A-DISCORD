from pathlib import Path
import re

root = Path.cwd()
path = root / "tools/validators/validate_adiscord_tech_doctrine.py"
text = path.read_text(encoding="utf-8")
text = text.replace(
    "        technology_grid_position as generated_technology_grid_position,",
    "        technology_grid_position as generated_technology_grid_position,\n"
    "        technology_tree_root as generated_technology_tree_root,\n"
    "        technology_successors as generated_technology_successors,",
)
text = text.replace('f"{branch.techs[0].id}_tree"', 'f"{generated_technology_tree_root(branch)}_tree"')
text = text.replace(
    "        for targets in graph.successors:\n"
    "            for target in targets:\n"
    "                child = branch.techs[target].id\n",
    "        for index in range(len(branch.techs)):\n"
    "            for child in generated_technology_successors(branch, index):\n",
)
text = text.replace(
    "            expected_leads = {\n"
    "                branch.techs[target].id for target in graph.successors[index]\n"
    "            }",
    "            expected_leads = set(generated_technology_successors(branch, index))",
)
path.write_text(text, encoding="utf-8")

path = root / "tools/tests/test_build_adiscord_technology_system.py"
text = path.read_text(encoding="utf-8")
text = text.replace('branch.techs[0].id + "_tree"', 'generator.technology_tree_root(branch) + "_tree"')
text = text.replace('rf\'name = "{branch.techs[0].id}_tree".*?\'', 'rf\'name = "{generator.technology_tree_root(branch)}_tree".*?\'')
path.write_text(text, encoding="utf-8")

path = root / "common/units/equipment/ADISCORD_infantry_equipment.txt"
original = path.read_bytes()
(root / "work/rifle-production-gap/equipment-before.txt").write_bytes(original)
text = original.decode("utf-8")
newline = "\r\n" if "\r\n" in text else "\n"
updates = {
    2168: ("0.063", {"steel": 2, "aluminium": 1}),
    2170: ("0.073", {"steel": 3, "aluminium": 1}),
    2178: ("0.086", {"steel": 3, "aluminium": 2}),
    2183: ("0.104", {"steel": 3, "aluminium": 2, "rare_components": 1}),
    2193: ("0.132", {"steel": 3, "aluminium": 2, "tungsten": 1, "rare_components": 1, "rare_alloys": 1}),
    2200: ("0.168", {"steel": 4, "aluminium": 2, "tungsten": 1, "rare_components": 2, "rare_alloys": 2}),
}
for year, (cost, resources) in updates.items():
    pattern = rf"(\tADISCORD_infantry_equipment_{year} = \{{.*?\n\t\}})"
    match = re.search(pattern, text, re.DOTALL)
    assert match, year
    block = match[1]
    replacement = re.sub(r"build_cost_ic = [\d.]+", f"build_cost_ic = {cost}", block)
    resource_lines = ["resources = {"]
    resource_lines.extend(f"\t\t\t{name} = {amount}" for name, amount in resources.items())
    resource_lines.append("\t\t}")
    replacement = re.sub(r"resources = \{[^}]+\}", lambda _: newline.join(resource_lines), replacement)
    text = text[:match.start()] + replacement + text[match.end():]
path.write_bytes(text.encode("utf-8"))

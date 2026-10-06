from pathlib import Path
import re
import json

root = Path.cwd()
updates = {}


def add(name, cost=None, **resources):
    assert name not in updates
    updates[name] = (cost, resources)


for suffix, cost, resources in (
    (2156, 1.30, dict(steel=3)),
    (2163, 1.40, dict(steel=3, aluminium=1)),
    (2168, 1.55, dict(steel=3, aluminium=1, tungsten=1)),
    (2170, 1.70, dict(steel=4, aluminium=1, tungsten=1)),
    (2178, 1.90, dict(steel=4, aluminium=2, tungsten=1)),
    (2183, 2.15, dict(steel=4, aluminium=2, tungsten=1, rare_components=1)),
    (2193, 2.45, dict(steel=4, aluminium=2, tungsten=1, rare_components=1, rare_alloys=1)),
    (2200, 2.80, dict(steel=4, aluminium=2, tungsten=1, rare_components=2, rare_alloys=2)),
):
    add(f"ADISCORD_squad_weapons_equipment_{suffix}", cost, **resources)

add("ADISCORD_support_equipment_2170", 5)
add("ADISCORD_support_equipment_2183", 6, aluminium=2, steel=2, tungsten=1, rare_components=1)
add("ADISCORD_support_equipment_2200", 7, aluminium=3, steel=2, tungsten=1, rare_components=2, rare_alloys=1)
add("ADISCORD_artillery_equipment_2170", 4.4)
add("ADISCORD_artillery_equipment_2183", 5.5, tungsten=2, steel=3, aluminium=1, rare_alloys=1, rare_components=1)
add("ADISCORD_anti_tank_equipment_2183", 6, tungsten=2, steel=3, chromium=1, rare_components=1, rare_alloys=1)
add("ADISCORD_anti_air_equipment_2183", 6, steel=3, aluminium=1, rare_components=1, rare_alloys=1)
add("ADISCORD_railway_gun_equipment_2200", 1050, steel=5, tungsten=3, chromium=2, aluminium=1, rare_components=1, rare_alloys=1)
add("ADISCORD_hardened_train_equipment_2183", 140)
add("ADISCORD_combat_platform_2183", 17)
add("ADISCORD_combat_platform_2200", 21, steel=4, tungsten=2, chromium=1, aluminium=1, rare_alloys=2, rare_components=2)
add("ADISCORD_heavy_combat_platform_2200", 30, steel=6, tungsten=3, chromium=2, aluminium=1, rare_alloys=2, rare_components=1)
add("ADISCORD_networked_ifv_2183", 14, steel=3, aluminium=2, tungsten=1, rare_components=1, rare_alloys=1)

add("ADISCORD_fighter_airframe_2161", aluminium=4, rubber=1)
add("ADISCORD_fighter_airframe_2166", 24, aluminium=4, rubber=2)
add("ADISCORD_interceptor_airframe_2183", 27, aluminium=4, rubber=2, tungsten=1, rare_components=1, rare_alloys=1)
add("ADISCORD_fighter_airframe_2170", 32, aluminium=5, rubber=2, tungsten=1, rare_components=1, rare_alloys=1)
add("ADISCORD_fighter_airframe_2175", 38, aluminium=5, rubber=2, tungsten=1, rare_components=2, rare_alloys=2)
add("ADISCORD_attack_airframe_2170", 29)
add("ADISCORD_attack_airframe_2175", 36, aluminium=5, rubber=1, rare_components=2, rare_alloys=1)
for family in ("bomber", "naval_aircraft"):
    add(f"ADISCORD_{family}_2164", aluminium=5, rubber=1)
    add(f"ADISCORD_{family}_2172", 50, aluminium=5, rubber=2, rare_components=1, rare_alloys=1)
for family in ("cv_fighter", "cv_bomber"):
    add(f"ADISCORD_{family}_2163", aluminium=4, rubber=1)
    add(f"ADISCORD_{family}_2170", 35, aluminium=4, rubber=1, rare_components=1)
    add(f"ADISCORD_{family}_2175", 43, aluminium=4, rubber=1, rare_components=2, rare_alloys=1)

add("ADISCORD_escort_ship_2163", steel=3, chromium=1)
add("ADISCORD_escort_ship_2175", steel=3, chromium=1, rare_components=2, rare_alloys=1)
add("ADISCORD_submarine_2163", steel=3)
add("ADISCORD_submarine_2170", steel=3, chromium=1, rare_components=1)
add("ADISCORD_submarine_2175", steel=3, chromium=1, rare_components=2, rare_alloys=1)
for family, steel, chromium in (
    ("light_cruiser", 4, 1),
    ("cruiser", 5, 2),
    ("battleship", 7, 3),
    ("carrier", 6, 2),
):
    add(f"ADISCORD_{family}_2163", steel=steel, chromium=chromium)
    add(f"ADISCORD_{family}_2170", steel=steel, chromium=chromium, rare_alloys=1, rare_components=1)
    add(f"ADISCORD_{family}_2175", steel=steel + 1, chromium=chromium, rare_alloys=2, rare_components=2)

changed = {}
for path in sorted((root / "common/units/equipment").glob("*.txt")):
    original = path.read_bytes()
    text = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    replacements = []
    for name, (cost, resources) in updates.items():
        match = re.search(rf"\t{name} = \{{.*?\n\t\}}", text, re.DOTALL)
        if match is None:
            continue
        block = match[0]
        if cost is not None:
            block, count = re.subn(r"\bbuild_cost_ic = [\d.]+", f"build_cost_ic = {cost:g}", block)
            assert count == 1, name
        if resources:
            lines = ["resources = {"]
            lines.extend(f"\t\t\t{key} = {value}" for key, value in resources.items())
            lines.append("\t\t}")
            block, count = re.subn(r"\bresources = \{[^}]+\}", lambda _: newline.join(lines), block)
            assert count == 1, name
        replacements.append((match.start(), match.end(), block))
        changed[name] = {"cost": cost, "resources": resources}
    for start, end, block in reversed(sorted(replacements)):
        text = text[:start] + block + text[end:]
    if text.encode("utf-8") != original:
        backup = root / "work/equipment-progression/before" / path.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        assert not backup.exists()
        backup.write_bytes(original)
        path.write_bytes(text.encode("utf-8"))
        print(path.name, len(replacements))
assert changed.keys() == updates.keys(), updates.keys() - changed.keys()
(root / "work/equipment-progression/changes.json").write_text(json.dumps(changed, indent=2), encoding="utf-8")
print(f"Reviewed {len(changed)} model cost/material updates.")

from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]

pos = {}
with (root / "map" / "unitstacks.txt").open(encoding="utf-8-sig") as handle:
    for line in handle:
        fields = line.strip().split(";")
        if len(fields) < 5 or not fields[0].isdigit() or fields[1] != "0":
            continue
        pid = int(fields[0])
        pos.setdefault(pid, (float(fields[2]), float(fields[4])))

states = {}
for path in (root / "history" / "states").glob("*.txt"):
    text = path.read_text(encoding="utf-8")
    match_id = re.search(r"id\s*=\s*(\d+)", text)
    if not match_id:
        continue
    sid = int(match_id.group(1))
    match_prov = re.search(r"provinces\s*=\s*\{([^}]+)\}", text)
    if not match_prov:
        continue
    provs = [int(token) for token in re.findall(r"\d+", match_prov.group(1))]
    owner = re.search(r"owner\s*=\s*(\w+)", text)
    states[sid] = {
        "provs": provs,
        "owner": owner.group(1) if owner else "?",
    }

names = {}
loc = (root / "localisation" / "russian" / "state_names_l_russian.yml").read_text(
    encoding="utf-8-sig"
)
for match in re.finditer(r'STATE_(\d+):\s*"([^"]+)"', loc):
    names[int(match.group(1))] = match.group(2)

york = pos.get(16576)
eirmi = pos.get(16594)
print("York 16576", york)
print("Eirmi 16594", eirmi)
print("Zatern 16593", pos.get(16593))
print("Port Amir 8243", pos.get(8243))
print("Eshatta VP 16587", pos.get(16587))
print()

rows = []
for sid, info in states.items():
    xs = []
    zs = []
    for pid in info["provs"]:
        if pid in pos:
            xs.append(pos[pid][0])
            zs.append(pos[pid][1])
    if not xs:
        continue
    rows.append(
        (
            sid,
            info["owner"],
            names.get(sid, "?"),
            sum(xs) / len(xs),
            sum(zs) / len(zs),
            len(info["provs"]),
        )
    )

mx = (york[0] + eirmi[0]) / 2
mz = (york[1] + eirmi[1]) / 2
print("States near York/Eirmi midpoint:")
near = []
for sid, owner, name, cx, cz, count in rows:
    dist = ((cx - mx) ** 2 + (cz - mz) ** 2) ** 0.5
    near.append((dist, sid, owner, name, cx, cz, count))
near.sort()
for dist, sid, owner, name, cx, cz, count in near[:30]:
    print(
        f"  d={dist:7.1f}  state {sid:3d}  {owner:3s}  {name:25s}  "
        f"({cx:.1f}, {cz:.1f})  n={count}"
    )

print()
print("Focus states:")
for sid in (75, 81, 102, 106, 107, 108, 109, 110, 111, 121, 122, 123, 124, 320, 324, 325):
    info = states[sid]
    xs = [pos[pid][0] for pid in info["provs"] if pid in pos]
    zs = [pos[pid][1] for pid in info["provs"] if pid in pos]
    cx = sum(xs) / len(xs)
    cz = sum(zs) / len(zs)
    print(
        f"  {sid:3d} {info['owner']:3s} {names.get(sid, '?'):25s} "
        f"centroid=({cx:.1f},{cz:.1f}) n={len(info['provs'])}"
    )

from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parents[1]
text = (root / "map" / "definition.csv").read_bytes().decode("utf-8-sig")
by_color = {}
by_id = {}
for line in text.splitlines():
    fields = line.split(";")
    if len(fields) < 7 or not fields[0].isdigit():
        continue
    pid = int(fields[0])
    rgb = (int(fields[1]), int(fields[2]), int(fields[3]))
    info = {"id": pid, "kind": fields[4], "coastal": fields[5].lower() == "true", "rgb": rgb}
    by_id[pid] = info
    by_color[rgb] = pid

image = Image.open(root / "map" / "provinces.bmp").convert("RGB")
width, height = image.size
pixels = image.load()
counts = Counter()
targets = {1017, 10440, 12553}
coords = defaultdict(list)
for y in range(height):
    for x in range(width):
        pid = by_color.get(pixels[x, y])
        if pid is None:
            continue
        counts[pid] += 1
        if pid in targets and len(coords[pid]) < 8:
            coords[pid].append((x, y))

print("map size", width, height)
for pid in sorted(targets):
    print(pid, by_id[pid], "pixels", counts[pid], "samples", coords[pid])

ortho = ((-1, 0), (1, 0), (0, -1), (0, 1))
for pid in sorted(targets):
    neighbours = Counter()
    for y in range(height):
        for x in range(width):
            if by_color.get(pixels[x, y]) != pid:
                continue
            for dx, dy in ortho:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                npid = by_color.get(pixels[nx, ny])
                if npid and npid != pid:
                    info = by_id[npid]
                    neighbours[(npid, info["kind"], info["coastal"])] += 1
    print("neighbors", pid, neighbours.most_common(12))

ports = set()
for line in (root / "map" / "buildings.txt").read_text(encoding="utf-8").splitlines():
    parts = line.split(";")
    if len(parts) >= 7 and parts[1] in {"naval_base", "naval_base_spawn"}:
        try:
            ports.add(int(parts[6]))
        except ValueError:
            pass

missing = [
    (pid, counts[pid])
    for pid, info in by_id.items()
    if info["kind"] == "land" and info["coastal"] and pid not in ports
]
print("coastal land without port", len(missing))
print("smallest missing", sorted(missing, key=lambda item: item[1])[:40])
print("crash ids missing", [item for item in missing if item[0] in targets])
print("tiny land provinces <3", [(pid, counts[pid], by_id[pid]["kind"], by_id[pid]["coastal"]) for pid, n in counts.items() if n < 3 and by_id[pid]["kind"] == "land"])

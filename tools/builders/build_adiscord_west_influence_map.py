"""Build the western political map and its presentation-only native bindings.

Owns west_influence PNGs, the standalone mockup and marked interface,
scripted-GUI, UI-trigger and localisation sections. Default mode never writes.
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
OUT = Path("gfx/interface/west_influence")
GUI = Path("interface/ADISCORD_western_continent.gui")
GFX = Path("interface/ADISCORD_western_continent.gfx")
SGUI = Path("common/scripted_guis/ADISCORD_west_final_war_scripted_gui.txt")
TRIGGERS = Path("common/scripted_triggers/ADISCORD_west_final_war_triggers.txt")
SCRIPTED_LOC = Path("common/scripted_localisation/ADISCORD_west_final_war_scripted_loc.txt")
MOCKUP = Path("docs/mockups/west_influence.html")
WIDTH, HEIGHT = 436, 300
REGIONAL = ("PWR", "PSD", "ZAO", "WIT", "IIA", "IBA", "IBL", "WPA", "WPS", "ROM", "TRU")
SOURCE_OWNERS = {*REGIONAL, "WRK", "IVN"}
BEGIN = "# BEGIN GENERATED WEST INFLUENCE MAP"
END = "# END GENERATED WEST INFLUENCE MAP"
PALETTE = ((48, 59, 65), (110, 122, 122), (144, 121, 76), (222, 187, 105),
           (69, 111, 139), (116, 184, 220), (113, 128, 127), (63, 73, 79))
LABELS = {"PWR": "Риматская инженерная директория", "PSD": "Грейн", "ZAO": "Заозерская республика",
          "WIT": "Город-государство Римат", "IIA": "Иторское островное управление", "IBA": "Норвейн",
          "IBL": "Крайтская директория", "WPA": "Республика Норвен", "WPS": "Хольденский синдикат",
          "ROM": "Республика Фреалор", "TRU": "Золоторевская республика", "WRK": "Воркерланд", "IVN": "Итора"}
DEMO_FRAMES = {"PWR": 6, "PSD": 1, "ZAO": 6, "WIT": 6, "IIA": 8, "IBA": 1,
               "IBL": 1, "WPA": 1, "WPS": 1, "ROM": 6, "TRU": 6, "WRK": 4, "IVN": 6}


def geography():
    colors = {}
    land = []
    with (ROOT / "map/definition.csv").open(encoding="utf-8-sig") as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) > 4 and row[0].isdigit():
                color = int(row[1]) * 65536 + int(row[2]) * 256 + int(row[3])
                colors[int(row[0])] = color
                if row[4] == "land":
                    land.append(color)
    states = {}
    for path in sorted((ROOT / "history/states").glob("*.txt")):
        source = re.sub(r"#.*", "", path.read_text(encoding="utf-8-sig"))
        owner = re.search(r"\bowner\s*=\s*(\w+)", source)
        if owner is None or owner[1] not in SOURCE_OWNERS:
            continue
        state = int(re.search(r"\bid\s*=\s*(\d+)", source)[1])
        provinces = re.search(r"\bprovinces\s*=\s*\{([^}]+)\}", source)[1]
        states[state] = {"owner": owner[1], "colors": [colors[int(p)] for p in re.findall(r"\d+", provinces)]}
    with Image.open(ROOT / "map/provinces.bmp") as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint32)
    packed = rgb[:, :, 0] * 65536 + rgb[:, :, 1] * 256 + rgb[:, :, 2]
    selected = np.isin(packed, [c for info in states.values() for c in info["colors"]])
    yy, xx = np.nonzero(selected)
    if not len(xx):
        raise ValueError("Western states absent from provinces.bmp")
    box = (max(0, int(xx.min()) - 25), max(0, int(yy.min()) - 25),
           min(packed.shape[1], int(xx.max()) + 26), min(packed.shape[0], int(yy.max()) + 26))
    crop = packed[box[1]:box[3], box[0]:box[2]]
    scale = min(WIDTH / crop.shape[1], HEIGHT / crop.shape[0])
    size = (round(crop.shape[1] * scale), round(crop.shape[0] * scale))
    offset = ((WIDTH - size[0]) // 2, (HEIGHT - size[1]) // 2)

    def project(selection):
        raw = Image.fromarray(selection.astype(np.uint8) * 255)
        canvas = Image.new("L", (WIDTH, HEIGHT))
        canvas.paste(raw.resize(size, Image.Resampling.NEAREST), offset)
        return canvas

    visible = {}
    for state, info in sorted(states.items()):
        mask = project(np.isin(crop, info["colors"]))
        bounds = mask.getbbox()
        # Subpixel capital wards are contextual geography at this continental scale.
        if bounds:
            visible[state] = {"owner": info["owner"], "mask": mask, "box": bounds}
    return {"states": visible, "land": project(np.isin(crop, land)), "source_box": box}


def state_strip(mask):
    width, height = mask.size
    strip = Image.new("RGBA", (width * 8, height))
    rim = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
    yy, xx = np.indices((height, width))
    for index, color in enumerate(PALETTE):
        frame = Image.new("RGBA", mask.size, (*color, 255))
        if index in (6, 7):
            hatch = ((yy % 6 == 0) if index == 6 else ((xx + yy) % 7 == 0))
            pattern = Image.fromarray(hatch.astype(np.uint8) * 95)
            ink = Image.new("RGBA", mask.size, (202, 212, 205, 255))
            ink.putalpha(pattern)
            frame.alpha_composite(ink)
        edge = Image.new("RGBA", mask.size, tuple(min(255, channel + 28) for channel in color))
        edge.putalpha(rim)
        frame.alpha_composite(edge)
        frame.putalpha(mask)
        strip.paste(frame, (width * index, 0))
    return strip


def render_images():
    geometry = geography()
    background = Image.new("RGBA", (WIDTH, HEIGHT), (18, 29, 37, 255))
    background.paste((37, 48, 55, 255), (0, 0, WIDTH, HEIGHT), geometry["land"])
    draw = ImageDraw.Draw(background)
    for x in range(16, WIDTH, 32):
        for y in range(12, HEIGHT, 32):
            draw.point((x, y), fill=(60, 75, 83, 255))
    draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=(80, 96, 103, 255))
    images = {"background.png": background}
    for state, info in geometry["states"].items():
        images[f"state_{state}.png"] = state_strip(info["mask"].crop(info["box"]))
    badge = Image.new("RGBA", (36 * 8, 28))
    draw = ImageDraw.Draw(badge)
    for index, color in enumerate(PALETTE):
        x = index * 36
        draw.rectangle((x, 0, x + 35, 27), fill=(28, 38, 45, 255), outline=color)
        draw.rectangle((x + 1, 24, x + 34, 26), fill=color)
    images["badge.png"] = badge
    for tag in REGIONAL:
        with Image.open(ROOT / f"gfx/flags/medium/{tag}.tga") as image:
            images[f"flag_{tag}.png"] = image.convert("RGBA").resize((30, 19), Image.Resampling.LANCZOS)
    panel = Image.new("RGBA", (460, 420), (25, 34, 40, 255))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, 459, 419), outline=(73, 89, 96, 255))
    draw.line((12, 30, 447, 30), fill=(73, 89, 96, 255))
    draw.line((12, 336, 447, 336), fill=(73, 89, 96, 255))
    images["panel.png"] = panel
    return images, geometry


def icon(name, sprite, x, y, tooltip=None, passive=False, frame=1):
    lines = ["\t\ticonType = {", f'\t\t\tname = "{name}"',
             f"\t\t\tposition = {{ x = {x} y = {y} }}", f'\t\t\tquadTextureSprite = "{sprite}"',
             f"\t\t\tframe = {frame}"]
    if tooltip:
        lines.append(f'\t\t\tpdx_tooltip = "{tooltip}"')
    if passive:
        lines.append("\t\t\talwaystransparent = yes")
    return "\n".join([*lines, "\t\t}"])


def textbox(name, key, x, y, width, height, tooltip=None):
    lines = ["\t\tinstantTextBoxType = {", f'\t\t\tname = "{name}"',
             f"\t\t\tposition = {{ x = {x} y = {y} }}", f'\t\t\ttext = "{key}"',
             '\t\t\tfont = "hoi_16mbs"', f"\t\t\tmaxWidth = {width}", f"\t\t\tmaxHeight = {height}",
             '\t\t\tfixedsize = yes', '\t\t\tformat = center']
    if tooltip:
        lines.append(f'\t\t\tpdx_tooltip = "{tooltip}"')
    else:
        lines.append('\t\t\talwaystransparent = yes')
    return "\n".join([*lines, '\t\t}'])


def gui_block(geometry):
    parts = ['\tcontainerWindowType = {\n\t\tname = "ADISCORD_west_influence_window"\n'
             '\t\tposition = { x = 0 y = 0 }\n\t\tsize = { width = 460 height = 420 }',
             icon("ADISCORD_west_map_panel", "GFX_ADISCORD_west_map_panel", 0, 0, passive=True),
             textbox("ADISCORD_west_map_scale", "ADISCORD_west_map_scale", 12, 7, 436, 22, "ADISCORD_west_map_rules_tt"),
             icon("ADISCORD_west_map_background", "GFX_ADISCORD_west_map_background", 12, 34, passive=True)]
    for state, info in geometry["states"].items():
        name = f"ADISCORD_west_map_state_{state}"
        x, y, _, _ = info["box"]
        parts.append(icon(name, "GFX_" + name, 12 + x, 34 + y, name + "_tt"))
    for index, tag in enumerate(REGIONAL):
        x = 12 + index * 40
        parts.append(icon(f"ADISCORD_west_map_country_{tag}", "GFX_ADISCORD_west_map_badge", x, 345,
                          f"ADISCORD_west_map_{tag}_tt"))
        parts.append(icon(f"ADISCORD_west_map_flag_{tag}", f"GFX_ADISCORD_west_map_flag_{tag}", x + 3, 348, passive=True))
    parts.append(textbox("ADISCORD_west_map_legend", "ADISCORD_west_map_legend", 12, 380, 436, 34,
                         "ADISCORD_west_map_rules_tt"))
    return "\n\n".join([*parts, "\t}"]) + "\n"


def gfx_block(images):
    parts = []
    for filename in images:
        name = Path(filename).stem
        frames = 8 if name.startswith("state_") or name == "badge" else 1
        parts.append("\n".join(['\tspriteType = {', f'\t\tname = "GFX_ADISCORD_west_map_{name}"',
                                f'\t\ttexturefile = "{(OUT / filename).as_posix()}"',
                                f'\t\tnoOfFrames = {frames}', '\t\ttransparencecheck = yes', '\t}']))
    return "\n\n".join(parts) + "\n"


def scripted_gui(geometry):
    triggers = []
    properties = []
    for state in geometry["states"]:
        name = f"ADISCORD_west_map_state_{state}"
        triggers.append(f'''\t\t\t{name}_visible = {{
\t\t\t\tset_temp_variable = {{ var = ADISCORD_west_map_frame value = 1 }}
\t\t\t\t{state} = {{
\t\t\t\t\towner = {{ ADISCORD_west_map_set_country_frame = yes }}
\t\t\t\t}}
\t\t\t\tset_temp_variable = {{ var = {name}_frame value = ADISCORD_west_map_frame }}
\t\t\t\talways = yes
\t\t\t}}''')
        properties.append(f"\t\t\t{name} = {{ frame = {name}_frame }}")
    for tag in REGIONAL:
        name = f"ADISCORD_west_map_country_{tag}"
        triggers.append(f'''\t\t\t{name}_visible = {{
\t\t\t\tset_temp_variable = {{ var = ADISCORD_west_map_frame value = 1 }}
\t\t\t\t{tag} = {{ ADISCORD_west_map_set_country_frame = yes }}
\t\t\t\tset_temp_variable = {{ var = {name}_frame value = ADISCORD_west_map_frame }}
\t\t\t\talways = yes
\t\t\t}}''')
        properties.append(f"\t\t\t{name} = {{ frame = {name}_frame }}")
    return ('scripted_gui = {\n\tADISCORD_west_influence_panel = {\n'
            '\t\tcontext_type = decision_category\n\t\twindow_name = "ADISCORD_west_influence_window"\n'
            '\t\tvisible = { ADISCORD_west_influence_open = yes }\n\t\tai_enabled = { always = no }\n'
            '\t\ttriggers = {\n' + '\n'.join(triggers) + '\n\t\t}\n\t\tproperties = {\n' +
            '\n'.join(properties) + '\n\t\t}\n\t}\n}\n')


def frame_trigger():
    # Order matches ADISCORDWestLean. Only champions and unrelated owners need
    # map-specific branches; the authoritative influence predicates stay shared.
    cases = (("exists = no", 1), ("tag = event_target:ADISCORD_vorkerland_nation", 4),
             ("tag = IVN", 6), ("ADISCORD_west_regional_country = no", 1),
             ("ADISCORD_west_on_wrk_side = yes", 4), ("ADISCORD_west_on_ivn_side = yes", 6),
             ("has_country_flag = ADISCORD_west_neutral", 7), ("is_subject = yes", 8),
             ("ADISCORD_west_leans_to_wrk_ally = yes", 4), ("ADISCORD_west_leans_to_ivn_ally = yes", 6),
             ("ADISCORD_west_grants_wrk_transit = yes", 3), ("ADISCORD_west_grants_ivn_transit = yes", 5))
    lines = ["# COUNTRY. Presentation-only frame; no campaign state is written.",
             "ADISCORD_west_map_set_country_frame = {",
             "\tset_temp_variable = { var = ADISCORD_west_map_frame value = 2 }"]
    for index, (condition, frame) in enumerate(cases):
        lines.extend([f"\t{'if' if index == 0 else 'else_if'} = {{", f"\t\tlimit = {{ {condition} }}",
                      f"\t\tset_temp_variable = {{ var = ADISCORD_west_map_frame value = {frame} }}", "\t}"])
    return "\n".join([*lines, "}", ""])


def scripted_loc():
    return '''defined_text = {
\tname = ADISCORDWestMapStatus
\ttext = {
\t\ttrigger = { tag = event_target:ADISCORD_vorkerland_nation }
\t\tlocalization_key = ADISCORD_west_map_champion_wrk
\t}
\ttext = {
\t\ttrigger = { tag = IVN }
\t\tlocalization_key = ADISCORD_west_map_champion_ivn
\t}
\ttext = {
\t\ttrigger = { ADISCORD_west_regional_country = no }
\t\tlocalization_key = ADISCORD_west_map_outside
\t}
\ttext = { localization_key = ADISCORD_west_map_owner_status }
}
'''


def localisation(geometry, language):
    if language == "russian":
        texts = {
            "scale": "§Y+100 Воркерланд§!                         §CИтора -100§!",
            "legend": "Светлый - союз. Тёмный - проход.\\nШтрихи: нейтралитет / зависимость.",
            "rules_tt": "§YПолитическая карта Запада§!\\nЗолотой - Воркерланд, синий - Итора.\\n\\nСклонность от +50 или до -50: готовность вступить в войну на соответствующей стороне. От +20 или до -20: проход войск для нейтральной страны.\\n\\nСерый - колебание; горизонтальные штрихи - объявленный нейтралитет; диагональные - зависимая страна. Уже выбранная сторона войны имеет приоритет над шкалой.\\n\\nЦвет территории следует её текущему владельцу. Наведите курсор на участок карты или флаг страны для подробностей.",
            "champion_wrk": "§YВоркерланд: претендент на господство на Западе§!",
            "champion_ivn": "§CИтора: претендент на господство на Западе§!",
            "outside": "§gВладелец не участвует в западной шкале влияния.§!",
            "owner_status": "[ADISCORDWestLean]",
        }
        state_text = "§Y[{state}.Owner.GetName]§!\\n[{state}.Owner.ADISCORDWestMapStatus]\\n\\nТерритория: [{state}.GetName]\\nКонтролёр: [{state}.Controller.GetName]"
    else:
        texts = {
            "scale": "§Y+100 Vorkerland§!                         §CItora -100§!",
            "legend": "Bright - alliance. Muted - transit.\\nHatching - neutrality or dependency. Hover for details.",
            "rules_tt": "§YPolitical map of the West§!\\nGold - Vorkerland; blue - Itora.\\n\\nA lean of +50 or -50 means readiness to join that side of the war. +20 or -20 grants military transit through a neutral country.\\n\\nGrey - undecided; horizontal lines - declared neutrality; diagonal lines - a subject country. A chosen war side takes priority over the lean score.\\n\\nTerritories follow their current owner. Hover over a map area or country flag for details.",
            "champion_wrk": "§YVorkerland: contender for western supremacy§!",
            "champion_ivn": "§CItora: contender for western supremacy§!",
            "outside": "§gThis owner does not participate in western influence.§!",
            "owner_status": "[ADISCORDWestLean]",
        }
        state_text = "§Y[{state}.Owner.GetName]§!\\n[{state}.Owner.ADISCORDWestMapStatus]\\n\\nTerritory: [{state}.GetName]\\nController: [{state}.Controller.GetName]"
    lines = [f' ADISCORD_west_map_{key}:0 "{value}"' for key, value in texts.items()]
    for state in geometry["states"]:
        lines.append(f' ADISCORD_west_map_state_{state}_tt:0 "{state_text.format(state=state)}"')
    for tag in REGIONAL:
        lines.append(f' ADISCORD_west_map_{tag}_tt:0 "§Y[{tag}.GetName]§!\\n[{tag}.ADISCORDWestLean]"')
    return "\n".join(lines) + "\n"


def managed_section(path, content, root_block=False):
    source = (ROOT / path).read_bytes() if (ROOT / path).exists() else b""
    newline = b"\r\n" if b"\r\n" in source else b"\n"
    indent = b"\t" if root_block else b""
    body = content.rstrip("\n").replace("\n", newline.decode()).encode("utf-8")
    replacement = indent + BEGIN.encode() + newline + body + newline + indent + END.encode() + newline
    if BEGIN.encode() in source or END.encode() in source:
        if source.count(BEGIN.encode()) != 1 or source.count(END.encode()) != 1:
            raise ValueError(f"Ambiguous generated section in {path}")
        pattern = rb"(?m)^[\t ]*" + BEGIN.encode() + rb"\r?\n.*?^[\t ]*" + END.encode() + rb"\r?\n"
        output, count = re.subn(pattern, lambda _: replacement, source, flags=re.S)
        if count != 1:
            raise ValueError(f"Unterminated generated section in {path}")
        return output
    if root_block:
        match = re.search(rb"(?m)^}[ \t]*(?:\r?\n)?\Z", source)
        if not match:
            raise ValueError(f"Expected native root in {path}")
        return source[:match.start()] + newline + replacement + source[match.start():]
    return source + (newline if source and not source.endswith(newline * 2) else b"") + replacement


def png_bytes(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def mockup_html(images, geometry):
    assets = {Path(name).stem: "data:image/png;base64," + base64.b64encode(png_bytes(image)).decode() for name, image in images.items()}
    states = {}
    for state, info in geometry["states"].items():
        mask = info["mask"].crop(info["box"])
        rows = []
        for row in np.asarray(mask):
            edges = np.flatnonzero(np.diff(np.pad((row > 0).astype(np.int8), (1, 1))))
            rows.append(edges.reshape(-1, 2).tolist())
        states[state] = {"box": info["box"], "owner": info["owner"], "rows": rows}
    data = json.dumps({"assets": assets, "states": states, "countries": REGIONAL, "labels": LABELS,
                       "frames": DEMO_FRAMES}, separators=(",", ":"))
    return ('''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<!-- Generated by tools/builders/build_adiscord_west_influence_map.py. -->
<title>Влияние на Западе / политическая карта</title><style>
*{box-sizing:border-box}body{margin:0;background:#111a20;color:#d7e2df;font:14px system-ui,sans-serif}
main{max-width:1050px;margin:44px auto;padding:0 24px}h1{font-size:30px;margin:10px 0}p{color:#a1b3bb;line-height:1.6}
.eyebrow{color:#cdb67b;font-size:11px;letter-spacing:3px}.layout{display:flex;gap:36px;align-items:flex-start;flex-wrap:wrap;margin-top:28px}
#panel{position:relative;width:460px;height:420px;flex-shrink:0;background:#192228;border:1px solid #495960}
.sprite{position:absolute;background-repeat:no-repeat;pointer-events:none}.scale{position:absolute;top:7px;left:12px;width:436px;height:23px;display:flex;justify-content:space-between;padding:0 12px;font-weight:600}
.gold{color:#debb69}.blue{color:#74b8dc}.legend{position:absolute;left:12px;top:380px;width:436px;text-align:center;font-size:12px;line-height:17px}
.controls{width:460px;margin:24px 0;display:grid;grid-template-columns:1fr 1fr;gap:10px}label{font-size:12px;display:grid;gap:5px;color:#a1b3bb}
select,button{font:inherit;background:#1d2a32;color:#d7e2df;border:1px solid #455962;padding:7px;border-radius:3px}
.aside{max-width:370px}.aside h2{font-size:18px}.key{display:flex;align-items:center;gap:10px;margin:14px 0}.chip{width:24px;height:16px;flex-shrink:0}
#tip{position:fixed;display:none;white-space:pre-line;max-width:300px;pointer-events:none;z-index:10;background:#10181e;border:1px solid #7c8c92;padding:12px;line-height:1.5;box-shadow:0 4px 12px #0007}
.note{border-top:1px solid #384a53;padding-top:18px;font-size:12px;max-width:850px}
</style><main><div class="eyebrow">ЗАПАД / ДИПЛОМАТИЯ / ВЛИЯНИЕ</div><h1>Карта политических склонностей</h1>
<p>Страны видны по территории, выбор стороны - по цвету. Наведите курсор на карту или флаг.</p>
<div class="layout"><section><div id="panel"><div class="scale" id="rules"><span class="gold">+100 Воркерланд</span><span class="blue">Итора -100</span></div>
<div class="legend">Светлый цвет - союз. Приглушённый - проход.<br>Штрихи - нейтралитет или зависимость.</div></div><div class="controls" id="controls"></div></section>
<aside class="aside"><h2>Один взгляд на баланс сил</h2>
<div class="key"><i class="chip" style="background:#debb69"></i>Готовность выступить с Воркерландом</div>
<div class="key"><i class="chip" style="background:#90794c"></i>Проход войск Воркерланда</div>
<div class="key"><i class="chip" style="background:#74b8dc"></i>Готовность выступить с Иторой</div>
<div class="key"><i class="chip" style="background:#456f8b"></i>Проход войск Иторы</div>
<div class="key"><i class="chip" style="background:#6e7a7a"></i>Колеблющаяся страна</div>
<p>Цвет участка в игре читает текущего владельца. После распада или передачи территории карта следует новым границам.</p>
<p>Нижняя строка сохраняет доступ ко всем 11 участникам, даже когда у страны сейчас нет территории.</p>
<button id="collapse">Показать пример после распада</button></aside></div>
<p class="note">Макет 1:1, 460x420. Значения влияния условные; открытая игра не считывается. Панель заменяет старую иллюстрацию и текстовый список, решения остаются ниже неё.</p>
</main><div id="tip"></div><script>
const data=__DATA__,panel=document.getElementById('panel'),tip=document.getElementById('tip');
const labels=['Вне шкалы / отсутствует','Колеблется','Склоняется к Воркерланду: проход','Готова выступить с Воркерландом','Склоняется к Иторе: проход','Готова выступить с Иторой','Объявлен нейтралитет','Зависимая страна'];
const nodes={},badges={};
function sprite(name,w,h,x,y,frame=1){let e=document.createElement('div');e.className='sprite';Object.assign(e.style,{width:w+'px',height:h+'px',left:x+'px',top:y+'px',backgroundImage:`url("${data.assets[name]}")`,backgroundPosition:`-${(frame-1)*w}px 0`});panel.append(e);return e;}
sprite('background',436,300,11,33);
Object.entries(data.states).forEach(([s,info])=>{let [x,y,r,b]=info.box;nodes[s]=sprite('state_'+s,r-x,b-y,11+x,33+y,data.frames[info.owner]||1);});
function status(tag){return tag==='WRK'?'Претендент: Воркерланд':tag==='IVN'?'Претендент: Итора':labels[(data.frames[tag]||1)-1];}
function show(event,value){tip.textContent=value;tip.style.display=value?'block':'none';tip.style.left=Math.min(event.clientX+16,innerWidth-320)+'px';tip.style.top=Math.min(event.clientY+16,innerHeight-tip.offsetHeight-12)+'px';}
data.countries.forEach((tag,i)=>{badges[tag]=sprite('badge',36,28,11+i*40,344,data.frames[tag]);sprite('flag_'+tag,30,19,14+i*40,347);});
panel.addEventListener('pointermove',event=>{let rect=panel.getBoundingClientRect(),x=event.clientX-rect.left-12,y=event.clientY-rect.top-34;
if(y>=311&&y<339){let index=Math.floor(x/40);let tag=data.countries[index];show(event,tag?data.labels[tag]+'\\n'+status(tag):'');return;}
if(y<0){show(event,'Шкала: от -100 до +100.\\nПорог союза: +/-50. Порог прохода: +/-20.\\nВыбранная сторона войны имеет приоритет.');return;}
for(const info of Object.values(data.states)){let [a,b,r,d]=info.box;if(x>=a&&x<r&&y>=b&&y<d&&info.rows[Math.floor(y-b)].some(([s,e])=>x-a>=s&&x-a<e)){show(event,data.labels[info.owner]+'\\n'+status(info.owner));return;}}show(event,'');});
panel.addEventListener('pointerleave',()=>tip.style.display='none');
function refresh(){Object.entries(data.states).forEach(([s,info])=>nodes[s].style.backgroundPosition=`-${((data.frames[info.owner]||1)-1)*(info.box[2]-info.box[0])}px 0`);data.countries.forEach(tag=>badges[tag].style.backgroundPosition=`-${(data.frames[tag]-1)*36}px 0`);}
data.countries.forEach(tag=>{let label=document.createElement('label');label.textContent=data.labels[tag];let select=document.createElement('select');select.id='select_'+tag;labels.forEach((name,i)=>{let o=document.createElement('option');o.textContent=name;o.value=i+1;o.selected=i+1===data.frames[tag];select.append(o);});select.onchange=()=>{data.frames[tag]=Number(select.value);refresh();};label.append(select);document.getElementById('controls').append(label);});
document.getElementById('collapse').onclick=()=>{for(const [state,tag] of Object.entries({194:'PSD',93:'PSD',94:'PSD',328:'PSD',195:'WPA',196:'WPS',322:'WPS',90:'IBA',91:'IBA'})){data.states[state].owner=tag;data.frames[tag]=2;document.getElementById('select_'+tag).value=2;}refresh();};
</script></html>'''.replace("__DATA__", data)).encode("utf-8")


def build_outputs():
    images, geometry = render_images()
    outputs = {OUT / name: png_bytes(image) for name, image in images.items()}
    outputs[GUI] = managed_section(GUI, gui_block(geometry), root_block=True)
    outputs[GFX] = managed_section(GFX, gfx_block(images), root_block=True)
    outputs[SGUI] = ("# Generated by tools/builders/build_adiscord_west_influence_map.py.\n" + scripted_gui(geometry)).encode()
    outputs[TRIGGERS] = managed_section(TRIGGERS, frame_trigger())
    outputs[SCRIPTED_LOC] = managed_section(SCRIPTED_LOC, scripted_loc())
    for language in ("russian", "english"):
        path = Path(f"localisation/{language}/ADISCORD_west_final_war_l_{language}.yml")
        outputs[path] = managed_section(path, localisation(geometry, language))
    outputs[MOCKUP] = mockup_html(images, geometry)
    return outputs, geometry


def review_image(images, geometry):
    """Compose a review in memory; no preview is part of the runtime outputs."""
    image = images["panel.png"].copy()
    image.alpha_composite(images["background.png"], (12, 34))
    for state, info in geometry["states"].items():
        x, y, right, bottom = info["box"]
        width, height = right - x, bottom - y
        frame = DEMO_FRAMES[info["owner"]] - 1
        image.alpha_composite(images[f"state_{state}.png"].crop((frame * width, 0, (frame + 1) * width, height)), (12 + x, 34 + y))
    for index, tag in enumerate(REGIONAL):
        frame = DEMO_FRAMES[tag] - 1
        image.alpha_composite(images["badge.png"].crop((frame * 36, 0, (frame + 1) * 36, 28)), (12 + index * 40, 345))
        image.alpha_composite(images[f"flag_{tag}.png"], (15 + index * 40, 348))
    draw = ImageDraw.Draw(image)
    draw.text((24, 10), "+100 VORKERLAND", fill=PALETTE[3])
    draw.text((343, 10), "ITORA -100", fill=PALETTE[5])
    draw.text((111, 383), "Bright: alliance / Muted: transit", fill=(218, 230, 225))
    draw.text((97, 400), "Hatching: neutrality or dependency", fill=(165, 183, 190))
    return image


def differences(outputs):
    return [path for path, expected in outputs.items() if not (ROOT / path).is_file() or (ROOT / path).read_bytes() != expected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare generated outputs without writing (default)")
    mode.add_argument("--apply", action="store_true", help="write changed outputs only")
    args = parser.parse_args()
    outputs, geometry = build_outputs()
    changed = differences(outputs)
    if args.apply:
        for relative in changed:
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(outputs[relative])
        print(f"West influence outputs written: {len(changed)}")
    else:
        for path in changed:
            print(f"Different or missing: {path.as_posix()}")
    remaining = differences(outputs)
    print(f"West influence outputs checked: {len(outputs)}; differences: {len(remaining)}; states: {len(geometry['states'])}")
    return int(bool(remaining))


if __name__ == "__main__":
    raise SystemExit(main())

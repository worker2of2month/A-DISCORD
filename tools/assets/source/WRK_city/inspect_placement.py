"""Inspect city placement and its map data without editing the map."""
import csv,json,re,sys
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
MOD=ROOT.parents[3]
sys.path.insert(0,str(MOD))
from tools.validators.validate_adiscord_vorkerland_collapse import named_blocks,named_block

provinces=Image.open(MOD/'map/provinces.bmp').convert('RGB')
heights=Image.open(MOD/'map/heightmap.bmp')
definitions={tuple(map(int,row[1:4])):{'province':int(row[0]),'terrain':row[6]} for row in csv.reader((MOD/'map/definition.csv').open(),delimiter=';') if len(row)>6 and row[0].isdigit()}
source=(MOD/'map/ambient_object.txt').read_text()
rows=[]
for group in named_blocks(source,'type'):
    kind=re.search(r'type\s*=\s*"([^"]+)"',group).group(1)
    if not ('cityblock' in kind or 'skyscraper' in kind):
        continue
    scale=float(re.search(r'\bscale\s*=\s*([\d.]+)',group).group(1))
    for obj in named_blocks(group,'object'):
        xyz=list(map(float,re.search(r'position\s*=\s*\{([^}]+)',obj).group(1).split()))
        rotation=list(map(float,re.search(r'rotation\s*=\s*\{([^}]+)',obj).group(1).split()))
        x,y=round(xyz[0]),provinces.height-1-round(xyz[2])
        province=definitions[provinces.getpixel((x,y))]
        rows.append({'type':kind,'scale':scale,'position':xyz,'rotation':rotation,**province,'height_pixel':heights.getpixel((x,y)),'vorkensberg':3100<=xyz[0]<=3210 and 680<=xyz[2]<=770})
report={'map_size':provinces.size,'heightmap_size':heights.size,'rows':rows}
(ROOT/'existing_placement.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'map_size':provinces.size,'city_count':sum(r['vorkensberg'] for r in rows),'city_height_values':sorted(set(r['height_pixel'] for r in rows if r['vorkensberg'])),'outside_count':sum(not r['vorkensberg'] for r in rows),'terrain_types':sorted(set(r['terrain'] for r in rows if r['vorkensberg']))}))

"""Read-only inventory of actual bundled artwork for the faction UI."""
from pathlib import Path
from PIL import Image
import json
import zipfile
out=Path('/tmp/party-evidence');out.mkdir(exist_ok=True)
rows=[]
with zipfile.ZipFile(out/'stat-icons.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in Path('gfx').rglob('*'):
        if not p.is_file() or p.suffix.lower() not in ('.png','.dds','.tga'):continue
        if p.stat().st_size>200000:continue
        if 'texticons' in p.parts or any(k in p.name.lower() for k in ('orga','stability','morale','planning','cohesion','command')):
            try:
                with Image.open(p) as im:wh=im.size
            except Exception as exc:
                rows.append({'path':str(p),'error':str(exc)});continue
            rows.append({'path':str(p),'size':wh})
            z.write(p,str(p))
(out/'stat-icons.json').write_text(json.dumps(rows,indent=2))
print('Bundled icons',len(rows))
for r in rows:
    if any(k in r['path'].lower() for k in ('org','stabil','morale')): print(r)

"""Package shared architectural textures without modifying their source files."""
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
MOD=ROOT.parents[3]
sys.path.insert(0,str(ROOT.parent/'WRK_unity_tower'))
from package_tower import mip_chain


def main():
    source=MOD/'gfx/models/buildings/vorkerland_special'
    inputs={}
    for material,suffix in [('glass','windows'),('concrete','wall'),('roof','roof')]:
        path=source/f'ADISCORD_vorkerland_pyramid_{suffix}.dds'
        image=Image.open(path).convert('RGB').convert('RGBA')
        (ROOT/f'City_{material}_diffuse.dds').write_bytes(mip_chain(image))
        inputs[str(path.relative_to(MOD))]=hashlib.sha256(path.read_bytes()).hexdigest()
    # A technical swatch atlas supplies untextured metal, paving and planted beds.
    palette=Image.new('RGBA',(256,256))
    colors=[(65,72,79),(40,45,49),(107,89,57),(45,62,41),
            (68,70,71),(136,126,108),(93,105,110),(113,109,101)]
    for index,color in enumerate(colors):
        palette.paste((*color,255),(index*32,0,(index+1)*32,256))
    (ROOT/'City_detail_diffuse.dds').write_bytes(mip_chain(palette))
    for name,gloss,strength in [('glass',92,75),('concrete',18,14),('roof',21,16),('detail',30,22)]:
        image=Image.new('RGBA',(256,256),(0,strength,0,gloss))
        (ROOT/f'City_{name}_specular.dds').write_bytes(mip_chain(image))
    (ROOT/'City_normal.dds').write_bytes(mip_chain(Image.new('RGBA',(256,256),(128,128,0,128))))
    atlas=Image.open(ROOT/'City_glass_screen_atlas.png').convert('RGB').convert('RGBA')
    w,h=atlas.size
    for name,box,gloss in [('glass_teal',(0,0,w//2,h//2),110),
                           ('glass_bronze',(w//2,0,w,h//2),100),
                           ('glass_silver',(0,h//2,w//2,h),90)]:
        tile=atlas.crop(box).resize((1024,1024),Image.Resampling.LANCZOS)
        (ROOT/f'City_{name}_diffuse.dds').write_bytes(mip_chain(tile))
        (ROOT/f'City_{name}_specular.dds').write_bytes(mip_chain(Image.new('RGBA',(256,256),(0,75,0,gloss))))
    (ROOT/'City_screen_normal.dds').write_bytes(mip_chain(Image.new('RGBA',(256,256),(128,128,180,128))))
    ads=Image.open(ROOT/'City_advertisements.png').convert('RGB').convert('RGBA').resize((1024,1024),Image.Resampling.LANCZOS)
    (ROOT/'City_screen_diffuse.dds').write_bytes(mip_chain(ads))
    (ROOT/'City_screen_specular.dds').write_bytes(mip_chain(Image.new('RGBA',(256,256),(0,75,0,70))))
    (ROOT/'material_sources.json').write_text(json.dumps({'source_sha256':inputs,'shader':'PdxMeshAdvancedSnow','opaque_diffuse':True,'normal_encoding':'HOI4 flat normal: X in green, Y in alpha with sign inversion; blue controls night emission','textures':'BC3 full mip chains'},indent=2))
    print('Prepared 18 shared DDS textures; original textures unchanged')


if __name__=='__main__':
    main()

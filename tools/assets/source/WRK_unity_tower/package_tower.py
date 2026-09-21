"""Prepare a procedural concrete material and package the independent tower asset."""
import argparse
import hashlib
import io
import json
import random
import struct
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
MOD = ROOT.parents[3]
DEST = MOD/'gfx/models/buildings/ADISCORD_unity_tower'
MAX_TEXTURE_EDGE = 2048


def mip_chain(image):
    image = image.convert('RGBA')
    chunks = []
    header = None
    while True:
        stream = io.BytesIO()
        image.save(stream, format='DDS', pixel_format='DXT5')
        data = stream.getvalue()
        if header is None:
            header = bytearray(data[:128])
        chunks.append(data[128:])
        if image.size == (1,1):
            break
        image = image.resize((max(1,image.width//2),max(1,image.height//2)), Image.Resampling.LANCZOS)
    struct.pack_into('<I',header,8,struct.unpack_from('<I',header,8)[0]|0x20000)
    struct.pack_into('<I',header,28,len(chunks))
    struct.pack_into('<I',header,108,struct.unpack_from('<I',header,108)[0]|0x400008)
    return bytes(header)+b''.join(chunks)


def prepare():
    randomizer = random.Random(16428)
    image = Image.new('RGBA',(512,512))
    pixels = []
    for y in range(512):
        for x in range(512):
            value = 35 + randomizer.randrange(-8,9) + ((x//31+y//23)%3)*3
            pixels.append((value+3,value+1,value,255))
    image.putdata(pixels)
    maps = {'diffuse':image, 'normal':Image.new('RGBA',(512,512),(128,128,0,128)),
            'specular':Image.new('RGBA',(512,512),(0,20,0,18))}
    for kind, image in maps.items():
        (ROOT/f'Tower_concrete_{kind}.dds').write_bytes(mip_chain(image))


def prepare_baked():
    diffuse = Image.open(ROOT/'Tower_fire_diffuse.png').convert('RGB').convert('RGBA')
    # Keep the bake resolution independent of the engine texture-size limit.
    diffuse.thumbnail((MAX_TEXTURE_EDGE, MAX_TEXTURE_EDGE), Image.Resampling.LANCZOS)
    maps = {'diffuse':diffuse,
            # PdxMeshStandard reads RGB normals, without the advanced GA packing.
            'normal':Image.new('RGBA',(512,512),(128,128,255,255)),
            'specular':Image.new('RGBA',(512,512),(0,16,0,14))}
    for kind,image in maps.items():
        (ROOT/f'Tower_fire_{kind}.dds').write_bytes(mip_chain(image))


def package(apply=False):
    names = ['ADISCORD_unity_tower_destruction.mesh','ADISCORD_unity_tower_collapse.anim','ADISCORD_unity_tower_ruins.anim']
    files = {name:(ROOT/name).read_bytes() for name in names}
    for kind in ('diffuse','normal','specular'):
        name=f'Tower_fire_{kind}.dds'
        files[name]=(ROOT/name).read_bytes()
        with Image.open(io.BytesIO(files[name])) as image:
            assert max(image.size) <= MAX_TEXTURE_EDGE, f'{name}: texture exceeds runtime limit'
            if kind == 'normal':
                assert image.convert('RGB').getextrema()[2][0] > 250, 'Standard normal must point along positive tangent Z'
    files['animation.asset'] = (
        'animation = { name = "ADISCORD_unity_tower_collapse_animation" file = "ADISCORD_unity_tower_collapse.anim" }\n'
        'animation = { name = "ADISCORD_unity_tower_ruins_animation" file = "ADISCORD_unity_tower_ruins.anim" }\n').encode()
    changed = [name for name,content in files.items() if not (DEST/name).is_file() or (DEST/name).read_bytes()!=content]
    prior = json.loads((ROOT/'package_report.json').read_text()) if (ROOT/'package_report.json').is_file() else {}
    obsolete = [name for name in prior if name not in files and (DEST/name).is_file()]
    if apply:
        DEST.mkdir(parents=True,exist_ok=True)
        for name in changed:
            (DEST/name).write_bytes(files[name])
        for name in obsolete:
            path=(DEST/name).resolve()
            assert path.parent==DEST.resolve() and path.suffix=='.dds'
            path.unlink()
        (ROOT/'package_report.json').write_text(json.dumps({name:{'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)} for name,content in files.items()},indent=2))
    print(json.dumps({'files':len(files),'changed':changed,'obsolete_owned_files':obsolete,'applied':apply}))
    return changed+obsolete


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--prepare-baked',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.prepare_baked:
        prepare_baked()
    elif package(args.apply) and args.check:
        raise SystemExit(1)

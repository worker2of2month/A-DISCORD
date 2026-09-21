"""Package native HOI4 mesh/textures with a full BC3 mip chain."""
import argparse, hashlib, io, json, math, struct
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).parent
MOD=ROOT.parents[3]
DEST=MOD/'gfx/models/units/STP_shabrat'

def resize_channels(image, size):
    """Filter packed data channels without treating gloss/normal Y as opacity."""
    return Image.merge('RGBA',tuple(channel.resize(size,Image.Resampling.LANCZOS)
                                    for channel in image.split()))


def dds_mips(path, *, packed_channels=False):
    image=Image.open(path).convert('RGBA')
    assert image.width==image.height and image.width in (512,1024)
    payload=[];header=None
    while True:
        buf=io.BytesIO();image.save(buf,format='DDS',pixel_format='DXT5')
        data=buf.getvalue()
        assert data[:4]==b'DDS ' and data[84:88]==b'DXT5'
        if header is None:header=bytearray(data[:128])
        payload.append(data[128:])
        if image.width==1:break
        size=(image.width//2,image.height//2)
        image=(resize_channels(image,size) if packed_channels else
               image.resize(size,Image.Resampling.LANCZOS))
    struct.pack_into('<I',header,8,struct.unpack_from('<I',header,8)[0]|0x20000)
    struct.pack_into('<I',header,28,len(payload))
    struct.pack_into('<I',header,108,struct.unpack_from('<I',header,108)[0]|0x400008)
    return bytes(header)+b''.join(payload)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    files={'STP_shabrat_infantry.mesh':(ROOT/'STP_shabrat_infantry.mesh').read_bytes()}
    for part in ('body','gear'):
        for kind in ('diffuse','normal','specular'):
            name=f'Shabrat_{part}_{kind}.dds';files[name]=dds_mips(ROOT/name)
    if args.apply:DEST.mkdir(parents=True,exist_ok=True)
    report={}
    for name,content in files.items():
        path=DEST/name
        if args.apply:path.write_bytes(content)
        assert path.read_bytes()==content, f'Stale native output: {path}'
        report[name]={'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    if args.apply:(ROOT/'package_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'verified_native_files':len(report),'mip_levels':'10 or 11, through 1x1','directory':str(DEST)},indent=2))

if __name__=='__main__':main()

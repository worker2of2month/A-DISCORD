"""Local-only visual QA using the installed, unmodified JoroDox loaders."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,unquote
import base64
import json
import re
import argparse

ROOT=Path(__file__).resolve().parent
MOD=ROOT.parents[2]
JORO=Path.home()/'AppData/Local/Google/Chrome/User Data/Default/Extensions/pmhbboeiannanamjandkhiakpaaoecoo/0.8.1_0'
ROUTES={'joro':JORO,'city':MOD/'gfx/models/buildings/ADISCORD_city',
        'weapon':MOD/'gfx/models/units/ADISCORD_weapons',
        'infantry':MOD/'gfx/models/units/ADISCORD_regulars',
        'hq':MOD/'gfx/models/units/ADISCORD_headquarters','source':ROOT}

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self,url):
        parts=unquote(urlparse(url).path).strip('/').split('/')
        if parts[0] not in ROUTES:return str(ROOT/'jorodox_preview.html')
        root=ROUTES[parts[0]].resolve()
        target=root.joinpath(*parts[1:]).resolve()
        if not target.is_relative_to(root):return str(ROOT/'nonexistent')
        return str(target)
    def do_POST(self):
        if self.path!='/capture':return self.send_error(404)
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        name=data['name']
        if not re.fullmatch(r'(city|weapon|infantry|hq)_[A-Za-z0-9_]+',name):return self.send_error(400)
        owner={'city':'WRK_city','weapon':'infantry_weapons_3d','infantry':'STP_regulars','hq':'STP_regulars'}[name.split('_',1)[0]]
        directory=ROOT/owner/'jorodox_visual'
        directory.mkdir(exist_ok=True)
        (directory/(name+'.png')).write_bytes(base64.b64decode(data['png'].split(',',1)[1]))
        (directory/(name+'.json')).write_text(json.dumps(data['evidence'],indent=2))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--infantry-root',type=Path)
    parser.add_argument('--hq-root',type=Path)
    parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args()
    if args.infantry_root:ROUTES['infantry']=args.infantry_root.resolve()
    if args.hq_root:ROUTES['hq']=args.hq_root.resolve()
    print(f'JoroDox visual QA: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

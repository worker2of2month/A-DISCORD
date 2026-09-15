"""Adapt inherited smoke events to the original VAL head locator.

Original VAL geometry/rig remains untouched. Override the complete idle group
so the same five native animation variants and chances are retained.
"""
from pathlib import Path
import argparse
import re

ROOT=Path(__file__).resolve().parents[3]
ASSET=ROOT/'gfx/entities/zz_ADISCORD_country_infantry.asset'
GAME=Path(r'Z:/SteamLibrary/steamapps/common/Hearts of Iron IV/gfx/entities/units_infantry.asset')
START='# BEGIN ADISCORD VAL native locator idle\n'
END='# END ADISCORD VAL native locator idle\n'

def blocks(text,kind):
    for match in re.finditer(r'(?m)^\s*'+kind+r'\s*=\s*\{',text):
        depth=0
        for i in range(text.index('{',match.start()),len(text)):
            if text[i]=='{':depth+=1
            elif text[i]=='}':
                depth-=1
                if not depth:
                    yield match.start(),i+1,text[match.start():i+1]
                    break

def idle_group(parent,node):
    native=GAME.read_text()
    source=next(row[2] for row in blocks(native,'entity') if re.search(r'\bname\s*=\s*"'+parent+'"',row[2]))
    idle=[row[2].strip() for row in blocks(source,'state') if re.search(r'\bname\s*=\s*"idle"',row[2])]
    assert len(idle)==5 and sum('node="head"' in state for state in idle)==1
    return '\n'.join('\t'+state.replace('node="head"',f'node="{node}"') for state in idle)+'\n'


def output():
    text=ASSET.read_text()
    labels=['VAL_infantry_entity','VAL_infantry_2_entity','ADISCORD_VAL_regular_entity']
    labels+=re.findall(r'\bname\s*=\s*"(VAL_ADISCORD_militia(?:_[2-8])?_entity)"',text)
    for label in labels:
        a,b,body=next(row for row in blocks(text,'entity') if re.search(r'\bname\s*=\s*"'+label+'"',row[2]))
        mesh=re.search(r'\bpdxmesh\s*=\s*"([^"]+)"',body)[1]
        node='back_mid|head|head' if mesh.startswith('VAL_infantry') else 'head'
        parent='infantry_rifle_entity' if label in ('VAL_infantry_entity','VAL_ADISCORD_militia_entity') else 'infantry_2_entity'
        if START in body:
            left=body.index(START)
            right=body.index(END)+len(END)
        else:
            left=right=len(body)-1
        overrides=idle_group(parent,node)
        body=body[:left]+START+overrides+END+body[right:]
        text=text[:a]+body+text[b:]
    return text.encode()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    data=output()
    changed=data!=ASSET.read_bytes()
    print({'changed':changed,'applied':args.apply,'original_VAL_mesh':'untouched'})
    if args.apply:ASSET.write_bytes(data)
    elif args.check and changed:raise SystemExit(1)

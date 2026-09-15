"""Preserve donor locator transforms without touching mesh/skin/skeleton bytes.

The donor's duplicate collision skeleton has zero bind matrices. io_pdx_mesh
imports the body rig correctly, but uses those zero matrices for locators.
Only these four new bodies reuse the donor rig unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parent
MOD=ROOT.parents[2]
DONOR=MOD/'gfx/models/units/STP_infantry_hedonist.mesh'
TARGETS=(ROOT/'STP_shabrat/STP_shabrat_infantry.mesh',
         *(ROOT/'STP_regulars'/f'{label}.mesh' for label in ('STP_party','STS_regular','VAL_regular')))
MARKER=b'[locator\0'

def corrected_bytes(path):
    path=Path(path).resolve()
    assert path in TARGETS,'Only new bodies with the unchanged donor rig are supported'
    donor=DONOR.read_bytes()
    assert hashlib.sha256(donor).hexdigest()=='50c56bdd4e3e2c67a0802d46dc4bb2d31f3ade1c31751c07f469970327772357'
    data=path.read_bytes()
    assert donor.count(MARKER)==data.count(MARKER)==1
    index=data.index(MARKER)
    tail=donor[donor.index(MARKER):]
    assert len(tail)==606
    result=data[:index]+tail
    assert result[:index]==data[:index]
    return result

def preserve_locators(path):
    path=Path(path)
    path.write_bytes(corrected_bytes(path))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    report={}
    for path in TARGETS:
        before=path.read_bytes()
        after=corrected_bytes(path)
        report[path.name]={'geometry_skin_skeleton_unchanged':True,'locator_bytes':606,
                           'changed':before!=after,'sha256':hashlib.sha256(after).hexdigest()}
        if args.apply:path.write_bytes(after)
        else:assert before==after,path.name+': locator transforms differ from native donor'
    if args.apply:(ROOT/'STP_regulars/locator_repair_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

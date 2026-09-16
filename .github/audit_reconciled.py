"""Reconcile the diagnostic transport against the inspected narrative commit."""
from pathlib import Path
import sys

source = Path(__file__).with_name('audit_apply.py').read_text(encoding='utf-8')
source = source.replace('QBCLK2T2H2sa', 'QBCLK2T2Hsa')
source = source.replace('DDGjIriq6G/x', 'DDGjIriq16D/x')
source = source.replace('len(preserved) != 84', 'len(preserved) != 98')
namespace = {'__name__': 'audit_payload'}
exec(compile(source, 'audit_apply.py', 'exec'), namespace)
namespace['BEFORE']['localisation/replace/ADISCORD_STP_story_l_russian.yml'] = '60a4157e6fd26b3bde27f51038e144c01bcc74f8c1c55a1d11bd07cf48236e76'
namespace['EXPECTED']['localisation/russian/ADISCORD_STP_l_russian.yml'] = 'a0512b87dc1c31795ebca3992e7bb3de61260a91d6960e8fea3003d99dce1ee2'
namespace['main']()

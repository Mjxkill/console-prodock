#!/usr/bin/env python3
"""Reject ambiguous authored optical networks before building resources."""
import copy,importlib.util,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('assets',root/'tools/build_assets.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
base=assets.read_worlds()
room={'id':'contract_light_fixture','name':'Contract','title':'Contract','width':16,'height':16,'tile':32,'indoors':True,'rows':['#'*16]+['#'+'.'*14+'#']*14+['#'*16],'spawn':{'x':80,'y':80},'quests':[],
 'entities':[{'id':'source','kind':'emitter','x':80,'y':176,'direction':0},
             {'id':'mirror','kind':'mirror','x':176,'y':176,'orientation':0},
             {'id':'receiver','kind':'receiver','x':176,'y':80,'grants':1}]}
arts=assets.ART+['emitter','mirror','receiver']
cases=[('source reads receiver',lambda w:w['entities'][0].update(requires=1)),
       ('source direction',lambda w:w['entities'][0].update(direction=4)),
       ('mirror orientation',lambda w:w['entities'][1].update(orientation=2)),
       ('receiver not one bit',lambda w:w['entities'][2].update(grants=3)),
       ('receiver uses sequence byte',lambda w:w['entities'][2].update(grants=1<<24)),
       ('producer shares receiver bit',lambda w:w['entities'][0].update(grants=1)),
       ('mirror is conditional',lambda w:w['entities'][1].update(requires=8)),
       ('optics overlap',lambda w:w['entities'][1].update(x=80,y=176)),
       ('off-grid optic',lambda w:w['entities'][1].update(x=177))]
with tempfile.TemporaryDirectory(prefix='light-contract-',dir=root/'build') as tmp:
 assets.OUT=Path(tmp);assets.compile_worlds(base+[room],arts+sorted({e.get('art',e['kind']) for w in base for e in w['entities']}-set(arts)))
 for label,mutate in cases:
  invalid=copy.deepcopy(room);mutate(invalid)
  try:assets.compile_worlds(base+[invalid],arts+sorted({e.get('art',e['kind']) for w in base for e in w['entities']}-set(arts)))
  except AssertionError:pass
  else:raise AssertionError('Accepted invalid optical data: '+label)
print(f'LUMA_LIGHT_CONTRACT_PASS {len(cases)} invalid networks rejected')

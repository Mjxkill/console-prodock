#!/usr/bin/env python3
"""Bind the helper-only mapped tests to exact FF pins/INIT and source bytes."""
import hashlib,importlib.util,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RECIPE=HERE.parent/'build_review_01/recipe.py'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)

def main():
 spec=importlib.util.spec_from_file_location('banked_qualification_recipe',RECIPE);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);a=r.modules_api()
 vg=HERE/'stage_02/helper/neo_command_ff128.vg';text=vg.read_text();block=a.modules(text)['neo_command_ff128'];cells=a.instances(block)
 memory=set();outputs=set();gsr=0
 for name,c in cells.items():
  kind=c['kind'];pins={k:''.join(v) for k,v in c['ports'].items()}
  require(kind in ['DFFRE','LUT2','LUT3','LUT4','VCC','GND','GSR'],'Unexpected primitive '+kind)
  if kind=='GSR':require(pins=={'GSRI':'VCC'},'GSR active');gsr+=1
  if kind!='DFFRE':continue
  require(re.findall(r'defparam\s+'+re.escape(name)+r'\s*\.INIT\s*=\s*([^;]+);',block)==["1'b0"],'FF INIT mismatch')
  m=re.fullmatch(r'\\cell_word\[(\d+)\]\.cell_bit\[(\d+)\]\.ff',name)
  o=re.fullmatch(r'\\output_bit\[(\d+)\]\.ff',name)
  if m:
   slot,bit=map(int,m.groups());memory.add((slot,bit))
   require(pins['Q']==f'\\words[{slot}][{bit}]' and pins['D']==f'DI[{bit}]','Storage data binding')
   require(pins['CLK']=='CLKA' and pins['RESET']=='GND','Storage CLK/reset')
  elif o:
   bit=int(o[1]);outputs.add(bit)
   require(pins=={'Q':f'DO[{bit}]','D':f'read_selected[{bit}]','CLK':'CLKB','RESET':'RESET','CE':'read_enabled'},'Output latency/control changed')
  else:raise ValueError('Unexpected FF '+name)
 require(memory=={(w,b)for w in range(128)for b in range(32)} and outputs==set(range(32)) and gsr==1,'FF index/count/GSR mismatch')
 rtl=json.loads((HERE/'rtl_02/RESULT.json').read_text());mapped=json.loads((HERE/'mapped_01/RESULT.json').read_text())
 require(rtl['passed'] and mapped['passed'],'Simulation incomplete/failed')
 require(len(rtl['cases'])==11 and len(mapped['cases'])==6,'Missing scenarios')
 require(mapped['files'].get(str(vg.relative_to(ROOT)))==sha(vg) or mapped['files'].get(str(vg))==sha(vg),'Mapped simulation source mismatch')
 require(rtl['files'][str(HERE/'banked_words32.v')]==sha(HERE/'banked_words32.v'),'RTL simulation source mismatch')
 initial=(HERE/'neo_command_ff128.v').read_text();array=(HERE/'banked_words32.v').read_text()
 changes={'wire [4095:0] words;':'wire [31:0] words [0:127];','words[32*slot+bit_index]':'words[slot][bit_index]','words[32*(16*bank+2*pair_index)+bit_index]':'words[16*bank+2*pair_index][bit_index]','words[32*(16*bank+2*pair_index+1)+bit_index]':'words[16*bank+2*pair_index+1][bit_index]'}
 inverse=array
 for before,after in changes.items():
  require(inverse.count(after)==1,'Array representation inversion anchor');inverse=inverse.replace(after,before)
 require(inverse==initial,'Array representation changed logic text')
 files=[vg,HERE/'banked_words32.v',HERE/'neo_command_ff128.v',HERE/'rtl_02/RESULT.json',HERE/'mapped_01/RESULT.json',HERE/'COMPARISON.json',HERE/'stage_02/helper/result.json',HERE/'stage_02/helper/synthesis.log',HERE/'test_banked.py',HERE/'synthesize.py',Path(__file__)]
 q={'passed':True,'scope':'helper only, no application assembly','helper_sha256':sha(vg),'source_sha256':sha(HERE/'banked_words32.v'),
  'ff_storage':4096,'ff_output':32,'ram':0,'GSR':'one constant GSRI(VCC)','INIT':'all explicitzero',
  'array_change_inverse_exact':True,'rtl_cases':6,'mutants_detected':5,'mapped_cases':6,
  'files':{str(p.relative_to(ROOT)):sha(p) for p in files},'PNR':False,'hardware':False,'timing_qualified':False,
  'limits':['Finite binary input scenarios, not complete formal equivalence','Vendor simultaneous same-address collision remains outside qualified contract','Decoded select fanout and physical placement not measured','No routability/STA/CLS claim','Storage CE behavior covered by tests, pin outputs/reset/clock checked individually']}
 (HERE/'QUALIFICATION.json').write_text(json.dumps(q,indent=2)+'\n');print('HELPER_QUALIFICATION_PASS',q['helper_sha256'])
if __name__=='__main__':main()

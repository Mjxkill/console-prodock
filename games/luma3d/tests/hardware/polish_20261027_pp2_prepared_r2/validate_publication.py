#!/usr/bin/env python3
"""Prove declared shooter publication against poison RAM and every atlas entry."""
import argparse,hashlib,json,re,subprocess,zlib
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3];B=R/'games/luma3d/build/arcade_polish_20261026_r6';S=B/'source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
 cmd=['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-ffunction-sections','-fdata-sections','-fsanitize=undefined']
 cmd+=['-I'+str(S/d) for d in ['games/luma3d/src','games/luma3d/include','games/luma3d/minigames','linux/drivers','fw_console']]
 cmd+=[str(C/'tests/shooter_publication.c'),'-Wl,--gc-sections','-o',str(o/'publisher')]
 subprocess.run(cmd,check=True);records=[]
 for wide,name in [(0,'boss'),(1,'boss_720')]:
  cap=B/'captures'/name;run=subprocess.run([o/'publisher',str(wide),cap.with_suffix('.memory')],capture_output=True,text=True);(o/(name+'.log')).write_text(run.stdout+run.stderr);run.check_returncode()
  d={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',run.stdout)};assert d['poison_mismatch']==d['unused'];memory=cap.with_suffix('.memory').read_bytes();ranges=[]
  for kind in ('field','atlas'):
   start=d[kind+'_offset'];length=d[kind+'_bytes'];data=memory[start:start+length];ranges.append(dict(offset=start,bytes=length,sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}'))
  overlay=json.loads(cap.with_suffix('.overlay.json').read_text());fetches=0
  def allowed(addr,n):return any(x['offset']<=addr and addr+n<=x['offset']+x['bytes'] for x in ranges)
  for layer in overlay['layers']:
   if not layer[6]&1 or layer[0]<(0x800000+(28<<20)):continue
   address=layer[0]-0x800000;width=layer[1]&65535;height=layer[1]>>16;pitch=layer[5]
   for y in range(height):assert allowed(address+y*pitch,((width+31)//32)*32);fetches+=1
  for sprite in overlay['sprites']:
   if not sprite[2]&(1<<16):continue
   address=sprite[0]-0x800000;w=sprite[2]&255;h=(sprite[2]>>8)&255
   assert 0<w<=32 and 0<h<=32 and allowed(address,1024);fetches+=32
  # A descriptor pointed into either gap must fail the same coverage predicate.
  assert not allowed(ranges[0]['offset']+ranges[0]['bytes'],32)
  assert not allowed(ranges[1]['offset']+ranges[1]['bytes'],32)
  records.append(dict(name=name,wide=wide,passed=True,counts=d,ranges=ranges,descriptor_rows=fetches,overlay_sha256=sha(cap.with_suffix('.overlay.json')),memory_sha256=sha(cap.with_suffix('.memory'))))
 report=dict(passed=True,hardware=False,records=records,game_sha256=sha(B/'luma3d-riscv'),files={str(p.relative_to(R)):sha(p) for p in [Path(__file__),C/'tests/shooter_publication.c',S/'games/luma3d/src/shooter_render.c',S/'games/luma3d/include/shooter_art.h']},limits=['Proves reference/publisher mismatch only in unused holes on poisoned host RAM','Actual PP1 useful bytes remain unqualified until strict readback of each published allocation','No hardware timing or composite LCD readback'])
 (o/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Compare the PC view to established GPU pixel/compositor reference models.

Replays the *actual* C command stream and scene descriptors. This catches
sprite/layer priority and clipping differences; it is not a hardware result.
"""
from pathlib import Path
import json,struct,sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'TESTS'),str(ROOT/'tools')]
from test_gpu_v1 import Model,signed16
import gpu_compose
def check(prefix):
 p=Path(prefix);meta=json.loads(p.with_suffix('.json').read_text());memory=bytearray(p.with_suffix('.memory').read_bytes());commands=np.frombuffer(p.with_suffix('.commands').read_bytes(),'<u4').reshape(-1,8)
 model=Model.__new__(Model);model.memory=memory;model.commands=[];model.at=lambda addr:addr-0x800000
 for row in commands:
  c=list(map(int,row));op=c[0]>>24
  if op==22:model.target(c[3]>>16,c[3]&65535,c[4]>>16,c[4]&65535,c[1],c[2])
  elif op==28:model.clear(c[1],c[2],c[3],signed16(c[4]>>16),signed16(c[4]),c[5]>>16,c[5]&65535)
  elif op==29:model.copy(c[1],c[2]>>16,c[2]&65535,c[3],signed16(c[4]>>16),signed16(c[4]),signed16(c[5]>>16),signed16(c[5]),c[6]>>16,c[6]&65535)
  else:raise AssertionError(f'Unmodeled GPU opcode {op}')
 width,height=meta['width'],meta['height'];desc=struct.unpack('<392I',p.with_suffix('.scene').read_bytes());assert desc[2]==7
 raw=np.ndarray((height//2,width//2),'<u2',buffer=memory,offset=desc[0]-0x800000,strides=(desc[1],2));pixels=np.repeat(np.repeat(raw,2,axis=0),2,axis=1).copy()
 gpu_compose.W=width;gpu_compose.H=height
 layers=[desc[i:i+8] for i in range(8,136,8)];sprites=[desc[i:i+4] for i in range(136,392,4)]
 assert all(not (layer[6]&1) for layer in layers[12:]),"R17 text-reserved layers"
 assert all(((sprite[2]>>20)&15)<12 for sprite in sprites if sprite[2]&(1<<16)),"R17 text-reserved sprite priority"
 def read(addr,n):
  assert addr>=0x800000 and addr-0x800000+n<=len(memory),(hex(addr),n)
  return memory[addr-0x800000:addr-0x800000+n]
 indices=np.frombuffer(gpu_compose.compose(layers,sprites,read),np.uint8).reshape(height,width)
 palette=np.frombuffer(memory,'<u4',count=256,offset=meta['palette_offset']);assert np.all(palette[240:]==0),'Linux palette slots overwritten'
 rgb565=((((palette>>12)&63)*31//63)<<11)|(((palette>>6)&63)<<5)|((palette&63)*31//63)
 assert np.all(indices<240),'Application references a reserved Linux text color'
 pixels[indices!=0]=rgb565[indices[indices!=0]]
 rgb=np.stack(((pixels>>11)*255//31,((pixels>>5)&63)*255//63,(pixels&31)*255//31),axis=-1).astype(np.uint8)
 actual=np.asarray(Image.open(p.with_suffix('.ppm')).convert('RGB'));mismatches=int(np.any(rgb!=actual,axis=2).sum())
 assert mismatches==0,f'{prefix}: {mismatches} pixels differ from independent GPU model'
 print(f'LUMA_REFERENCE_PASS {width}x{height} pixels={width*height} commands={len(commands)} sprites={meta["sprites"]}')
if __name__=='__main__':
 for arg in sys.argv[1:]:check(arg)

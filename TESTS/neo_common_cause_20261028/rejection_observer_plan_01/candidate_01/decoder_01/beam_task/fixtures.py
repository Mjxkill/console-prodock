"""Explicit 640-bit synthetic records; not hardware evidence."""
import copy
from rjc_decode import VG_SHA,FW_SHA
POSITIONS={'tag1':(320,32),'target_base':(352,32),'stride':(384,16),'width':(400,16),'height':(416,16),'src_end':(432,33),'dst_end':(465,33),'parent_state':(498,58),'check_state':(556,5),'child_bad_state':(561,5),'descriptor_d':(566,3),'descriptor_q':(569,3),'word_difference':(572,8),'flags':(580,13),'reason':(593,3),'command_generation':(596,16),'check_generation':(612,16),'live':(628,12)}
def pair(kind='child'):
 tag=(0x4a31<<16)|1
 packet=[0x1d000000,0x12000100,1,32,0,0,0,0]
 f={'tag1':tag,'target_base':0x12000020,'stride':32,'width':16,'height':1,'src_end':0x12000120,'dst_end':0x12000040,'parent_state':1<<42,'check_state':1,'child_bad_state':17,'descriptor_d':1,'descriptor_q':1,'word_difference':4,'flags':1|2|4|8|16|32|128|512|2048,'reason':3,'command_generation':2,'check_generation':2,'live':(1<<6)|(1<<7)}
 if kind!='child':
  f.update(check_state=0,child_bad_state=0,descriptor_d=0,descriptor_q=0,word_difference=0,check_generation=0,flags=1|2|32|128,parent_state=1<<45,live=0)
  if kind=='header': packet[0]=0x1d000001;f.update(reason=1,flags=1|2|32|64)
  elif kind=='target':f.update(reason=2,flags=1|2|32)
  elif kind=='manual':f.update(reason=0,flags=1|128,parent_state=1<<33,live=1<<10)
  elif kind=='parent_other':packet[0]=0x1c000000;f.update(reason=5)
  elif kind=='child_other':f.update(reason=4,parent_state=1<<42,live=(1<<6)|(1<<7))
  else:raise ValueError(kind)
 v=sum(w<<(32*i) for i,w in enumerate(packet))|(tag<<256)|(packet[0]<<288)
 for key,x in f.items():lo,width=POSITIONS[key];v|=x<<lo
 return [[(v>>(32*i))&0xffffffff for i in range(10)],[(v>>(320+32*i))&0xffffffff for i in range(10)]]
def mutate_pair(banks,field,value):
 a,b=copy.deepcopy(banks);v=sum(w<<(32*i) for i,w in enumerate(a+b));lo,width=POSITIONS[field];v=(v&~(((1<<width)-1)<<lo))|(value<<lo)
 return [[(v>>(32*i))&0xffffffff for i in range(10)],[(v>>(320+32*i))&0xffffffff for i in range(10)]]
def capture(kind='child'):
 a,b=pair(kind)
 def reading(words,seq):return {'sequence_before':seq,'status_before':6,'words':words,'sequence_after':seq,'status_after':6}
 r={'gpu':reading(a,12),'scan':reading(b,21)}
 return {'schema':'RJC1_CAPTURE_1','candidate_vg_sha256':VG_SHA,'firmware_sha256':FW_SHA,'arm_before':0,'arm_after':1,'sequences_before':{'gpu':10,'scan':20},'prime':{'discarded':True,'gpu_sequence_after':11},'rounds':[copy.deepcopy(r),copy.deepcopy(r)]}

"""Independent journal fixtures: incomplete reads never imply unchanged DDR."""
import json
import struct
from decode_copy import BASE,EXPECTED,SEED,decode

def fixture():
    w=[0]*128
    w[:7]=[0x4d443132,1,10,1,0,0,0xa0000001]
    w[8]=0x1800;w[17:21]=[0x424c5432,0,1,2]
    w[24:26]=[1,BASE+124];w[28:31]=[32]*3
    w[32:64]=SEED;w[64:96]=SEED;w[96:128]=EXPECTED
    return w

def encoded(w):return struct.pack('<128I',*w)

def main():
    results=[]
    w=fixture();assert decode(encoded(w))['copy_test_passed'];results.append('healthy')
    for name,index,value in [('wrong_done',20,1),('cache',4,2),('lost',22,1),
                             ('reserved',26,1),('extent',25,BASE),('packetcounter',24,0),
                             ('count',30,31),('comparison',16,1),('canary',127,123)]:
        w=fixture();w[index]=value;assert not decode(encoded(w))['copy_test_passed'];results.append(name)
    w=fixture();w[2:4]=[8,0xfffffffb];w[30]=0;w[96:]=[0]*32
    r=decode(encoded(w));assert not r['copy_test_passed'] and r['classification']=='unobserved';results.append('timeout_no_memory_inference')
    w=fixture();w[2:4]=[9,0xfffffffa];w[96:]=SEED;w[13:17]=[BASE+32,EXPECTED[8],SEED[8],8]
    r=decode(encoded(w));assert not r['copy_test_passed'] and r['classification']=='seed_unchanged' and 'comparison_metadata' not in r['issues'];results.append('completed_seed_unchanged')
    for name,data in [('short',bytes(511)),('wrong_identity',bytes(512))]:
        try:decode(data)
        except ValueError:results.append(name)
        else:raise AssertionError(name)
    print(json.dumps({'passed':True,'cases':results}))

if __name__=='__main__':main()

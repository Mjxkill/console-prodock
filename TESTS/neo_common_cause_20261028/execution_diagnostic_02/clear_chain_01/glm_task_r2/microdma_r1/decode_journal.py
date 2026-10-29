#!/usr/bin/env python3
"""Decode the512B CPU journal; never trust a success flag without its images."""
import argparse
import json
from pathlib import Path
import struct

NAMES=('magic','version','phase','result','cache_before','cache_after','milmb',
       'old_mtvec','old_mstatus','old_mie','mcause','mtval','mepc','first_bad_address',
       'first_expected','first_actual','error_count','gpu_identity','done_before',
       'done_target','done_clear','gpu_errors','queue_lost','v1_rejected',
       'command_words_remaining','last_ddr_address','reserved26','reserved27',
       'seed_compared_words','target_compared_words','clear_compared_words','reserved31')
RESULTS={1:'complete',0:'incomplete',-1:'guard',-2:'cpu_seed',-3:'target_wait_or_error',
         -4:'target_changed_memory',-5:'clear_wait_or_error',-6:'clear_memory',
         -7:'trap',-9:'command_fifo_timeout'}

def decode(data):
    if len(data)!=512:raise ValueError('Expected exactly512bytes, no partial PASS')
    words=list(struct.unpack('<128I',data))
    if words[:2]!=[0x4d443132,1]:raise ValueError('Wrong journal identity/version')
    result=words[3] if words[3]<0x80000000 else words[3]-0x100000000
    header=dict(zip(NAMES,words[:32]));header['result']=result
    issues=[]
    if result!=1:issues.append(RESULTS.get(result,'unknown_result'))
    if words[2]!=10:issues.append('not_final_phase')
    expected=[(0x12000000+4*i)^0xa5396c17 for i in range(32)]
    clear=expected[:8]+[0x6b4d6b4d]*8+expected[16:]
    for label,image,wanted in [('seed',words[32:64],expected),('target',words[64:96],expected),
                               ('clear',words[96:128],clear)]:
        if image!=wanted:issues.append(label+'_image_mismatch')
    if words[4:7]!=[0,0,0xa0000001]:issues.append('cache_or_ilm_guard')
    if words[8]&8 or words[9]:issues.append('interrupt_guard')
    if words[10:17]!=[0]*7:issues.append('trap_or_memory_error_recorded')
    if words[17:24]!=[0x424c5432,0,1,2,0,0,0]:issues.append('gpu_counters')
    if words[28:31]!=[32,32,32]:issues.append('incomplete_cpu_images')
    return dict(passed=not issues,header=header,issues=issues,
                images={'seed':words[32:64],'target':words[64:96],'clear':words[96:128]},
                limit='Journal consistency only; caller supplies exact bitstream/binary/board provenance.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('journal',type=Path)
    args=parser.parse_args();result=decode(args.journal.read_bytes())
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)

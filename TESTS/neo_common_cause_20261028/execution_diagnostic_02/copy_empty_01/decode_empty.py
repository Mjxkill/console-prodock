#!/usr/bin/env python3
"""Decode only reviewed empty-COPY MD12; the controller supplies firmware SHA."""
import argparse
import json
from pathlib import Path
import struct

BASE=0x12000000
SEED=[(BASE+4*i)^0xa5396c17 for i in range(32)]
EXPECTED=SEED
FIRMWARE_SHA256="0e9b249f276a9c660bebf2a74774b7930cdaa02bb9fbfffc01136d7f0eb8bbc7"

def decode(data, *, firmware_sha256):
    if firmware_sha256!=FIRMWARE_SHA256:raise ValueError("Wrong empty-COPY firmware provenance")
    if len(data)!=512:raise ValueError('Expected exact512B MD12 journal')
    words=list(struct.unpack('<128I',data))
    if words[:2]!=[0x4d443132,1]:raise ValueError('Wrong MD12 identity/version')
    result=words[3] if words[3]<0x80000000 else words[3]-0x100000000
    complete=words[2:4]==[10,1]
    issues=[]
    if not complete:issues.append('payload_not_complete_success')
    if words[4:7]!=[0,0,0xa0000001] or words[8]&8 or words[9]:issues.append('guard_metadata')
    if any(words[10:13]):issues.append('trap_recorded')
    if words[17]!=0x424c5432:issues.append('gpu_identity')
    if words[18:21]!=[0,1,2]:issues.append('gpu_done_sequence')
    if any(words[21:24]):issues.append('gpu_error_counters')
    if words[24]!=1 or words[25]!=BASE+124:issues.append('packet_or_extent_metadata')
    if any(words[26:28]) or words[31]:issues.append('reserved_metadata')
    if words[28:31]!=[32,32,32]:issues.append('incomplete_cpu_comparisons')
    images=[words[32:64],words[64:96],words[96:128]]
    if words[28]==32 and images[0]!=SEED:issues.append('seed_image')
    if words[29]==32 and images[1]!=SEED:issues.append('target_touched_memory')
    final_read_complete=words[30]==32 and words[2] in (9,10)
    classification='unobserved'
    if final_read_complete:
        final=images[2]
        changed=[i for i,(a,b) in enumerate(zip(final,EXPECTED)) if a!=b]
        first=changed[0] if changed else None
        mismatch=[0,0,0] if first is None else [BASE+4*first,EXPECTED[first],final[first]]
        if words[13:16]!=mismatch or words[16]!=len(changed):issues.append('comparison_metadata')
        if final==EXPECTED:classification='seed_unchanged'
        else:classification='other_or_partial_change'
        if changed:issues.append('empty_copy_modified_memory')
    return {'empty_copy_test_passed':complete and not issues,'classification':classification,
            'phase':words[2],'cpu_result':result,'issues':issues,
            'compared_counts':words[28:31],'done_counts':words[18:21],
            'images':images,'scope':'Bounded empty COPY control; CPU comparisons only, no global GPU/DDR qualification.',
            'provenance':'Caller must bind this journal to the reviewed COPY firmware SHA; MD12 alone does not identify the operation.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('journal',type=Path);p.add_argument('--firmware-sha256',required=True)
    a=p.parse_args();r=decode(a.journal.read_bytes(),firmware_sha256=a.firmware_sha256);print(json.dumps(r,indent=2))
    raise SystemExit(not r['empty_copy_test_passed'])

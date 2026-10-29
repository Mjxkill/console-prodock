#!/usr/bin/env python3
"""Decode the reviewed MD13 sequence only, bound to its exact firmware bytes."""
import argparse
import json
from pathlib import Path
import struct

FIRMWARE_SHA256='5171a15d524722faf19b4cf3bc9fa7c2cf6327cc7654fe06c998cce1a5c06fff'
BASE=0x12000000
SEED=[(BASE+4*i)^0xa5396c17 for i in range(32)]


def decode(data,*,firmware_sha256):
    if firmware_sha256!=FIRMWARE_SHA256:raise ValueError('Wrong sequence firmware provenance')
    if len(data)!=512:raise ValueError('Expected exact512B MD13 journal')
    w=list(struct.unpack('<128I',data))
    if w[:2]!=[0x4d443133,1]:raise ValueError('Wrong MD13 identity/version')
    result=w[3] if w[3]<0x80000000 else w[3]-0x100000000
    phase=w[2];complete=(phase==12 and result==1)
    issues=[]
    if not complete:issues.append('payload_not_complete_success')
    if w[4:7]!=[0,0,0xa0000001] or w[8]&8 or w[9]:issues.append('guard_metadata')
    if any(w[10:13]):issues.append('trap_recorded')
    if w[17]!=0x424c5432:issues.append('gpu_identity')
    if w[18:21]!=[0,1,3]:issues.append('gpu_done_sequence')
    if any(w[21:24]):issues.append('gpu_error_counters')
    if w[26:28]!=[2,0]:issues.append('clear_control_not_passed')
    if w[24]!=1 or w[25]!=BASE+124:issues.append('packet_or_extent_metadata')
    if w[31]:issues.append('reserved_metadata')
    if w[28:31]!=[32,32,32]:issues.append('incomplete_cpu_comparisons')
    images=[w[32:64],w[64:96],w[96:128]]
    if w[28]==32 and images[0]!=SEED:issues.append('seed_image')
    if w[29]==32 and images[1]!=SEED:issues.append('target_touched_memory')
    final_complete=w[30]==32 and phase in (11,12)
    classification='unobserved'
    if final_complete:
        changed=[i for i,(a,b) in enumerate(zip(images[2],SEED)) if a!=b]
        first=changed[0] if changed else None
        mismatch=[0,0,0] if first is None else [BASE+4*first,SEED[first],images[2][first]]
        if w[13:16]!=mismatch or w[16]!=len(changed):issues.append('comparison_metadata')
        classification='other_or_partial_change' if changed else 'seed_unchanged'
        if changed:issues.append('no_op_sequence_modified_memory')
    # These are firmware observations, not directly observed internal target_valid.
    clear_passed=phase in (9,10,11,12) and w[26:28]==[2,0]
    observation='incomplete_or_other_failure'
    if phase==8 and result==-8 and w[26:28]==[2,1]:observation='clear_control_completed_rejected'
    if phase==10 and result==-5 and clear_passed and w[20]==3 and w[23]==1:
        observation='clear_control_passed_copy_completed_rejected'
    if complete and not issues:observation='sequence_completed_without_rejection'
    return dict(sequence_test_passed=complete and not issues,phase=phase,cpu_result=result,
      observation=observation,clear_control_passed=clear_passed,classification=classification,
      issues=issues,done_counts=dict(initial=w[18],target=w[19],clear=w[26],copy=w[20]),
      clear_rejected=w[27],final_rejected=w[23],compared_counts=w[28:31],images=images,
      scope='MD13 bounded TARGET/CLEAR0/COPY0 control; no global GPU or DDR qualification.',
      provenance='SHA binding is required; controller must independently attest fresh execution and restoration.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('journal',type=Path);p.add_argument('--firmware-sha256',required=True)
    a=p.parse_args();r=decode(a.journal.read_bytes(),firmware_sha256=a.firmware_sha256)
    print(json.dumps(r,indent=2));raise SystemExit(not r['sequence_test_passed'])

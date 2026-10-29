#!/usr/bin/env python3
"""Hardened OWNED candidate decoder for the 512B MD12 CPU journal (decode v2).

The protected original microdma_r1/decode_journal.py is unchanged.  The
reviewer confirmed its useful defect: it never inspects reserved26/27 (words
26/27), reserved31 (word 31) or last_ddr_address (word 25), and it accepts any
command_words_remaining (word 24) value on a completion claim.  Those fields
must match the healthy completed payload, so this candidate adds exactly those
bounded checks -- nothing else differs from the original ABI.

Reviewer correction adopted here (and against my own earlier wrong inference):
microdma.S stores command_words_remaining immediately BEFORE each command word
and never clears it afterwards, so the final journaled value is 1 even after
all 8 stores return.  My earlier fixture assumed 0 ("all consumed") -- that
inference is rejected; the payload is never edited to match a mistaken test.
Direct corroboration from the protected artifacts: the real run02/run03
512B journals carry words[24:32] = [1, 0x1200007c, 0, 0, 32, 32, 0, 0].

Bounded v2 checks:
  * words 26/27/31 must be zero in any well-formed journal (format integrity).
  * On a completed phase10/result1 claim word 24 must be exactly 1 and word 25
    exactly 0x1200007c (the last of the 32 compared DDR words at
    0x12000000+4*31).  The gate follows the reviewer's stated scope, so partial
    journals gain no invented issues; both real journals already satisfy the
    format words and stay FAIL for their genuine reasons.
All other behavior (identity check, header checks, image comparison, issue
labels, returned keys) matches the original module exactly.
"""
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

# Healthy-payload expectations for the words the original decoder ignores.
RESERVED_WORDS = (26, 27, 31)          # reserved words must always be zero
COMMAND_WORDS_REMAINING_DONE = 1      # microdma.S never clears it after the stores
LAST_DDR_ADDRESS_DONE = 0x1200007c    # 0x12000000 + 4*31: final compared DDR word


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
    # ---- bounded additions: v2 only; the protected original decode() ends here ----
    # Reserved words must be zero in every well-formed journal.
    if any(words[i] for i in RESERVED_WORDS):
        issues.append('reserved_words_nonzero')
    # On a completed phase10/result1 claim the formerly unchecked extent fields
    # must match the healthy payload exactly.
    if words[2]==10 and result==1:
        if words[24]!=COMMAND_WORDS_REMAINING_DONE:
            issues.append('command_words_remaining_not_one')
        if words[25]!=LAST_DDR_ADDRESS_DONE:
            issues.append('last_ddr_address_wrong_extent')
    return dict(passed=not issues,header=header,issues=issues,
                images={'seed':words[32:64],'target':words[64:96],'clear':words[96:128]},
                limit='Journal consistency plus bounded reserved/extent checks; '
                      'caller supplies exact bitstream/binary/board provenance.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('journal',type=Path)
    args=parser.parse_args();result=decode(args.journal.read_bytes())
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
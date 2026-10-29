#!/usr/bin/env python3
"""Strict RJC1 decoding. A coherent register decision is not a physical cause.

This module has no transport, subprocess, device, network or write operation.
The collector must separately establish bitstream identity and fresh execution.
"""
import argparse
import json
from pathlib import Path

VG_SHA = '63643b24d07d549d13feff4d3f532d79dedf31669466b98c62e86c617f3a6f15'
FW_SHA = '39484a6b2068dc48f176b3c397eee2551801cbda86936a5d0b38532a208f0663'
MAGIC = 0x4A31
MASK32 = (1 << 32) - 1
OFFSETS = (0x20,0x24,0x28,0x2c,0x30,0x34,0x38,0x3c,0x10,0x14)
FIELDS = {'tag1':(320,32),'target_base':(352,32),'stride':(384,16),
          'width':(400,16),'height':(416,16),'src_end':(432,33),'dst_end':(465,33),
          'parent_state':(498,58),'check_state':(556,5),'child_bad_state':(561,5),
          'descriptor_d':(566,3),'descriptor_q':(569,3),'word_difference':(572,8),
          'flags':(580,13),'reason':(593,3),'command_generation':(596,16),
          'check_generation':(612,16),'live':(628,12)}
FLAG_NAMES = ('valid','rejected','packet_child','associated','q_valid','parent_q',
              'bad_header','target_valid','reset_seen','check_seen','anomaly',
              'child_bad_seen','dq_error')
REASONS = ('NONE','HEADER','TARGET','CHILD_VALIDATE','CHILD_OTHER','PARENT_OTHER',
           'CAPTURE_INCONSISTENT','RESERVED')


class InvalidCapture(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidCapture(message)


def uint(value, bits, name):
    require(type(value) is int and 0 <= value < (1 << bits), 'invalid integer: '+name)
    return value


def keys(value, expected, name):
    require(type(value) is dict and set(value) == set(expected), 'schema: '+name)


def bank(value, name):
    require(type(value) is list and len(value) == 10, 'bank length: '+name)
    return [uint(v,32,name+' word') for v in value]


def copy_predicates(packet, target_base, target_stride, src_end, dst_end):
    """Recompute source predicates using the captured arithmetic outputs as inputs.

    A mismatch with actual D/Q is reported, not silently replaced by this oracle.
    """
    w1,w2,w3,w7 = packet[1],packet[2],packet[3],packet[7]
    width,height,stride = w2 >> 16,w2 & 65535,w3 & 65535
    overlap = w1 < dst_end and target_base < src_end
    groups = [
        {'source_high_address':w1>>30 != 0,'source_alignment':w1&31 != 0,
         'width_zero':width==0,'width_too_large':width>1024},
        {'height_zero':height==0,'height_too_large':height>512,
         'stride_high_word':w3>>16 != 0,'stride_alignment':w3&31 != 0,
         'stride_too_small':stride<2*width},
        {'source_end_overflow':src_end>0x40000000,'reserved_word7':w7!=0,
         'overlap_other_layout':overlap and (w1!=target_base or stride!=target_stride)},
    ]
    bits = sum(int(any(g.values())) << i for i,g in enumerate(groups))
    return {'recomputed_bits':bits,'conditions':groups,'overlap':overlap,
            'source_end_arithmetic_expected':w1+stride*height}


def decode_record(gpu_words, scan_words, *, expected_epoch):
    """Decode a *final* coherent pair. Use decode_capture for freshness checks."""
    gpu,scan = bank(gpu_words,'gpu'),bank(scan_words,'scan')
    epoch=uint(expected_epoch,16,'expected_epoch')
    require(epoch!=0,'zero expected epoch')
    value=sum(word << (32*i) for i,word in enumerate(gpu+scan))
    fields={name:(value>>lo)&((1<<width)-1) for name,(lo,width) in FIELDS.items()}
    tag0=(value>>256)&MASK32
    require(tag0==fields['tag1']==(MAGIC<<16)|epoch,'bank tag mismatch/stale epoch')
    flags={name:bool(fields['flags']&(1<<i)) for i,name in enumerate(FLAG_NAMES)}
    reason=fields['reason'];state=fields['parent_state'];live=fields['live']
    packet=gpu[:8];parent_w0=gpu[9]
    require(flags['valid'],'record not finalized')
    require(not any(flags[n] for n in ('reset_seen','anomaly','dq_error')),
            'capture reset/anomaly/overflow/DQ error')
    require(not(live&(1<<11)),'freeze pending')
    require(not(live&0x300),'engine reset at decision')
    require(state!=0 and (state&(state-1))==0,'parent state not one-hot')
    require(fields['command_generation']!=0,'missing command generation')
    require(fields['target_base']<0x40000000,'impossible captured target high bits')
    require(reason<6,'inconsistent/reserved reason')
    group=[flags[n] for n in ('packet_child','associated','q_valid','check_seen')]
    require(all(group) or not any(group),'partial CHECK association')
    associated=all(group)
    if associated:
        require(state==1<<42,'CHECK attached outside COPY_WAIT')
        require(fields['check_state']==1,'wrong raw CHECK state')
        require(fields['check_generation']==fields['command_generation'],
                'CHECK belongs to another command')
        require(fields['descriptor_d']==fields['descriptor_q'],'descriptor D/Q mismatch')
    else:
        require(all(fields[n]==0 for n in ('check_state','descriptor_d','descriptor_q',
                                           'word_difference','check_generation')),
                'stale CHECK fields without association')
        require(packet[0]==parent_w0,'parent packet/header mismatch')
    if not flags['rejected']:
        require(reason==0 and bool(live&(1<<10)) and not flags['parent_q'],
                'manual freeze/rejection mismatch')
        require(not associated and not flags['child_bad_seen'],'manual stale child evidence')
        require(state!=1,'idle manual freeze forbidden')
        stage='MANUAL_NO_REJECTION'
    else:
        require(flags['parent_q'] and not(live&(1<<10)) and reason!=0,
                'rejection is not confirmed')
        if state==1<<45 and flags['bad_header']:
            expected_reason=1
        elif state==1<<45 and parent_w0>>24==0x1d and not flags['target_valid']:
            expected_reason=2
        elif state==1<<42 and (live&(1<<6)) and (live&(1<<7)):
            expected_reason=3 if (associated and flags['child_bad_seen'] and
                fields['child_bad_state']==17 and fields['descriptor_q']!=0) else 4
        else:
            expected_reason=5
        require(reason==expected_reason,'reason contradicts captured decision evidence')
        stage=REASONS[reason]
    predicates=None
    if associated:
        predicates=copy_predicates(packet,fields['target_base'],fields['stride'],
                                   fields['src_end'],fields['dst_end'])
        predicates['matches_actual_D']=predicates['recomputed_bits']==fields['descriptor_d']
        predicates['source_end_matches_arithmetic']=(predicates['source_end_arithmetic_expected']==fields['src_end'])
        predicates['destination_end_matches_arithmetic']=(fields['target_base']+
            fields['stride']*fields['height']==fields['dst_end'])
    return {'format':'RJC1','epoch':epoch,'coherent_record':True,'decision_stage':stage,
            'packet_provenance':'COPY_AT_CHECK' if associated else 'PARENT_AT_FREEZE',
            'packet':packet,'parent_w0':parent_w0,'fields':fields,'flags':flags,
            'predicates':predicates,'freshness_established':False,
            'physical_cause_established':False,'gpu_or_ddr_qualified':False,
            'scope':'Register decision evidence only; collection and timing qualification required.'}


def _read(reading, name, sequence):
    keys(reading,('sequence_before','status_before','words','sequence_after','status_after'),name)
    require(uint(reading['sequence_before'],32,name+' sequence before')==sequence and
            uint(reading['sequence_after'],32,name+' sequence after')==sequence,
            'transport sequence changed: '+name)
    require(uint(reading['status_before'],32,name+' status')==6 and
            uint(reading['status_after'],32,name+' status')==6,'transport not ready: '+name)
    return bank(reading['words'],name)


def decode_capture(capture):
    """Verify a protocol transcript, not the truth of a caller's hardware claims."""
    keys(capture,('schema','candidate_vg_sha256','firmware_sha256','arm_before','arm_after',
                  'sequences_before','prime','rounds'),'capture')
    require(capture['schema']=='RJC1_CAPTURE_1','capture version')
    require(capture['candidate_vg_sha256']==VG_SHA,'wrong candidate netlist')
    require(capture['firmware_sha256']==FW_SHA,'wrong stimulus firmware')
    before=uint(capture['arm_before'],32,'arm before');after=uint(capture['arm_after'],32,'arm after')
    require(before<65535 and after==before+1,'ARM stale/wrapped')
    keys(capture['sequences_before'],('gpu','scan'),'sequences')
    g=uint(capture['sequences_before']['gpu'],32,'gpu initial sequence')
    s=uint(capture['sequences_before']['scan'],32,'scan initial sequence')
    require(g<=MASK32-2 and s<MASK32,'transport sequence wrap')
    keys(capture['prime'],('discarded','gpu_sequence_after'),'prime')
    require(capture['prime']['discarded'] is True and
            uint(capture['prime']['gpu_sequence_after'],32,'prime sequence')==g+1,
            'prime missing, unconsumed or not discarded')
    require(type(capture['rounds']) is list and len(capture['rounds'])==2,'two read rounds required')
    images=[]
    for i,r in enumerate(capture['rounds']):
        keys(r,('gpu','scan'),'round')
        images.append((_read(r['gpu'],'gpu round'+str(i),g+2),
                       _read(r['scan'],'scan round'+str(i),s+1)))
    require(images[0]==images[1],'two reads differ')
    result=decode_record(*images[0],expected_epoch=after)
    result['transcript_freshness_checks_passed']=True
    result['freshness_established']=False  # A file cannot attest actual I/O or SRAM identity.
    result['scope']='Coherent protocol transcript; root must attest physical execution and timing separately.'
    return result


def load_strict(path):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate JSON key')
            result[key]=value
        return result
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(InvalidCapture('non-finite JSON')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('capture',type=Path)
    args=parser.parse_args()
    try:print(json.dumps(decode_capture(load_strict(args.capture)),indent=2))
    except (InvalidCapture,ValueError,TypeError) as error:
        print(json.dumps({'accepted':False,'error':str(error),'physical_cause_established':False}));raise SystemExit(1)

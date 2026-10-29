#!/usr/bin/env python3
"""Decode R20 snapshots; label observations without inventing a root cause."""
STATE_NAMES=('IDLE BAD FINISH TARGET_CHECK TEX_CHECK TRI_START TRI_BOOT TRI_WAIT '
    'SPAN_CLIP ROW_ADDR PLANE_MUL PLANE_SUM PLANE_LOAD CHUNK COLOR_REQ COLOR_WAIT '
    'Z_REQ Z_WAIT PIX_BEGIN PIX_ADDR PIX_TEX PIX_UNPACK PIX_MOD PIX_FOG PIX_FOG_MIX '
    'PIX_BLEND PIX_STORE PIX_NEXT COLOR_WRITE COLOR_SENT Z_WRITE Z_SENT ADVANCE '
    'RECT_SETUP RECT_ROW RECT_CHUNK RECT_COLOR RECT_CSENT RECT_Z RECT_ZSENT '
    'RECT_NEXT COPY_START COPY_WAIT RECT_BOUNDS RECT_CLIP DECODE TARGET_WAIT TEX_WAIT '
    'DECODE_WAIT TARGET_VALIDATE TEX_VALIDATE SPAN_BOUNDS PIX_LOD PIX_OFFSET '
    'PIX_FETCH PIX_OPAQUE DECODE_PIPE TARGET_PIPE').split()
HANDSHAKES=('native_valid native_write v1_select v1_pending v1_accepted b_grant '
    'v1_tx_write fetch_valid pending_d pending_reset accepted_d payload_ce '
    'copy_valid cache_valid legacy_valid v1_done').split()

def decode(words):
    if len(words)!=8 or any(type(v) is not int or not 0<=v<=0xffffffff for v in words):
        raise ValueError('Expected eight unsigned snapshot words')
    if words[2]>>16!=0x4d20 or words[6]>>28!=0xa:
        raise ValueError('Not the R20 memory observation layout')
    all_state=words[4]|words[5]<<32
    state=all_state&((1<<58)-1)
    active=[n for i,n in enumerate(STATE_NAMES) if state>>i&1]
    h={n:bool(words[2]>>i&1) for i,n in enumerate(HANDSHAKES)}
    flags=words[1]
    p=dict(native_d=bool(all_state>>58&1),native_ce=bool(all_state>>59&1),
        reset=bool(all_state>>60&1),clear_flags=(all_state>>61)&3,bad_clear=bool(all_state>>63&1))
    r=dict(done=words[0]&65535,engine_resetn=flags>>12&0xfff,ext_active=bool(flags&1),
        blitter_busy=bool(flags&4),opcode=words[7]>>24,states=active,
        onehot=len(active)==1,handshakes=h,pixel_control=p,
        slot_word_address=words[6]&0xfffffff,slot_byte_address=(words[6]&0xfffffff)<<2,
        notes=[])
    if not r['onehot']:r['notes'].append('PIXEL_FSM_NOT_ONEHOT')
    if p['reset'] or h['pending_reset']:r['notes'].append('RESET_OBSERVED')
    if len(active)==1 and active[0] in ('RECT_CSENT','RECT_ZSENT'):
        r['notes'].append('PIXELS_WAIT_FOR_WRITE_ACCEPTANCE')
        if not h['native_valid'] and not h['v1_accepted']:r['notes'].append('NO_NATIVE_VALID_OR_ACCEPT_AT_SAMPLE')
        if h['v1_pending'] and not h['b_grant']:r['notes'].append('SLOT_PENDING_WITHOUT_ARBITER_READY')
    if not h['v1_pending'] and h['pending_d'] and not h['pending_reset']:
        r['notes'].append('PENDING_Q0_D1_AT_SAMPLE')
    if not h['v1_accepted'] and h['accepted_d'] and not h['pending_reset']:
        r['notes'].append('ACCEPT_Q0_D1_AT_SAMPLE')
    r['limitation']='One coherent edge; Q differing from D is normally transient. Repeated snapshots and physical path checks are needed; these labels are not causes.'
    return r

def self_test():
    def sample(state=37,hs=0,extra=0):
        v=(1<<state)|extra
        return [4,0xfffc25,0x4d200000|hs,0x28281c09,v&0xffffffff,v>>32,0xa4800000,0x1c000000]
    a=decode(sample(hs=1|4|256,extra=1<<61))
    assert a['states']==['RECT_CSENT'] and a['pixel_control']['clear_flags']==1
    assert a['slot_byte_address']==0x12000000 and a['opcode']==28
    assert 'PENDING_Q0_D1_AT_SAMPLE' in a['notes']
    assert 'SLOT_PENDING_WITHOUT_ARBITER_READY' in decode(sample(hs=9))['notes']
    assert 'ACCEPT_Q0_D1_AT_SAMPLE' in decode(sample(hs=1024))['notes']
    assert 'RESET_OBSERVED' in decode(sample(extra=1<<60))['notes']
    assert not decode(sample(state=0,extra=1<<37))['onehot']
    for value in [sample()[:7],sample()+[0],[0]*8,[None]*8]:
        try:decode(value)
        except ValueError:pass
        else:raise AssertionError('Invalid/legacy layout accepted')
    for bit,name in enumerate(STATE_NAMES):assert decode(sample(state=bit))['states']==[name]
    for bit,name in enumerate(HANDSHAKES):assert decode(sample(hs=1<<bit))['handshakes'][name]
    return dict(passed=True,states_checked=len(STATE_NAMES),handshake_bits_checked=len(HANDSHAKES),
        scope='Decoder tests and injected observation patterns; no hardware')

if __name__=='__main__':
    import json
    print(json.dumps(self_test()))

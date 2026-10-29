#!/usr/bin/env python3
"""Independent fixed-input facts; no hardware and no general RTL equivalence."""
import hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lut(c,values):
 literal=c['params']['INIT'];v=int(literal.split("'h")[1],16)
 return (v>>sum(x<<i for i,x in enumerate(values)))&1
def release_model(hold):
    # Nonblocking assignment semantics of usb_reset_release.v.
    sync,count,reset=0,0,1
    first_low=None
    for edge in range(1,hold+4):
        old_sync=sync; sync=((sync&1)<<1)|1
        if not (old_sync&2):count,reset=0,1
        elif reset:
            if count==hold-1:reset=0
            else:count+=1
        if reset==0 and first_low is None:first_low=edge
    assert first_low==hold+2
    # A lock falling event clears state without any rising clock event.
    sync,count,reset=0,0,1
    assert (sync,count,reset)==(0,0,1)
    return first_low
model_cases={str(n):release_model(n) for n in [1,2,64,104000]}
results={}
for b in ['g22','r5']:
 ctx=P/'deepseek/task/context';c=json.loads((ctx/f'{b}_cone.json').read_text())['cells']
 critical=json.loads((ctx/'critical_cells.json').read_text())[b]
 tb=critical['\\u_usb_softphy_top/usb_pullup_en_o_s1'];drivers={v['ports']['F']:v for v in c.values() if v['kind'].startswith('LUT')}
 table=[]
 for rst in (0,1):
  for phy in (0,1):
   for term in (0,1):
    def resolve(net):
     if net in {'rst_usb':rst,'PHY_RESET':phy,'PHY_TERMSELECT':term}:return {'rst_usb':rst,'PHY_RESET':phy,'PHY_TERMSELECT':term}[net]
     cell=drivers[net];n=int(cell['kind'][3:]);return lut(cell,[resolve(cell['ports'][f'I{i}']) for i in range(n)])
    data,oe=resolve(tb['ports']['I']),resolve(tb['ports']['OEN'])
    actual='Z' if oe else data;r=rst|phy;expected=0 if r else (1 if term else 'Z')
    assert actual==expected
    table.append({'rst_usb':rst,'PHY_RESET':phy,'TERMSELECT':term,'M19':actual})
 pins=(ctx/f'{b}_pins.cst').read_text();assert re.search(r'IO_LOC\s+"ae350_tx_pin"\s+H15;',pins)
 top=(ctx/f'{b}_top.v').read_text();assert "assign ae350_tx_pin = ae350_tx;" in top
 seq=(ctx/f'{b}_reset.v').read_text();assert 'posedge clk or negedge locked' in seq
 results[b]={'pullup_table':table,'uart_pin':'H15','uart_comment_F19_is_stale':True,'reset_logic_asserts_without_clock':True,'release_cycles_after_lock_rise':{'ref_start':104002,'phy_start':104002,'controller_start':66},'release_time_given_nominal_clock_seconds':{'ref_start':104002/50e6,'phy_start':104002/50e6,'controller_start':66/60e6}}
# This proves exact connectivity/formulas only; no measured frequency/lock.
report={'hardware':False,'logical_reset_model_cases':model_cases,'proved':results,'limits':['Nominal frequencies and synchronizer delays are logical expectations, not observed clocks.','No complete internal encrypted PHY/calibration state machine equivalence.','An asserted reset drives M19 low; a low M19 alone cannot distinguish all internal reset/clock causes.','GPIO LED optical interpretation requires board revision/polarity verification.'],'inputs':{str(f.relative_to(P)):sha(f) for f in (P/'deepseek/task/context').glob('*') if f.is_file()},'official_tbuf_model':'/home/michael/gowin/IDE/simlib/gw5a/prim_sim.v:839 bufif0'}
(P/'owner_review/result.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS 16 pull-up truth cases, two actual UART pin mappings, reset source contract. No hardware inference.')

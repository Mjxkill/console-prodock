#!/usr/bin/env python3
"""Bounded interface-only regression; production failures remain explicit.

All outputs stay in a fresh subdirectory. Does not edit the candidate, patch,
manifest, production, hardware, or other agents' files.
"""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[2]
T=Path('/tmp/console-usb-sim-tools/extracted/usr')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();o=a.out.resolve();o.relative_to(C);o.mkdir(parents=True,exist_ok=False)
    candidate=C/'usb_fifo.v';production=R/'tang/rtl/usb/sync_fifo/usb_fifo.v';bench=C/'ep1_flush_interfaces_tb.sv'
    assert sha(candidate)=='6ef935c83948689456397f7b2bb1f2c36b3ee38a0202be4f3aae84451332f476'
    assert sha(production)=='ad5bc3378a7266b6e40e327210d85166aeedb01d080901a66b00ae3e01660307'
    # No hierarchical references even for diagnostics/coverage; signal values
    # and expected packet bytes are observed solely at the public ports.
    source=bench.read_text();assert not re.search(r'\bdut\s*\.',source)
    code=re.sub(r'//[^\n]*','',source);assert not re.search(r'\b(force|release|deposit)\b',code)
    dependencies=[R/'tang/rtl/usb/sync_fifo/sync_tx_pkt_fifo.v',R/'tang/rtl/usb/sync_fifo/sync_rx_pkt_fifo.v']
    inputs=[Path(__file__).resolve(),bench,candidate,production,*dependencies]
    frozen={str(x.relative_to(R)):sha(x) for x in inputs}
    report=dict(passed=False,hardware=False,inputs=frozen,compiles=[],cases=[],scope='Synchronous application/controller interfaces of actual EP1/EP2 FIFOs, no internal force or PHY model',limits=['No metastability/physical CDC, analogue PHY or cable qualification.','ACK/POP are kept on their original endpoint; idle EP2 strobes are deliberately not invented.','Coincident ACK+POP on EP2 occurs only after the complete advertised payload was consumed.','Expected production defects remain recorded as failing simulations.'])
    def save():
        (o/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def compile_one(label,path):
        vvp=o/(label+'.vvp');cmd=[T/'bin/iverilog','-B',T/'lib/x86_64-linux-gnu/ivl','-g2012','-Wall','-s','ep1_flush_interfaces_tb','-o',vvp,bench,path,*dependencies]
        q=subprocess.run(list(map(str,cmd)),capture_output=True,timeout=60);log=o/(label+'.compile.log');log.write_bytes(q.stdout+q.stderr)
        report['compiles'].append(dict(name=label,source_sha256=sha(path),exit_code=q.returncode,log=log.name,sha256=sha(log),command=list(map(str,cmd))));save();q.check_returncode();return vvp
    def run_one(label,image,config,expected_failure=None):
        cmd=[str(T/'bin/vvp'),str(image),*[f'+{k}={v}' for k,v in config.items()]]
        q=subprocess.run(cmd,capture_output=True,timeout=15);raw=q.stdout+q.stderr;log=o/(label+'.log');log.write_bytes(raw)
        if expected_failure:ok=q.returncode!=0 and expected_failure.encode() in raw and b'INTERFACE_PASS' not in raw
        else:ok=q.returncode==0 and len(re.findall(rb'^INTERFACE_PASS ',raw,re.M))==1
        counters={k.decode():int(v) for k,v in re.findall(rb'(checks|bytes|packets)=(\d+)',raw)}
        report['cases'].append(dict(name=label,config=config,exit_code=q.returncode,simulation_passed=q.returncode==0,expected_failure=expected_failure,expectation_met=ok,log=log.name,log_sha256=sha(log),counters=counters))
        save();print(('EXPECTED_FAIL ' if expected_failure and ok else 'PASS ' if ok else 'FAIL ')+label,flush=True)
        return ok
    try:
        old=compile_one('production',production);new=compile_one('candidate',candidate);ok=True
        for ep in (0,1,2):
            for cycles in (1,2,64):
                cfg=dict(FLUSH_ENDPOINT=ep,FLUSH_CYCLES=cycles,TXACT=0,EVENT=0,BASIC=1)
                ok=run_one(f'production_ep{ep}_c{cycles}',old,cfg,None if ep==1 else 'STALE_EP1_AFTER_FLUSH_OR_ACK') and ok
        for ep in (0,1,2):
            for cycles in (1,2,64):
                for active in (0,1):
                    for event in range(4):
                        if ep==2 and not active and event:continue
                        cfg=dict(FLUSH_ENDPOINT=ep,FLUSH_CYCLES=cycles,TXACT=active,EVENT=event)
                        ok=run_one(f'candidate_ep{ep}_c{cycles}_a{active}_e{event}',new,cfg) and ok
        for cycles in (1,2,64):
            for active in (0,1):
                ok=run_one(f'switch_c{cycles}_a{active}',new,dict(FLUSH_ENDPOINT=2,FLUSH_CYCLES=cycles,TXACT=active,EVENT=0,SWITCH_TO_EP1=1)) and ok
        for n1 in (1,64,512):
            for n2 in (1,63):
                ok=run_one(f'boundary_ep1_{n1}_ep2_{n2}',new,dict(FLUSH_ENDPOINT=0,FLUSH_CYCLES=1,TXACT=0,EVENT=0,EP1_LENGTH=n1,EP2_LENGTH=n2)) and ok
        text=candidate.read_text();anchor="if (i_ep1_flush) begin\n            tx_pending[1] <= 1'b0;\n            tx_saved_len[1] <= 12'd0;\n        end"
        assert text.count(anchor)==1
        mutants={
          'no_pending_clear':(text.replace(anchor,'if (i_ep1_flush) begin\n            tx_saved_len[1] <= 12\'d0;\n        end'),'OFFER ep=1'),
          'clear_all_endpoints':(text.replace(anchor,anchor.replace("tx_pending[1] <= 1'b0;","tx_pending <= 0;")),'OFFER ep=2')}
        for label,(mutated,error) in mutants.items():
            path=o/(label+'.v');path.write_text(mutated);image=compile_one(label,path)
            ok=run_one('negative_'+label,image,dict(FLUSH_ENDPOINT=0,FLUSH_CYCLES=1,TXACT=0,EVENT=0),error) and ok
        report['inputs_stable']=frozen=={str(x.relative_to(R)):sha(x) for x in inputs};assert report['inputs_stable']
        report['candidate_passes']=sum(x['simulation_passed'] for x in report['cases'] if not x['name'].startswith(('production','negative')))
        report['expected_failures']=sum(bool(x['expected_failure']) and x['expectation_met'] for x in report['cases'])
        report['passed']=ok;save();assert ok,'At least one case did not meet its explicit expectation'
    finally:save()
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Check all 44 PHY FIFO Gray routes against this build's official exported VO.

Supports the generated HS3.5 Advance RX instance fifo_rx_pkt. No timing
exceptions or vendor files are changed. This is a digital connectivity and
route-delay audit, not a metastability/MTBF or analog USB qualification.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from check_usb_phy_cdc_timing import expected_paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    base=args.stage/'impl/pnr'/('console_'+args.stage.name)
    model=base.with_suffix('.vo');sdf=base.with_suffix('.sdf')
    wanted=expected_paths(model,instance_prefix='')
    found={};errors=[];timescale=None
    for line in sdf.open():
        units=re.search(r'\(TIMESCALE\s+([^)]*)\)',line)
        if units:timescale=units[1].strip()
        if 'INTERCONNECT' not in line or 'u_usb_softphy_top' not in line:continue
        line=line.replace('\\/','/').replace('\\.','.')
        match=re.search(r'INTERCONNECT (\S+) (\S+) \(([^)]+)\)',line)
        if not match:continue
        key=match[1],match[2]
        if key not in wanted:continue
        if key in found:errors.append('Duplicate route: '+key[1])
        delays=[float(v) for v in match[3].split(':')]
        if len(delays)!=3 or any(not math.isfinite(v) or v<0 or v>=1000/120 for v in delays):
            errors.append('Route outside 120 MHz period: '+key[1])
        found[key]=dict(**wanted[key],source=key[0],target=key[1],route_ns=delays)
    errors += ['Missing route: '+key[1] for key in wanted if key not in found]
    if timescale!='1 ns':errors.append('Expected SDF timescale 1 ns, found '+str(timescale))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    result=dict(passed=not errors,errors=errors,expected=44,found=len(found),
                route_bound_ns=1000/120,paths=list(found.values()),
                sha256={str(p):sha(p) for p in (model,sdf,Path(__file__),Path(__file__).with_name('check_usb_phy_cdc_timing.py'))},
                limits=__doc__)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=result['passed'],paths=len(found),
                         max_route_ns=max((max(v['route_ns']) for v in found.values()),default=None),errors=errors)))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())

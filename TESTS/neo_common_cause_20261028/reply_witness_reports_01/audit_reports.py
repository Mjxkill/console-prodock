#!/usr/bin/env python3
"""Read-only structural audit of the exact report-copy outputs, never load a board."""
import argparse
import json
from pathlib import Path
import sys
import prepare_reports as p
sys.path.insert(0,str(p.ROOT/'TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01'))
import audit_postroute as original

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
 p.check();route=json.loads((p.OUT/'route_result.json').read_text())
 p.require(route['status']=='ROUTED_NOT_QUALIFIED','route incomplete or failed')
 pnr=p.OUT/'impl/pnr';r19=p.previous.PARENT
 stable=[p.OUT/name for name in ['console_neo.vg','reports_assembly.json','postroute_expected.json','route_result.json','timing_report_requests.json']]
 stable+=[r19/'impl/pnr/console_neo.vo']+[pnr/('console_neo'+suffix) for suffix in ['.vo','.tr','.sdf','.fs','.rpt.txt']]
 stable+=[Path(__file__),Path(original.__file__)]
 hashes={str(path):p.sha(path) for path in stable}
 old,_=original.cells((r19/'impl/pnr/console_neo.vo').read_text())
 new,params=original.cells((pnr/'console_neo.vo').read_text())
 expected=json.loads((p.OUT/'postroute_expected.json').read_text())
 structure=original.check_structure(old,new,params,expected)
 timing=original.timing_inventory((pnr/'console_neo.vo').read_text(),(pnr/'console_neo.tr').read_text(),(pnr/'console_neo.sdf').read_text(),expected)
 p.require(all(p.sha(Path(path))==digest for path,digest in hashes.items()),'outputs changed during audit')
 args.out.mkdir(exist_ok=False)
 p.save(args.out/'result.json',dict(structure=structure,timing_inventory=timing,hardware_access=False,hardware_qualified=False,
  qualification='NOT_QUALIFIED',no_board_load_authorized=True,inputs=hashes,
  targeted_report_requests=str(p.OUT/'timing_report_requests.json'),
  remaining='Independently verify all 2604 query resolutions, active D/CE/RESET paths and global STA; the inventory is not a setup/hold proof.'))
 print(json.dumps(dict(structure_passed=structure['passed'],helper_ff=structure['helper_ff'],timing_complete=False,hardware_qualified=False)))
 if not structure['passed']:raise SystemExit(1)
if __name__=='__main__':main()

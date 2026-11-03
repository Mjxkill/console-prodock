#!/usr/bin/env python3
"""Pin helper qualification and graft; generate only the existing route adapter."""
import hashlib,json
from pathlib import Path
import assemble as a
HERE=Path(__file__).resolve().parent
VARIANT=a.ROOT/'TESTS/neo_copy_dma_20261101/build/route_variant.py'
VARIANT_SHA='fb15078cd9d4a557e9241bf311f1abee1a9fecb483e32569bd5616a18244e0dc'
OUT=a.ROOT/'tang/impl/console_neo_fifo_banked_20261103_r1'

def main():
 a.guards();a.need(a.sha(VARIANT)==VARIANT_SHA,'Routing adapter changed')
 q=json.loads((HERE/'QUALIFICATION.json').read_text());assembly=json.loads((HERE/'assembly_01/assembly.json').read_text())
 a.need(q['passed'] and assembly['passed'] and q['netlist_sha256']==assembly['netlist_sha256'],'Unqualified graft')
 for name,h in q['files'].items():a.need(a.sha(a.ROOT/name)==h,'Graft input changed '+name)
 a.need(not (HERE/'MAPPED_DELIVERY.json').exists() and not (HERE/'route.py').exists(),'Do not overwrite delivery')
 files=dict(q['files'])
 for p in [HERE/'QUALIFICATION.json',VARIANT,Path(__file__),HERE/'README.md',HERE/'TEST_RECORD.md',HERE/'dry_run.py']:
  files[str(p.relative_to(a.ROOT))]=a.sha(p)
 d={'status':'READY_ROOT_ROUTE_REVIEW_NOT_ROUTED','netlist_sha256':q['netlist_sha256'],
    'qualification':str((HERE/'QUALIFICATION.json').relative_to(a.ROOT)),
    'candidate_directory':str(OUT.relative_to(a.ROOT)),'files':files,'PNR':False,'hardware':False}
 a.save(HERE/'MAPPED_DELIVERY.json',d);digest=a.sha(HERE/'MAPPED_DELIVERY.json')
 entry='''#!/usr/bin/env python3
"""Two banked FF memories; frozen routing machinery, no synthesis/hardware."""
import hashlib,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SHARED=ROOT/'TESTS/neo_copy_dma_20261101/build'
if hashlib.sha256((SHARED/'route_variant.py').read_bytes()).hexdigest()!=%r:
    raise RuntimeError('Frozen routing adapter changed')
sys.path.insert(0,str(SHARED))
import route_variant as route
NET=%r
DELIVERY=%r
OUT=ROOT/%r
if __name__=='__main__':
    route.main(Path(__file__).resolve(),HERE,OUT,NET,DELIVERY)
'''%(VARIANT_SHA,q['netlist_sha256'],digest,str(OUT.relative_to(a.ROOT)))
 (HERE/'route.py').write_text(entry)
 a.save(HERE/'CANDIDATE.json',dict(experiment='NEO_TWO_COMMAND_FIFO_BANKED_FF',
  candidate_directory=str(OUT.relative_to(a.ROOT)),base='console_neo_reject_20261102_r1',
  netlist_sha256=q['netlist_sha256'],helper_sha256=a.HELP_SHA,mapped_delivery_sha256=digest,
  source_variant='banked_storage_01/banked_words32.v',legacy_engine_label='D128_COPY_DMA',
  label_note='Frozen routing engine keeps historical label; this manifest identifies the actual banked FIFO experiment.',
  PNR=False,hardware=False))
 print('ROUTE_ENTRY_PREPARED',q['netlist_sha256'],digest)
if __name__=='__main__':main()

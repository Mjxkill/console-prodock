#!/usr/bin/env python3
"""Two banked FF memories; frozen routing machinery, no synthesis/hardware."""
import hashlib,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SHARED=ROOT/'TESTS/neo_copy_dma_20261101/build'
if hashlib.sha256((SHARED/'route_variant.py').read_bytes()).hexdigest()!='fb15078cd9d4a557e9241bf311f1abee1a9fecb483e32569bd5616a18244e0dc':
    raise RuntimeError('Frozen routing adapter changed')
sys.path.insert(0,str(SHARED))
import route_variant as route
NET='9026b77de01114a52fb87edc459a48417c4eb570c4ec0945025e18a44f9f7524'
DELIVERY='def0ace9d5bcbf95509807b936baecca9ca30eb77bfd12e16f5edf8286ecdc11'
OUT=ROOT/'tang/impl/console_neo_fifo_banked_20261103_r1'
if __name__=='__main__':
    route.main(Path(__file__).resolve(),HERE,OUT,NET,DELIVERY)

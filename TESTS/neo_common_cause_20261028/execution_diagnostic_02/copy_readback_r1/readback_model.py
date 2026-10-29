"""Reuse the bounded RV32 interpreter, forbid every non-journal store.

The memory/GPU stubs exercise firmware control flow; they do not represent
the physical AE350, cache effects, DDR timing or actual arbitration.
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('readback_rv32', HERE.parent/'microdma_r1/rv32_model.py')
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)
rv.BASE = BASE = 0xa0005000
rv.JOURNAL = JOURNAL = 0xa0006400
OLD = 0xa0006000
SCRATCH = 0x12000000


class Reader(rv.RV32):
    def __init__(self, binary, scenario='copied', **kwargs):
        super().__init__(binary, **kwargs)
        self.scenario = scenario
        self.ddr_reads = []
        self.done = 1
        for address, value in [(OLD, 0x4d443132), (OLD+4, 1), (OLD+8, 8),
                               (OLD+12, 0xfffffffb), (OLD+112, 32), (OLD+116, 32)]:
            self.put(address, value)
        for i in range(32):
            address = SCRATCH+4*i
            value = address ^ 0xa5396c17
            if scenario in ('copied', 'canary', 'trap', 'partial') and 8 <= i < 16:
                if scenario != 'partial' or i < 12:
                    value = (address-32) ^ 0xa5396c17
            self.put(address, value)
        if scenario == 'canary':
            self.put(SCRATCH+64, self.word(SCRATCH+64) ^ 1)
        if scenario == 'bad_prior':
            self.put(OLD+8, 10)
        self.original_old = [self.word(OLD+4*i) for i in range(128)]

    def access(self, address, write=False, value=0):
        if write and not JOURNAL <= address < JOURNAL+256:
            raise AssertionError(f'Forbidden store {address:#x}')
        if JOURNAL+256 <= address < JOURNAL+512:
            raise AssertionError('Outside 256B journal')
        if OLD <= address < OLD+512:
            assert not write
            self.accesses.append((write, address, value))
            return self.word(address)
        if address == rv.GPU+4:
            assert not write
            self.accesses.append((write, address, value))
            return 1
        if SCRATCH <= address < SCRATCH+128:
            assert not write
            if self.scenario == 'trap' and len(self.ddr_reads) == 7:
                self.csr[0x342] = 5
                self.csr[0x343] = address
                self.csr[0x341] = self.pc
                self.pc = self.csr[0x305]
                raise rv.Trap
            self.ddr_reads.append(address)
        return super().access(address, write, value)

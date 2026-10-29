#!/usr/bin/env python3
"""Separate the completion counter from the V1 reject counter without DMA."""
import probe_config


def witness_cases():
    result=[]
    for n in range(3):
        # Blitter opcode 12 only configures the legacy affine coefficients.
        # No source/cache read or draw follows it.
        result.append(dict(name=f'legacy_affine_{n}',words=[0x0c000000]+[0]*7,accepted=True))
        result.append(dict(name=f'v1_invalidate_{n}',words=[0x1e000000]+[0]*7,accepted=True))
    assert all(len(c['words'])==8 and c['words'][0] in (0x0c000000,0x1e000000)
               and not any(c['words'][1:]) for c in result)
    return result


if __name__=='__main__':
    probe_config.cases=witness_cases
    probe_config.main()

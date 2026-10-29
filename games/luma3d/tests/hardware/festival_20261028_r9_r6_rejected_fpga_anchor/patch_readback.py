"""One bounded patch to the otherwise frozen inherited transport dependency."""
OLD='''def readback(tx, name, path, expected_bytes, expected_sha):
    # At the observed live-game console rate the 62 KiB helper's octal output
    # takes about 140 s. Keep the complete readback, with a bounded margin.
    data = tx.run(name, 'od -b -v '+path, 240)'''
NEW='''def readback_timeout(expected_bytes):
    # Root measured 474886 octal-output bytes / 240s while GM1 was active.
    # Budget five output bytes/input byte at a conservative 1200 bytes/s,
    # plus 60s framing margin; small retained probes keep their 240s window.
    if type(expected_bytes) is not int or not 1<=expected_bytes<=1048576:
        raise ValueError('Readback size must be bounded to 1..1048576 bytes')
    return max(240,(expected_bytes*5+1199)//1200+60)

def readback(tx, name, path, expected_bytes, expected_sha):
    data = tx.run(name, 'od -b -v '+path, readback_timeout(expected_bytes))'''
def apply(s):
    assert s.count(OLD)==1
    return s.replace(OLD,NEW)

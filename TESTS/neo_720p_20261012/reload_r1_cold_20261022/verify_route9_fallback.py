#!/usr/bin/env python3
"""Re-examine the programmed N56r8 fallback at 100 kHz, no FPGA/DDR writes."""
import fcntl
import json
import re
import subprocess

import probe_scan_observer as p

prior = p.HERE/'r9_route9_rgb_trial'
out = p.HERE/'r9_route9_fallback_recheck'
r = json.loads((prior/'result.json').read_text())
p.require(r['bitstream_sha256'] == '1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde'
          and r['fpga_reloaded'] and not r['linux_started'] and not r['sd_written'] and not r['flash_written']
          and r['restore_status'] == p.check_program_status((prior/'restore.log').read_text())
          and r['restore_status']['done'], 'Different recovery state')
p.require(not (prior/'rgb.tcl').exists(), 'Unexpected framebuffer phase')
script = prior/'restored.tcl'
text = script.read_text()
p.require(text.startswith(p.GUARD) and 'R8_BARS_RESTORED' in text
          and not re.search(r'^\s*(resume|load_image|write_memory)\b', text, re.M), 'Unexpected probe commands')
out.mkdir(exist_ok=False)
result = dict(passed=False, bitstream_sha256=p.R8SHA, fpga_programmed=False, sd_written=False,
              flash_written=False, linux_started=False, adapter_khz=100,
              prior_sha256=p.sha(prior/'result.json'), script_sha256=p.sha(script))
try:
    with (p.ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (out/'openocd.log').open('x') as log:
            subprocess.run(['/usr/local/bin/openocd', '-f', str(p.ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c', 'adapter speed 100; gdb_port disabled; tcl_port disabled; telnet_port disabled',
                '-f', str(script)], stdout=log, stderr=log, check=True, timeout=30)
    log = (out/'openocd.log').read_text()
    values = {n:[int(w, 0) for w in words.split()] for n, words in re.findall(r'^FALLBACK_(\d) (.+)$', log, re.M)}
    p.require(set(values) == {'0', '1'} and all(len(v) == 32 for v in values.values()), 'Incomplete samples')
    delta = (values['1'][6]-values['0'][6]) & 0xffffffff
    p.require(delta > 0 and all(v[2] == 0 and v[3] == 0 and v[24] == 0x1ff8f800 for v in values.values())
              and 'R8_BARS_RESTORED' in log, 'Fallback not progressing')
    result.update(passed=True, cpu_left_halted=True, frame_delta=delta, registers=values)
except Exception as exc:
    result['error'] = repr(exc)
finally:
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
raise SystemExit(0 if result['passed'] else 1)

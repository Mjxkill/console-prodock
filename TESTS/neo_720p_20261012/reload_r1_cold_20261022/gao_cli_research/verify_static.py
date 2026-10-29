#!/usr/bin/env python3
"""Record static GAO evidence. Never executes Gowin binaries or accesses USB."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
IDE = Path('/home/michael/gowin/IDE')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


evidence = {}
for name in ('gao_sh', 'gao_analyzer'):
    path = IDE / 'bin' / name
    raw = path.read_bytes()
    asm = subprocess.check_output(['objdump', '-d', '-C', str(path)], text=True)
    blocks = re.split(r'\n(?=[0-9a-f]{16} <)', asm)
    functions = {}
    for block in blocks:
        head = re.match(r'[0-9a-f]{16} <(.*)>:', block)
        if head:
            functions[head[1]] = block

    def strings_for(block):
        found = []
        for address in re.findall(r'# ([0-9a-f]+)', block):
            offset = int(address, 16) - 0x400000
            if offset < 0 or offset >= len(raw):
                continue
            value = raw[offset:offset + 256].split(b'\0')[0]
            if value and all(32 <= c < 127 for c in value):
                found.append(value.decode('ascii'))
        return found

    main_strings = strings_for(functions['main'])
    start = functions['GAO::GaoStandardDataManager::startDataTrigger(QList<int>)']
    check = functions['GAO::GaoStandardDataManager::checkState()']
    parse = functions['GAO::read_VER_2000(QDomDocument const&, QString&)']
    assert 'ATTR_AO_CAPTURE_INIT_DATA_ENABLED' in parse
    assert re.search(r'sete\s+0x68\(', parse)
    assert re.search(r'cmpb\s+\$0x0,0x68\(', start)
    assert 'startTrigger(GAO::AoCore*)' in start
    assert 'OP_SELECT_CAPTURE_INIT' in strings_for(check)
    assert 'OP_READ_CAPTURE_INIT' in strings_for(check)
    result = {'path': str(path), 'sha256': digest(path),
              'parsed_main_options': sorted(set(s for s in main_strings if s.startswith('-'))),
              'initial_capture_flag_offset': '0x68',
              'has_initial_capture_read_branch': True,
              'scope': 'static binary analysis; no device execution'}
    if name == 'gao_sh':
        exporter = functions['GAO::GaoCmdStandardAnalyzer::onReadRamComplete(int, int)']
        assert '_core%1_window%2' in strings_for(exporter)
        assert '.csv' in strings_for(exporter)
        assert 'us' in strings_for(exporter)
        result['output_suffix'] = '_core<core>_window<window>.csv'
        result['export_period_hardcoded'] = {'value': 1, 'unit': 'us'}
    evidence[name] = result

gao = ROOT / 'tang/impl/console_neo_n56r10_gao_startup/source/tang/boards/neo/startup.gao'
ao = ET.parse(gao).find('.//AoCore')
assert ao is not None and ao.get('capture_init_data_enabled') == 'true'
evidence['candidate_config'] = {'path': str(gao), 'sha256': digest(gao), 'ao_attributes': ao.attrib}
evidence['hardware_tested'] = False
evidence['neo_cable_selection_proven'] = False
(OUT / 'static_evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
print(json.dumps(evidence, indent=2))

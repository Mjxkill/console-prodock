#!/usr/bin/env python3
"""Synthetic tests: redaction, line numbers and indirect-secret false positives."""
import importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('scan',HERE/'scan.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
key='sk-'+('A'*32)
r=m.scan_bytes(('line1\n'+key+'\n').encode(),'synthetic','fixture')
assert len(r)==1 and r[0]['line']==2 and key not in json.dumps(r)
private='-----BEGIN '+'PRIVATE KEY-----'
r=m.scan_bytes(private.encode(),'synthetic','fixture');assert r[0]['type']=='private_key'
assert private not in json.dumps(r)
value='dummy_fixture_credential'
r=m.scan_bytes(('apiKey="'+value+'"').encode(),'synthetic','fixture')
assert r[0]['placeholder_indicator'] and value not in json.dumps(r)
assert not m.scan_bytes(b'key = os.environ["OLLAMA_API_KEY"]','synthetic','fixture')
assert not m.scan_bytes(b'--credential-file /path/to/secrets.env','synthetic','fixture')
(HERE/'SCANNER_TESTS.json').write_text(json.dumps({'passed':True,'cases':5,'inputs':'synthetic only; no credential disclosure'},indent=2)+'\n')
print('5 synthetic scanner/redaction checks PASS')

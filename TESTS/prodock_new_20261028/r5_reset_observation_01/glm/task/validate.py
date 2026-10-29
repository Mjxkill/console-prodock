import json,re
from pathlib import Path
p=Path(__file__).resolve().parent
f=json.loads((p/'owned/findings.json').read_text())
assert len(f.get('claims',[]))>=8
normal=lambda s:re.sub(r'\s+',' ',s).strip()
for c in f['claims']:
 assert c['status'] in ['documented','inference','unknown']
 s=Path(c['source']);assert s.name==str(s) and s.suffix in ['.txt','.v','.cst','.md']
 assert 8<=len(c['quote'])<=600
 assert normal(c['quote']) in normal((p/'context'/s).read_text()),c['id']
assert len(f.get('experiments',[]))>=2 and len(f.get('unknowns',[]))>=2
assert len((p/'owned/REPORT.md').read_text())>1500
print('PASS source citations and report shape; causal claims require independent review')

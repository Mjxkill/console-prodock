import pathlib,subprocess,sys,hashlib,json
root=pathlib.Path(__file__).resolve().parent
before=json.loads((root/'INPUTS.json').read_text())['protected_sha256']
for rel,expected in before.items():
 assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==expected,rel
p=root/'owned/test_adversarial.py'
assert len(p.read_text().splitlines())<=1000
r=subprocess.run([sys.executable,'-B',str(p)],cwd=root,text=True,capture_output=True,timeout=50)
print(r.stdout,end='');print(r.stderr,end='')
if r.returncode:raise SystemExit(r.returncode)
assert 'Ran ' in r.stderr and 'OK' in r.stderr,'Use actual unittest assertions and runner'
assert len((root/'owned/REPORT.md').read_text())>200,'Report not completed'
print('Protected verifier and context hashes preserved; independent suite completed')

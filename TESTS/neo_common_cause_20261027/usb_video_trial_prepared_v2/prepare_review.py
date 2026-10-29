"""Bind existing RTL proof and local mock tests. Never authorizes hardware."""
from pathlib import Path
import json,hashlib,difflib
import probe_usb_video as ctl
HERE=Path(__file__).parent.resolve();ROOT=ctl.ROOT
sha=ctl.sha
rtl=ctl.BASE_DIR/'candidate_02/usb_clock_constraints_01/protocol_result.json'
d=json.loads(rtl.read_text());assert d['passed'] and not d['hardware_access']
for relative,h in d['sources'].items():assert sha(ROOT/relative)==h,relative
assert sum(not x['expected_fail'] and x['passed'] for x in d['cases'])==3
assert sum(x['expected_fail'] and x['passed'] for x in d['cases'])==1
for rel in ['tang/rtl/usb/usb_idle_trace.v','tang/rtl/board/ddr_dcfifo.v']:
 assert sha(ctl.base.BUILD/'source'/rel)==sha(ctl.base.prior.t.R19/'source'/rel)
proofs={str(rtl):sha(rtl)}
for name in ['protocol_tests_result.json','controller_tests_result.json','signal_tests_result.json']:
 p=HERE/name;x=json.loads(p.read_text());assert x['passed'] and not x['hardware_access'];proofs[str(p)]=sha(p)
assert json.loads((HERE/'protocol_tests_result.json').read_text())['tcl_sha256']==sha(HERE/'usb_video.tcl')
assert json.loads((HERE/'controller_tests_result.json').read_text())['controller_sha256']==sha(HERE/'probe_usb_video.py')
signals=json.loads((HERE/'signal_tests_result.json').read_text())
assert signals['controller_sha256']==sha(HERE/'probe_usb_video.py')
assert signals['tool_sha256']==sha(HERE/'test_signals.py') and len(signals['cases'])==67
assert all(x['passed'] and not x['hardware_access'] for x in signals['cases'])
result={'passed':True,'hardware_access':False,'scope':'Existing exact frozen RTL 3 phases + 1 negative witness; unchanged Tcl protocol mocks 13 cases; restoration mocks 13 cases; 67 real POSIX signal cases with hardware IO mocked. No routed timing/physical proof.', 'proofs':proofs,'source_sha256':sha(Path(__file__))}
(HERE/'offline_result.json').write_text(json.dumps(result,indent=2)+'\n')
files=set(ctl.required_files())|{Path(__file__).resolve(),HERE/'protocol_tests_result.json',HERE/'controller_tests_result.json',HERE/'signal_tests_result.json'}
# Include source/log hashes already validated by the original RTL result.
files|={ROOT/k for k in d['sources']}
files|={p for p in (HERE/'protocol_tests').iterdir() if p.is_file()}
files.add(Path('/usr/bin/tclsh'))
review={'schema':1,'board':'neo','scope':'fresh_utna_video_then_restore','hardware_ready':False,'qualification_status':'FAIL','controller_sha256':sha(HERE/'probe_usb_video.py'),'bitstream_sha256':sha(ctl.base.BUILD/'impl/pnr/console_neo.fs'),'parent_r19_sha256':ctl.base.prior.t.R19_SHA,'anchor_sha256':ctl.ANCHOR_SHA,'proof_files':{str(p.resolve()):sha(p) for p in sorted(files)},'limits':['Preparation only: root must separately review and set hardware_ready true.','Observer-only MMIO writes, not read-only inspection.','Fresh UTNA activity does not qualify USB HS or disprove all conditional common reset/clock mechanisms.','Global bitstream timing FAIL retained; dynamic NCP D/Q/CE capture not used.']}
(HERE/'review_prepared.json').write_text(json.dumps(review,indent=2)+'\n')
old=HERE.parent/'usb_video_trial_prepared/probe_usb_video.py'
(HERE/'controller.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),(HERE/'probe_usb_video.py').read_text().splitlines(True),fromfile=str(old.relative_to(ROOT)),tofile=str((HERE/'probe_usb_video.py').relative_to(ROOT)))))
chunks=['REVIEW ONLY: new controller prepared; hardware_ready false; no hardware was used.\nReview the exact observer-only write protocol and cleanup, not general causes. Parent owns board access.\n']
for p in [HERE/'probe_usb_video.py',HERE/'utna_protocol.tcl',HERE/'video_prefix.tcl',HERE/'test_protocol.py',HERE/'test_controller.py',HERE/'test_signals.py',HERE/'offline_result.json']:
 chunks.append('\nFILE '+str(p.relative_to(ROOT))+' SHA256 '+sha(p)+'\n'+''.join(f'{i}: {l}\n' for i,l in enumerate(p.read_text().splitlines(),1)))
(HERE/'review_packet.txt').write_text(''.join(chunks))
print(json.dumps({'controller_sha256':sha(HERE/'probe_usb_video.py'),'tcl_sha256':sha(HERE/'usb_video.tcl'),'review_prepared_sha256':sha(HERE/'review_prepared.json'),'packet_sha256':sha(HERE/'review_packet.txt'),'packet_bytes':(HERE/'review_packet.txt').stat().st_size},indent=2))

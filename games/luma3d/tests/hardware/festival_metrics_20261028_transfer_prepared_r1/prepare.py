#!/usr/bin/env python3
"""Pure local generation/reconstruction; no remote execution or device access."""
import hashlib,importlib.util,json,math,shutil,subprocess,tempfile,time,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
BASE=ROOT/'games/luma3d/build/maze_events_20261027_r4';TARGET=ROOT/'games/luma3d/build/festival_memory_metrics_20261028_r4';OLD=ROOT/'games/luma3d/tests/hardware/festival_20261028_r9_prepared_r6';RX=ROOT/'games/luma3d/tests/hardware/rx2_20261028_prepared_r3';METRICS=ROOT/'games/luma3d/candidates/festival_memory_metrics_20261028_r1';PROOF=ROOT/'games/luma3d/tests/hardware/festival_20261028_tmpfs_cleanup_r3'
def info(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
def main():
 base=(BASE/'luma3d-riscv').read_bytes();target=(TARGET/'luma3d-riscv').read_bytes()
 assert info(base)==json.loads((BASE/'manifest.json').read_text())['riscv'] and info(base)['sha256']=='df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b'
 assert info(target)==json.loads((TARGET/'manifest.json').read_text())['riscv'] and info(target)['sha256']=='6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7'
 for src,dst in [(OLD/'build_delta.py','build_delta.py'),(OLD/'mc1-helper','mc1-helper'),(OLD/'helper-host','helper-host'),(OLD/'runtime_inspect.c','runtime_inspect.c'),(OLD/'prodock-uapi.h','prodock-uapi.h'),(BASE/'manifest.json','base_manifest.json'),(TARGET/'manifest.json','target_manifest.json'),(METRICS/'DELIVERY.json','metrics_delivery.json'),(METRICS/'read_metrics.py','read_metrics.py'),(RX/'sender.py','sender.py'),(RX/'manifest.json','rx2_manifest.json'),(PROOF/'helper_verified.bin','helper_verified.bin'),(PROOF/'result.json','helper_health.json')]:shutil.copy2(src,HERE/dst)
 assert (HERE/'mc1-helper').read_bytes()==(HERE/'helper_verified.bin').read_bytes()
 oldm=json.loads((OLD/'manifest.json').read_text());assert info((HERE/'mc1-helper').read_bytes())==oldm['files']['mc1-helper'] and info((HERE/'helper-host').read_bytes())==oldm['files']['helper-host']
 spec=importlib.util.spec_from_file_location('build_delta',HERE/'build_delta.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 raw=module.delta(base,target);packed=module.compress(raw);full=module.compress(target);(HERE/'metrics-r4.delta.lz4').write_bytes(packed);(HERE/'metrics-r4.full.lz4').write_bytes(full)
 reconstructions=[]
 with tempfile.TemporaryDirectory(prefix='fm4-prepare-') as tmp:
  for kind,blob,bytes_,crc_ in [('patch',packed,len(raw),zlib.crc32(raw)),('unpack',full,len(target),zlib.crc32(target))]:
   output=Path('/tmp/'+Path(tmp).name+'-'+kind);source=HERE/('metrics-r4.delta.lz4' if kind=='patch' else 'metrics-r4.full.lz4');cmd=[str(HERE/'helper-host'),kind,str(source),str(output),str(bytes_),f'{crc_:08x}']+([str(BASE/'luma3d-riscv')] if kind=='patch' else [])
   try:
    q=subprocess.run(cmd,capture_output=True,timeout=30);(HERE/(kind+'_host.log')).write_bytes(q.stdout+q.stderr);q.check_returncode();assert output.read_bytes()==target;reconstructions.append(dict(kind=kind,passed=True,output=info(output.read_bytes())))
   finally:
    if output.exists():output.unlink()
 (HERE/'host_reconstruction.json').write_text(json.dumps(dict(passed=True,hardware=False,methods=reconstructions),indent=2)+'\n')
 segments=math.ceil(len(packed)/(512*512));blocks=math.ceil(len(packed)/512);fullblocks=len(packed)//512;last=len(packed)%512
 data_wire=fullblocks*746+(2+4*math.ceil((44+last)/3) if last else 0);end_wire=segments*62
 pauses=fullblocks*47+(math.ceil((2+4*math.ceil((44+last)/3))/16) if last else 0)+segments*4
 windows=[dict(name=name,mode=k,args=['--festival-game',str(k),'--festival-sample-actions','4','--frames','3600'],table_actions=4,timeout_seconds=180) for k,name in enumerate(['othello','solitaire','chroma','hangman'])]
 windows += [dict(name='memory',mode=5,args=['--festival-memory','--memory-sample-actions','24','--frames','3600'],memory_actions=24,timeout_seconds=180),dict(name='garden',mode=4,args=['--festival','--manual','--festival-metrics','--frames','120'],timeout_seconds=180)]
 m=dict(schema=1,hardware_ready=False,hardware_access=False,base=info(base),target=info(target),target_manifest_sha256=info((TARGET/'manifest.json').read_bytes())['sha256'],helper=info((HERE/'mc1-helper').read_bytes()),base_remote='/tmp/luma3d-gm1',helper_remote='/tmp/mc1-helper',target_remote='/tmp/luma3d-fm4a',rx2_executable='/tmp/luma-rx2-probe3',remote_payload='/tmp/rx2-fm4a.delta.lz4.part',payload_file='metrics-r4.delta.lz4',delta=dict(raw_bytes=len(raw),raw_crc32=f'{zlib.crc32(raw):08x}'),alternatives=dict(full_lz4_bytes=len(full),raw_elf_bytes=len(target)),storage=dict(payload_bytes=len(packed),target_bytes=len(target),headroom_bytes=8<<20,minimum_before_transfer=len(packed)+len(target)+(8<<20),minimum_before_reconstruction=len(target)+(8<<20),helper_heap_upper_bytes=len(raw)+len(base)+len(target)+len(packed),required_memavailable_bytes=64<<20),transport=dict(protocol='RX2',chunk_bytes=16,pause_seconds=.002,block_bytes=512,blocks=blocks,segment_blocks=512,planned_sessions=segments,session_deadline_ms=900000,idle_ms=5000,payload_wire_bytes=data_wire,fin_stop_wire_bytes=end_wire,pacing_floor_seconds=pauses*.002,uart_wire_floor_seconds=(data_wire+end_wire)*10/115200,estimate_is_not_measurement=True),windows=windows,default_final_state='restore_gm1_showcase',protected=['/tmp/luma3d-gm1','/tmp/op2-live.save','/tmp/mc1-helper','/tmp/luma-rx','/tmp/luma3d-live.pid'],forbidden=['FPGA','SD','JTAG','kernel','boot','game save writes'],files={})
 for p in sorted(HERE.iterdir()):
  if p.is_file() and p.name not in ('plan.json','DELIVERY.json','sizes.json'):m['files'][p.name]=info(p.read_bytes())
 (HERE/'plan.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps({'prepared':True,'hardware':False,'payload_bytes':len(packed),'segments':segments,'storage':m['storage'],'transport':m['transport']},indent=2))
if __name__=='__main__':main()

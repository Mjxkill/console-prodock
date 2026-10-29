#!/usr/bin/env python3
"""Parse existing UTNA/video logs only. Never opens hardware or changes inputs."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path('/home/michael/console')
HERE=Path(__file__).resolve().parent
PHASES={'ARM':1,'DISARM':6,'STOPPED':2,'STABLE':2}
FIELDS={3:'ticks',4:'in2',5:'in3',6:'nak2',7:'nak3',8:'data2',9:'data3',10:'miss2',11:'miss3',12:'bad_response',13:'rx_error_cycles',14:'bad_token',15:'bus_reset_rising_edges',16:'sof_asserted_cycles',17:'tx_stall_cycles',18:'last_token',19:'last_response'}
LIMITS=[
 'Host UTNA_WRITE timestamps precede the MMIO write; they are not exact FPGA capture times.',
 'Ticks demonstrate sampled-domain activity only after a fresh coherent command/reply exchange; no HS enumeration, physical clock frequency or PLL_LOCK is inferred.',
 'Zero observed USB bus-reset edges does not prove absence of CPU/system/PLL resets, nor absence of USB reset outside the armed observation window.',
 'RXERROR and TXSTALL are sampled clock cycles, not packet counts. SOF increments for every asserted sampled cycle.',
 'Frame differences are modulo 2^32; wrap, reset and corrupt readback cannot be distinguished solely by a decreasing counter.',
 'Dynamic NCP D/Q/CE capture is not used. Global candidate timing FAIL is unchanged.'
]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def integer(token):
 if not re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)',token):raise ValueError('Bad numeric token '+repr(token))
 return int(token,16 if token.lower().startswith('0x') else 10)
def words(tokens,count):
 values=[integer(x) for x in tokens]
 if len(values)!=count or any(x>0xffffffff for x in values):raise ValueError('Wrong word count/width')
 return values

def index_proof():
 p=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled/source/tang/rtl/usb/usb_idle_trace.v'
 old=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local/source/tang/rtl/usb/usb_idle_trace.v'
 assert sha(p)==sha(old)=='97854f943d523304877e4fafc52c53e71ef03cb3e54940f13cd1a7a0bdbe8d9f'
 s=p.read_text();m=re.search(r'wire \[1023:0\] live=\{(.*?)\};',s,re.S);assert m
 body=re.sub(r'\s+','',m[1]);parts=[];start=0;depth=0
 for i,c in enumerate(body):
  if c=='{':depth+=1
  elif c=='}':depth-=1
  elif c==',' and depth==0:parts.append(body[start:i]);start=i+1
 parts.append(body[start:])
 expected=['ticks','in2','in3','nak2','nak3','data2','data3','miss2','miss3','bad_response','rx_errors','bad_token','resets','sofs','stalls','last_token','last_response']
 assert list(reversed(parts))[3:20]==expected
 assert list(reversed(parts))[:3]==["32'h55544e41","32'd1",'command']
 assert parts[:4]==["{21'd0,armed,pending,2'd0,target}",'first_fault','history',"{16'd0,max_accept,max_offer}"]
 for fragment in ["if(sof_sample)sofs<=sofs+1'b1", "if(rx_error_sample)rx_errors<=rx_errors+1'b1", "if(bus_reset_sample && !bus_reset_q)resets<=resets+1'b1", "if(tx_valid_sample && !tx_ready_sample)stalls<=stalls+1'b1"]:assert fragment in s
 video=p.parents[1]/'video/gpu_scanout.v';vs=video.read_text()
 for index,name in [(1,'shadow_base'),(2,"{29'b0,shadow_half,shadow_rgb565,shadow_enable}"),(6,'r_frames'),(7,'r_underflows'),(24,'r_display_checksum')]:
  assert f'({{32{{read_select[{index}]}}}} & ({name}))' in vs
 return {'source':str(p.relative_to(ROOT)),'source_sha256':sha(p),'r19_source_sha256':sha(old),'concat_line':s.count('\n',0,m.start())+1,'bank_indices':FIELDS,'status_word31':{'armed':10,'pending':9,'target_bits':'6:0'},'counter_update_lines':[i for i,l in enumerate(s.splitlines(),1) if any(x in l for x in ['if(sof_sample)','if(rx_error_sample)rx_errors','if(bus_reset_sample && !bus_reset_q)','if(tx_valid_sample && !tx_ready_sample)stalls'])], 'video_source':str(video.relative_to(ROOT)),'video_source_sha256':sha(video),'video_indices':{1:'shadow_base',2:'shadow_mode',6:'frames',7:'underflows',24:'display_checksum',28:'geometry'}}

def parse_text(text):
 records={k:{} for k in ['initial','write','status','bank','repeat','video_time','video_scan','video_gpu','usb_control']}
 malformed=[];failures=[];markers=[];reported_faults=[];done=[]
 def put(kind,key,value,line):
  if key in records[kind]:raise ValueError('Duplicate '+kind+' '+key)
  records[kind][key]={'value':value,'line':line}
 for n,line in enumerate(text.splitlines(),1):
  t=line.split()
  if not t:continue
  tag=t[0]
  try:
   if tag=='UTNA_INITIAL':put('initial','control',words(t[1:],3),n)
   elif tag=='UTNA_WRITE':
    assert len(t)==5;put('write',t[1],[integer(x) for x in t[2:]],n)
   elif tag=='UTNA_STATUS':put('status',t[1],words(t[2:],3),n)
   elif tag=='UTNA_BANK':
    assert len(t)==36;put('bank',t[1],{'command':integer(t[2]),'sequence':integer(t[3]),'words':words(t[4:],32)},n)
   elif tag=='UTNA_BANK_REPEAT':put('repeat',t[1],words(t[2:],32),n)
   elif tag=='VIDEO_TIME':
    assert len(t)==3;put('video_time',t[1],integer(t[2]),n)
   elif tag=='VIDEO_SCAN':put('video_scan',t[1],words(t[2:],30),n)
   elif tag=='VIDEO_GPU':put('video_gpu',t[1],words(t[2:],26),n)
   elif tag=='USB_TRACE_STATUS':put('usb_control',t[1],words(t[2:],3),n)
   elif tag=='UTNA_PROTOCOL_DONE':done.append(words(t[1:],4))
   elif tag=='USB_VIDEO_DONE':markers.append(n)
   elif tag in ['UTNA_REJECT','UTNA_BAD_SEQ','UTNA_TIMEOUT']:reported_faults.append({'line':n,'text':line})
  except (AssertionError,ValueError,IndexError) as e:malformed.append({'line':n,'text':line,'error':str(e)})
 def fail(condition,message):
  if not condition:failures.append(message)
 initial=records['initial'].get('control',{}).get('value')
 fail(initial==[0x55544e41,0,0],'Initial ID/status/sequence must be fresh')
 captures=[]
 for seq,(phase,command) in enumerate(PHASES.items(),1):
  b=records['bank'].get(phase,{}).get('value');w=records['write'].get(phase,{}).get('value');r=records['repeat'].get(phase,{}).get('value')
  fail(bool(b and w and r),phase+': missing command or complete repeated bank')
  if not(b and w and r):continue
  data=b['words'];fail(w[:2]==[command,seq] and b['command']==command and b['sequence']==seq,phase+': command/sequence mismatch')
  fail(data[:3]==[0x55544e41,1,command],phase+': bad captured header')
  fail(data==r,phase+': unstable bank')
  for suffix,expected in [('before',seq-1),('bank_before',seq),('bank_middle',seq),('bank_after',seq)]:
   status=records['status'].get(phase+'_'+suffix,{}).get('value')
   fail(status==[0x55544e41,0,expected],phase+': bad/missing '+suffix+' status')
  captures.append({'phase':phase,'command':command,'sequence':seq,'host_write_time_ms':w[2], 'header_words':data[:3], 'raw_words':data,'counters':{name:data[i] for i,name in FIELDS.items()},'armed':bool(data[31]&0x400),'pending':bool(data[31]&0x200),'target_address':data[31]&0x7f,'bank_repeated_exact':data==r,'acknowledged_idle':all(records['status'].get(phase+'_'+suffix,{}).get('value')==[0x55544e41,0,seq] for suffix in ['bank_before','bank_middle','bank_after'])})
 cap={x['phase']:x for x in captures}
 if all(x in cap for x in ['DISARM','STOPPED','STABLE']):
  a,b,c=(cap[x] for x in ['DISARM','STOPPED','STABLE'])
  fail(a['armed'] and a['counters']['ticks']>0,'No positive armed DISARM sample')
  fail(not b['armed'] and not c['armed'],'Counter not disarmed')
  fail(b['counters']['ticks']==((a['counters']['ticks']+1)&0xffffffff),'Final disarm tick not +1')
  fail(c['counters']['ticks']==b['counters']['ticks'],'Disarmed ticks changed')
  expected_done=[4,a['counters']['ticks'],b['counters']['ticks'],c['counters']['ticks']]
  fail(done==[expected_done],'Missing or inconsistent protocol completion values')
 else:fail(False,'Protocol capture incomplete')
 fail(len(markers)==1,'Missing/duplicate overall completion marker')
 fail(not reported_faults,'Controller reported protocol fault')
 fail(list(records['write'])==list(PHASES),'Unexpected command order/phase')
 fail(list(records['bank'])==list(PHASES),'Unexpected bank order/phase')
 for a,b in zip(captures,captures[1:]):fail(b['host_write_time_ms']>=a['host_write_time_ms'],'Nonmonotonic host command timestamps')
 video=[]
 for phase in ['T0','T100','T200','T1200','POST_USB']:
  ts=records['video_time'].get(phase,{}).get('value');data=records['video_scan'].get(phase,{}).get('value');gpu=records['video_gpu'].get(phase,{}).get('value');usb=records['usb_control'].get(phase,{}).get('value')
  if ts is None or data is None or gpu is None or usb is None:
   failures.append(phase+': incomplete video/control sample');continue
  fail(data[0]==0x47505531 and data[28]==0x02d00500 and gpu[0]==0x424c5432,phase+': GPU identity/geometry mismatch')
  fail(usb==[0x55544e41,0,4 if phase=='POST_USB' else 0],phase+': unexpected live UTNA status')
  video.append({'phase':phase,'host_time_ms':ts,'shadow_base':data[1],'shadow_mode':data[2],'frame_counter':data[6],'underflows':data[7],'display_checksum':data[24],'raw_scan':data,'raw_gpu':gpu,'usb_live_control':usb})
 for a,b in zip(video,video[1:]):fail(b['host_time_ms']>=a['host_time_ms'],'Nonmonotonic host video timestamps')
 window=None
 if len(video)>=2:
  a,b=video[0],video[-1];window={'host_elapsed_ms':b['host_time_ms']-a['host_time_ms'],'frame_delta_mod32':(b['frame_counter']-a['frame_counter'])&0xffffffff,'counter_decreased':b['frame_counter']<a['frame_counter']}
 return {'complete':len(markers)==1 and len(captures)==4 and len(video)==5,'capture_consistent':not(malformed or failures),'parse_errors':malformed,'check_failures':failures,'reported_faults':reported_faults,'captures':captures,'video_samples':video,'video_window':window,'raw_records':records}

def comparison_markdown(result):
 lines=['# Relevé hors carte des journaux vidéo/UTNA','', 'Ces valeurs sont extraites des journaux fournis ; elles ne qualifient ni le timing, ni une énumération USB HS.','', '| Build | Capture cohérente | Durée hôte vidéo (ms) | Delta images modulo 2³² | Sommes vidéo successives |','|---|---|---:|---:|---|']
 for name,b in result['boards'].items():
  w=b['video_window'] or {};sums=', '.join(f"0x{x['display_checksum']:08x}" for x in b['video_samples'])
  lines.append(f"| {name} | {b['capture_consistent']} | {w.get('host_elapsed_ms','?')} | {w.get('frame_delta_mod32','?')} | {sums} |")
 lines += ['', '| Build | Phase | Heure hôte écriture (ms) | Séq. | En-tête ID/version/cmd | ACK idle | Armed | Ticks | RX error cycles | Bus-reset fronts | SOF cycles | TX stall cycles |','|---|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|']
 for name,b in result['boards'].items():
  for c in b['captures']:
   v=c['counters'];header='/'.join(f'0x{x:x}' for x in c['header_words'])
   lines.append(f"| {name} | {c['phase']} | {c['host_write_time_ms']} | {c['sequence']} | {header} | {c['acknowledged_idle']} | {c['armed']} | {v['ticks']} | {v['rx_error_cycles']} | {v['bus_reset_rising_edges']} | {v['sof_asserted_cycles']} | {v['tx_stall_cycles']} |")
 lines += ['','Les heures hôte précèdent chaque écriture MMIO ; elles ne datent pas exactement le front FPGA de capture. ARM contient l’état avant effacement. Les champs après DISARM appartiennent à une fenêtre armée, pas à toute la vie du FPGA.','']
 for name,b in result['boards'].items():
  for error in b['check_failures']+b['parse_errors']:lines.append(f'- {name}: {error}')
 return '\n'.join(lines)+'\n'

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--r19-log',type=Path,required=True);ap.add_argument('--candidate-log',type=Path);ap.add_argument('--trial-result',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 result={'hardware_access':False,'scope':'Offline interpretation of existing logs only','tool_sha256':sha(Path(__file__)),'index_proof':index_proof(),'limits':LIMITS,'inputs':{},'boards':{}}
 trial=None
 if a.trial_result:
  trial=json.loads(a.trial_result.read_text());result['inputs'][str(a.trial_result.resolve())]=sha(a.trial_result)
  result['trial_metadata']={k:trial[k] for k in ['qualification_status','candidate_sha256','last_programmed_sha256','left_startup_verified','observations_completed']}
 for name,p in [('r19',a.r19_log),('candidate',a.candidate_log)]:
  if p is None:continue
  digest=sha(p);result['inputs'][str(p.resolve())]=digest
  if trial is not None:
   assert p.resolve().parent==a.trial_result.resolve().parent
   assert trial['files'][p.name]==digest,p
  result['boards'][name]=parse_text(p.read_text(errors='replace'))
 result['both_captures_consistent']=len(result['boards'])==2 and all(x['capture_consistent'] for x in result['boards'].values())
 a.out.mkdir(parents=True,exist_ok=False);(a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 (a.out/'comparison.md').write_text(comparison_markdown(result))
 print(json.dumps({'output':str(a.out),'both_captures_consistent':result['both_captures_consistent'],'errors':{k:v['check_failures']+v['parse_errors'] for k,v in result['boards'].items()}},indent=2))
 raise SystemExit(0 if all(x['capture_consistent'] for x in result['boards'].values()) else 1)
if __name__=='__main__':main()

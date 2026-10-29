#!/usr/bin/env python3
"""Offline parser controls, using copied Tcl-mock logs and synthetic read values."""
import hashlib,json,subprocess,sys
from pathlib import Path
import extract
HERE=Path(__file__).resolve().parent
PREP=HERE.parent/'usb_video_trial_prepared'
OUT=HERE/'tests_02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def fixture(text, moving=True):
    result=[];frames={'T0':0,'T100':6,'T200':12,'T1200':72,'POST_USB':96}
    for line in text.splitlines():
        t=line.split()
        if not t:result.append(line);continue
        if t[0]=='VIDEO_SCAN':
            v=[0]*30;v[0]=0x47505531;v[1]=0x800000;v[2]=3;v[6]=frames[t[1]] if moving else 0;v[7]=17
            v[24]=0x1ff8f800 if moving else 0;v[28]=0x02d00500
            line=' '.join(t[:2]+[hex(x) for x in v])
        elif t[0]=='VIDEO_GPU':line=' '.join(t[:2]+['0x424c5432']+['0']*25)
        elif t[0] in ['UTNA_BANK','UTNA_BANK_REPEAT']:
            off=4 if t[0]=='UTNA_BANK' else 2
            # Distinct sentinels catch silently shifted field indexes. These
            # are synthetic, not measured traffic or a complete RTL model.
            if t[1]!='ARM':
                for index,value in [(12,120),(13,130),(14,140),(15,150),(16,160),(17,170),(18,180),(19,190)]:t[off+index]=str(value)
            line=' '.join(t)
        result.append(line)
    return '\n'.join(result)+'\n'

def replace_field(text,tag,phase,index,value):
    result=[]
    for line in text.splitlines():
        t=line.split()
        if t[:2]==[tag,phase]:t[index]=str(value);line=' '.join(t)
        result.append(line)
    return '\n'.join(result)+'\n'

def main():
    OUT.mkdir(exist_ok=False)
    proof=extract.index_proof();cases=[]
    source=PREP/'protocol_tests/none.log';r19=fixture(source.read_text());candidate=fixture(source.read_text(),False)
    for name,text in [('r19',r19),('candidate',candidate)]:
        (OUT/(name+'.log')).write_text(text)
        parsed=extract.parse_text(text)
        assert parsed['complete'] and parsed['capture_consistent'],parsed
        assert parsed['video_samples'][0]['shadow_mode']==3
        assert parsed['video_samples'][0]['shadow_base']==0x800000
        d=parsed['captures'][1]['counters']
        assert (d['rx_error_cycles'],d['bus_reset_rising_edges'],d['sof_asserted_cycles'],d['tx_stall_cycles'])==(130,150,160,170)
        assert parsed['video_window']['frame_delta_mod32']==(96 if name=='r19' else 0)
        cases.append({'name':name+'_positive_with_index_sentinels','passed':True})
    variants={
        'malformed_number':replace_field(r19,'UTNA_BANK','DISARM',17,'NaN'),
        'wide_word':replace_field(r19,'UTNA_BANK','DISARM',17,0x100000000),
        'wrong_header':replace_field(r19,'UTNA_BANK','DISARM',6,7),
        'wrong_ack_sequence':replace_field(r19,'UTNA_STATUS','DISARM_bank_after',4,9),
        'unstable_bank':replace_field(r19,'UTNA_BANK_REPEAT','DISARM',15,999),
        'lost_final_tick':replace_field(r19,'UTNA_BANK','STOPPED',7,12000000),
        'command_time_reversal':replace_field(r19,'UTNA_WRITE','DISARM',4,0),
        'missing_done':r19.replace('USB_VIDEO_DONE\n',''),
        'duplicate_bank':r19+next(x for x in r19.splitlines() if x.startswith('UTNA_BANK DISARM'))+'\n',
        'partial_capture':r19[:r19.index('UTNA_BANK STOPPED')],
        'reported_fault':r19+'UTNA_TIMEOUT STABLE 0x55544e41 1 3\n',
    }
    for name,text in variants.items():
        p=extract.parse_text(text);assert not p['capture_consistent'],name
        (OUT/(name+'.log')).write_text(text)
        cases.append({'name':name,'passed':True,'parse_errors':p['parse_errors'],'check_failures':p['check_failures']})
    # Preserve exact Tcl error logs, with only mock video values substituted
    # so failure is attributable to protocol, not their all-zero mock GPU ID.
    for name in ['busy','rejected','sequence','no_ticks','keeps_ticking','armed_stuck']:
        p=extract.parse_text(fixture((PREP/'protocol_tests'/f'{name}.log').read_text()))
        assert not p['capture_consistent'],name
        assert not any('GPU identity' in x for x in p['check_failures'])
        cases.append({'name':'exact_tcl_mock_'+name,'passed':True,'check_failures':p['check_failures']})
    args=[sys.executable,str(HERE/'extract.py'),'--r19-log',str(OUT/'r19.log'),'--candidate-log',str(OUT/'candidate.log'),'--out',str(OUT/'comparison')]
    call=subprocess.run(args,capture_output=True,text=True,timeout=10);assert call.returncode==0,call.stderr
    result=json.loads((OUT/'comparison/result.json').read_text());assert result['both_captures_consistent']
    trial={'qualification_status':'FAIL','candidate_sha256':'synthetic','last_programmed_sha256':'synthetic','left_startup_verified':True,'observations_completed':True,'files':{p.name:sha(p) for p in [OUT/'r19.log',OUT/'candidate.log']}}
    tp=OUT/'synthetic_trial_result.json';tp.write_text(json.dumps(trial))
    boundargs=args[:-1]+[str(OUT/'bound_comparison'),'--trial-result',str(tp)]
    call=subprocess.run(boundargs,capture_output=True,text=True,timeout=10);assert call.returncode==0,call.stderr
    trial['files']['candidate.log']='0'*64;tp=OUT/'tampered_manifest.json';tp.write_text(json.dumps(trial))
    call=subprocess.run(args[:-1]+[str(OUT/'must_not_exist'),'--trial-result',str(tp)],capture_output=True,text=True,timeout=10)
    assert call.returncode!=0 and not (OUT/'must_not_exist').exists()
    cases.append({'name':'cli_complete_bound_and_wrong_digest_refused','passed':True})
    report={'passed':True,'hardware_access':False,'scope':'Offline parsing only; generated fixtures explicitly synthetic, no hardware/RTL qualification','tool_sha256':sha(HERE/'extract.py'),'test_sha256':sha(Path(__file__)),'mock_source_sha256':sha(source),'index_proof':proof,'cases':cases}
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(cases),'result':str(OUT/'result.json')}))
if __name__=='__main__':main()

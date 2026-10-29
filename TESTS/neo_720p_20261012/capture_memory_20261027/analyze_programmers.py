#!/usr/bin/env python3
"""Read-only comparison of FS metadata, offline SVF and used loader sources."""
import collections
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SRC=Path('/home/michael/openFPGALoader-src')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    report={'hardware_access':False,'script_sha256':sha(Path(__file__)),'builds':{}}
    for name,build,logname in [('r19','console_neo_n56r19_capture_ce_local','fallback_r19'),('r21','console_neo_n56r21r1_capture_memory','program_r21')]:
        fs=ROOT/'tang/impl'/build/'impl/pnr/console_neo.fs'
        lines=fs.read_text().splitlines()
        header=dict(re.findall(r'^//([^:\r\n]+): (.*)$','\n'.join(lines),re.M))
        binary=[(i+1,line) for i,line in enumerate(lines) if line and not line.startswith('//')]
        assert all(set(line)<={'0','1'} and len(line)%8==0 for _,line in binary)
        config_header=next(i for i,(_,line) in enumerate(binary) if len(line)==32 and line[:8]=='00111011')
        count=int(binary[config_header][1][-16:],2)
        cfg=binary[config_header+1:config_header+1+count]
        assert len(cfg)==count and all(len(line)==1584 for _,line in cfg)
        # Exact FsParser calculation (uncompressed, padding=0, CRC enabled).
        computed=sum(int(line[i:i+16],2) for _,line in cfg for i in range(0,len(line)-64,16))&0xffff
        log=HERE/'startup_100k_20261027_090320'/(logname+'.log')
        observed=int(re.search(r'checksum 0x([0-9a-f]+)',log.read_text())[1],16)
        assert computed==observed
        svf=HERE/'programmer_comparison_02'/(name+'.svf')
        raw=HERE/'programmer_comparison_raw_01'/(name+'.svf')
        svftext=svf.read_text();instructions=re.findall(r'SIR 8 TDI \(([0-9A-F]+)\)',svftext)
        svf_frames=[f'{int(h,16):01513b}'[::-1]
                    for h in re.findall(r'SDR 1513 TDI \(([0-9A-F]+)\)',svftext)]
        frame_mismatch=[i for i,((_,line),sdr) in enumerate(zip(cfg,svf_frames))
                        if line[7:-64]!=sdr]
        extras=svf_frames[len(cfg):]
        extra_matches=[]
        for value in extras:
            extra_matches.append([{'line':i+1,'line_bits':len(line),'offset':line.find(value)}
                for i,line in enumerate(lines) if len(line)>1513 and value in line])
        usercode=int(re.search(r'SIR 8 TDI \(0A\);\s*RUNTEST 5 TCK;\s*SDR 32 TDI \(([0-9A-F]+)\)',svftext)[1],16)
        assert usercode==int(header['UserCode'],16)
        rawbits=sum(len(line) for _,line in binary)
        report['builds'][name]={'fs_sha256':sha(fs),'metadata':header,'binary_bits':rawbits,
          'binary_line_lengths':dict(collections.Counter(len(line) for _,line in binary)),
          'configuration_frames':count,'loader_final_chunk_bits':rawbits%524288,
          'loader_checksum_computed_and_logged':f'0x{computed:04x}',
          'vendor_svf_usercode':f'0x{usercode:08x}','vendor_svf_sha256':sha(svf),
          'vendor_svf_op2_equals_op16':svf.read_bytes()==raw.read_bytes(),
          'vendor_svf_sdr_lengths':dict(collections.Counter(re.findall(r'SDR (\d+)',svftext))),
          'vendor_svf_instructions':instructions,
          'vendor_svf_frame_mapping':{'mapping':'SDR1513 LSB-first == FS1584[7:-64]',
              'checked_frames':min(len(cfg),len(svf_frames)),'mismatch_count':len(frame_mismatch),
              'extra_frames':len(extras),'extra_matching_FS_lines':extra_matches},
          'vendor_svf_checked_status':re.findall(r'TDO \(([0-9A-F]+)\).*MASK \(([0-9A-F]+)\)',svftext)[-1],
          'short_nonframe_words_after_configuration':[{'line':line_no,'bits':len(line),'value':hex(int(line,2))}
              for line_no,line in binary[config_header+count+1:] if len(line)<=64]}
    a,b=(report['builds'][k]['metadata'] for k in ('r19','r21'))
    report['metadata_differences']={k:[a.get(k),b.get(k)] for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
    used=Path('/home/michael/.local/bin/openFPGALoader')
    assert sha(used)==sha(SRC/'build/openFPGALoader')
    report['loader_binary_sha256']=sha(used)
    report['source_sha256']={str(p):sha(p) for p in [SRC/'src/gowin.cpp',SRC/'src/fsparser.cpp',SRC/'src/ftdipp_mpsse.cpp']}
    report['conclusions']={
      'compression_or_device_metadata_difference':False,
      'both_payload_byte_aligned_and_nonzero_final_chunk':all(v['loader_final_chunk_bits']>0 for v in report['builds'].values()),
      'vendor_svf_is_not_proof_of_live_vendor_sequence':True,
      'no_full_sram_readback_proven':True,'loader_causal_fault_proven':False}
    (HERE/'programmer_comparison_02/analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

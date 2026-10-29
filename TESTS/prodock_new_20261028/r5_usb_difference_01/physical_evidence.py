#!/usr/bin/env python3
"""Compare published USB SDF branches/options, without inferring silicon placement.

The SDF delay models changed between Gowin versions. Equal global-region rows
and unequal delays do not prove equal or unequal detailed physical routes.
"""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
NAMES = {'g22':'gpu_geometry_g22r0','r5':'prodock_sd_boot_20261029_r5'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def relevant(name):
    return 'usb' in name.lower() or name.startswith(('u_pll_f/','u_pll_b/'))


def read_sdf(path):
    arcs={}; header={}
    with path.open() as src:
        for line in src:
            if line.startswith('//Tool Version:'):header['tool']=line.strip().split(': ',1)[1]
            for key in ['VOLTAGE','TEMPERATURE','TIMESCALE','PROCESS']:
                m=re.search(r'\('+key+r' (.*?)\)',line)
                if m:header[key]=m.group(1)
            m=re.search(r'\(INTERCONNECT (\S+) (\S+) (.*?)\)\s*$',line)
            if not m:continue
            a,b,raw=m.groups();a=a.replace('\\/','/');b=b.replace('\\/','/')
            if not(relevant(a) or relevant(b)):continue
            triple=re.findall(r'(-?\d+(?:\.\d+)?):(-?\d+(?:\.\d+)?):(-?\d+(?:\.\d+)?)',raw)
            assert triple, line
            assert (a,b) not in arcs,(a,b)
            arcs[a,b]=[[float(v) for v in group] for group in triple]
    return header,arcs


def main():
    inputs={};sdfs={};headers={};options={};configs={};pinrows={};package_rows={};globals_={}
    for label,name in NAMES.items():
        pn=ROOT/'tang/impl'/name/'impl/pnr'
        sdf=next(pn.glob('*.sdf'));rpt=next(pn.glob('*.rpt.txt'))
        headers[label],sdfs[label]=read_sdf(sdf)
        options[label]=(pn/'cmd.do').read_text().splitlines()
        configs[label]=(pn/'device.cfg').read_text().splitlines()
        text=rpt.read_text();rows=text.splitlines()
        pinpart=text.split('7. Pinout by Port Name',1)[1].split('8. All Package Pins',1)[0]
        pinrows[label]=sorted(re.sub(r'\s+',' ',x.strip()) for x in pinpart.splitlines()
                              if x.lstrip().startswith('usb_') and ' | ' in x)
        package_rows[label]=sorted(re.sub(r'\s+',' ',x.strip()) for x in text.split('8. All Package Pins',1)[1].splitlines()
                                   if 'usb_' in x and ' | ' in x)
        globalpart=text.split('6. Global Clock Signals',1)[1].split('7. Pinout',1)[0]
        globals_[label]=[re.sub(r'\s+',' ',x.strip()) for x in globalpart.splitlines() if '|' in x]
        inputs[label]={str(x.relative_to(ROOT)):sha(x) for x in [sdf,rpt,pn/'cmd.do',pn/'device.cfg']}
    a,b=sdfs['g22'],sdfs['r5'];common=a.keys()&b.keys()
    changed=[{'source':k[0],'target':k[1],'g22_ns':a[k],'r5_ns':b[k],
              'nominal_delta_ns':round(b[k][0][1]-a[k][0][1],3)} for k in common if a[k]!=b[k]]
    changed.sort(key=lambda r:abs(r['nominal_delta_ns']),reverse=True)
    # Identical endpoints, selected for physical clock/IO/calibration evidence.
    selected=[r for r in changed if (r['target'].endswith(('/FCLK','/PCLK','/CLKIN','/RESETN','/OEN'))
             or 'pullup_en_o_s1' in r['target'] or 'reset_calib_s2/' in r['target']
             or 'u_usb_controller_start/reset_s4/' in r['target'])]
    clocks=[r for r in changed if r['target'].endswith(('/CLK','/PCLK','/FCLK','/CLKIN'))]
    # Compare exact option values; paths are identities, not optimizations.
    normalize=lambda lines:[re.sub(r'/home/michael/console/tang/impl/[^ /]+','BUILD',x)
                            for x in lines if not x.startswith(('-d ','-cst ','-cfg ','-sdc ','-inc_pnr '))]
    data={'hardware':False,'units':'ns','model_headers':headers,
          'delay_model_changed':headers['g22']!=headers['r5'],
          'scope':'public SDF annotated arcs only; no recovery waiver or placement inference',
          'arc_counts':{k:len(v) for k,v in sdfs.items()},'common_arcs':len(common),
          'different_common_arcs':len(changed),'only_g22_arcs':len(a.keys()-b.keys()),
          'only_r5_arcs':len(b.keys()-a.keys()),'clock_arcs_changed':len(clocks),
          'largest_nominal_differences':changed[:20],'selected_common_arcs':selected,
          'usb_pin_rows_equal':pinrows['g22']==pinrows['r5'],'usb_pin_rows':pinrows,
          'usb_package_rows_equal':package_rows['g22']==package_rows['r5'],
          'usb_package_rows':package_rows,
          'port_report_format_note':'Old by-port table omits LVDS input pseudo-pins; compare All Package Pins for actual assignments',
          'global_rows_equal':globals_['g22']==globals_['r5'],
          'normalized_pnr_options_equal':normalize(options['g22'])==normalize(options['r5']),
          'device_cfg_equal':configs['g22']==configs['r5'],
          'device_cfg_diff':list(difflib.unified_diff(configs['g22'],configs['r5'],fromfile='g22',tofile='r5')),
          'incremental_anchor_r5':next(x for x in options['r5'] if x.startswith('-inc_pnr ')),
          'placements_limitation':'.p/.pr encrypted vendor files; public reports give IO/global regions, not all cell coordinates',
          'inputs':inputs}
    (OUT/'physical_evidence.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({k:data[k] for k in ['model_headers','arc_counts','common_arcs','different_common_arcs',
          'clock_arcs_changed','usb_pin_rows_equal','usb_package_rows_equal','global_rows_equal','normalized_pnr_options_equal',
          'device_cfg_equal','device_cfg_diff']},indent=2))


if __name__=='__main__':main()

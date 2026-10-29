#!/usr/bin/env python3
"""Prepare, then explicitly generate, official USB HS IPs for Neo PG484C.

Preparation invokes no vendor tool. Generation requires the reviewed manifest,
produces only local IP netlists and never modifies a console build or hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from gowin_toolchain import IDE, environment, SYSTEM_FREETYPE
from board_contract import before_build, record_build

REFERENCE = ROOT/'tang/impl/gpu_sdusb_c28'
G22 = ROOT/'tang/impl/gpu_geometry_g22r0/source'
PREPARED = HERE/'prepared'
GENERATED = HERE/'generated'
DEVICE = dict(id='GW5AST-138C', package='PBGA484A', speed='1', partNumber='GW5AST-LV138PG484AC1/I0')
IPS = {
    'usb_ip': dict(vendor='USB_DEVICE_CONTROLLER',stem='usb_device_controller',
        spec='usb_device_controller.ipspec',version='3.3',id='usb20_device_controller',
        config='usb_device_controller_define.v',project='controller.prj',metadata='usb_controller.json'),
    'usb_phy_ip': dict(vendor='USBTwoSoftPHY',stem='usb2_0_softphy',
        spec='usbtwosoftphy.ipspec',version='3.5',id='usb_20_softphy',
        config='usb2_0_softphy_name.v',project='phy.prj',metadata='usb_phy.json'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def inputs():
    records = {}
    paths = [Path(__file__), ROOT/'tools/build_gpu.py', ROOT/'tools/gowin_toolchain.py',
             IDE/'bin/GowinSynthesis', SYSTEM_FREETYPE.resolve(strict=True)]
    neo_project = ROOT/'tang/impl/console_neo_n56_observe/impl/gwsynthesis/console_neo.prj'
    if ET.parse(neo_project).getroot().find('Device').attrib != DEVICE:
        raise ValueError('Neo target metadata differs')
    paths.append(neo_project)
    for directory,ip in IPS.items():
        vendor = IDE/'ipcore'/ip['vendor']
        spec = vendor/ip['spec']
        info = ET.parse(spec).getroot().find('ip')
        if info is None or info.attrib.get('id') != ip['id'] or info.attrib.get('version') != ip['version']:
            raise ValueError('Unexpected official IP version: '+directory)
        meta = json.loads((REFERENCE/ip['metadata']).read_text())
        if meta['ip_version'] != ip['version']:
            raise ValueError('Reference IP metadata differs')
        paths.extend([spec,REFERENCE/ip['metadata']])
        files = {}
        for name in (ip['stem']+'.v',ip['stem']+'_top.v','static_macro_define.v'):
            official,ref = vendor/'data'/name,REFERENCE/'source'/directory/name
            if sha(official) != sha(ref):
                raise ValueError('Official vendor source differs from C28: '+name)
            paths.extend([official,ref])
            files[name] = dict(source=str(official),sha256=sha(official))
        config = REFERENCE/'source'/directory/ip['config']
        g22config = G22/directory/ip['config']
        if config.read_bytes() != g22config.read_bytes():
            raise ValueError('C28 and G22 configuration differ')
        macros = config.read_text().splitlines()
        if directory == 'usb_ip':
            required = ['`define module_name USB_Device_Controller_Top','`define HSSUPPORT',
                        '`define DESC_PACKET_MAX64','`define SELFPOWERED','`define UTMI']
            required += [f'`define ENDPT{ep}_{direction}_T_TYPE 0' for ep in range(1,16) for direction in ('IN','OUT')]
        else:
            required = ['`define module_name USB2_0_SoftPHY_Top','`define TX_DELAY_0_BIT',
                        '`define UTMI','`define GW5AT','`define V_120']
        if macros != required:
            raise ValueError('Unexpected HS macros: '+directory)
        paths.extend([config,g22config])
        files[ip['config']] = dict(source=str(config),sha256=sha(config))
        reference_xml = REFERENCE/'source'/directory/ip['project']
        paths.append(reference_xml)
        project = ET.parse(reference_xml).getroot()
        old_device = dict(project.find('Device').attrib)
        if old_device != dict(id='GW5AST-138B',package='FCPBGA676A',speed='1',partNumber='GW5AST-LV138FPG676AC1/I0'):
            raise ValueError('Unexpected reference target')
        project.find('Device').attrib.clear()
        project.find('Device').attrib.update(DEVICE)
        destination = GENERATED/directory
        for entry in project.find('FileList'):
            name = Path(entry.attrib['path']).name
            if name not in (ip['stem']+'.v',ip['stem']+'_top.v') or entry.attrib['type']!='verilog':
                raise ValueError('Unexpected XML input')
            entry.attrib['path']=str(destination/name)
        options = project.find('OptionList')
        for option in options:
            if option.attrib['type']=='include_path':
                option.attrib['value']=str(destination)
        expected_options = dict(disable_insert_pad='1',enable_dsrm='0',include_path=str(destination),
            output_file=ip['stem']+'.vg',ram_balance='1',ram_rw_check='1',
            top_module='USB_Device_Controller_Top' if directory=='usb_ip' else 'USB2_0_SoftPHY_Top',
            vcc='0.9',vccx='1.8',verilog_language='sysv-2017')
        if {o.attrib['type']:o.attrib['value'] for o in options} != expected_options:
            raise ValueError('Unexpected synthesis options')
        ET.indent(project)
        xml = ET.tostring(project,encoding='UTF-8',xml_declaration=True).decode()+'\n'
        records[directory]=dict(**ip,files=files,xml=xml,old_device=old_device,device=DEVICE,
            macros=macros,command=[str(IDE/'bin/GowinSynthesis'),'-prj',ip['project']],
            cwd=str(destination),vendor_sources_unmodified=True)
    return dict(hardware_access=False,full_console_build=False,ips=records,
        compiler=str(IDE/'bin/GowinSynthesis'),system_freetype=True,
        files_sha256={str(p):sha(p) for p in paths},
        changes_from_c28=['Device id/package/partNumber = Neo138C/PG484','Local input/include/output-directory paths'],
        excluded=['No pin or PLL changes','No RTL or generated IP copy into shared sources','No R4 modification','No board access'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only',action='store_true')
    mode.add_argument('--generate-reviewed',metavar='MANIFEST_SHA256')
    args=parser.parse_args()
    record=inputs()
    if args.prepare_only:
        PREPARED.mkdir(exist_ok=False)
        for directory,ip in record['ips'].items():
            target=PREPARED/directory;target.mkdir()
            for name,item in ip['files'].items():
                shutil.copy2(item['source'],target/name)
                if sha(target/name)!=item['sha256']:
                    raise ValueError('Prepared source copy differs')
            shutil.copy2(IDE/'ipcore'/ip['vendor']/ip['spec'],target/ip['spec'])
            (target/ip['project']).write_text(ip['xml'])
        record['prepared_sha256']={str(p.relative_to(PREPARED)):sha(p)
            for p in PREPARED.rglob('*') if p.is_file()}
        dump(PREPARED/'manifest.json',record)
        print(json.dumps(dict(prepared=str(PREPARED),manifest_sha256=sha(PREPARED/'manifest.json'),
                              device=DEVICE,compiler_invoked=False),indent=2))
        return
    if sha(PREPARED/'manifest.json') != args.generate_reviewed:
        raise ValueError('Different reviewed manifest')
    expected=json.loads((PREPARED/'manifest.json').read_text())
    hashes=expected.pop('prepared_sha256')
    if expected != record:
        raise ValueError('Inputs changed after preparation')
    if {str(p.relative_to(PREPARED)):sha(p) for p in PREPARED.rglob('*')
        if p.is_file() and p!=PREPARED/'manifest.json'} != hashes:
        raise ValueError('Prepared source/XML drift')
    contract=before_build('neo',candidate=True)
    GENERATED.mkdir(exist_ok=False)
    record_build(GENERATED,contract)
    shutil.copy2(PREPARED/'manifest.json',GENERATED/'reviewed_manifest.json')
    results={}
    for directory,ip in record['ips'].items():
        target=GENERATED/directory
        shutil.copytree(PREPARED/directory,target)
        if (target/ip['project']).read_text()!=ip['xml']:
            raise ValueError('Generation XML changed')
        with (target/'synth.log').open('w') as log:
            completed=subprocess.run(ip['command'],cwd=target,env=environment(system_freetype=True),
                                     stdout=log,stderr=subprocess.STDOUT)
        log=(target/'synth.log').read_text(errors='replace')
        output=target/(ip['stem']+'.vg')
        if completed.returncode or re.search(r'^(ERROR|unknown option:)',log,re.M) or 'GowinSynthesis finish' not in log:
            raise SystemExit('IP generation failed: '+directory)
        if not output.is_file() or output.stat().st_size<1000:
            raise SystemExit('Generated IP netlist absent: '+directory)
        for name,item in ip['files'].items():
            if sha(target/name)!=item['sha256']:
                raise SystemExit('Vendor/config input changed during synthesis: '+name)
        results[directory]=dict(version=ip['version'],target=DEVICE,exit_code=completed.returncode,
            netlist=str(output),netlist_sha256=sha(output),log_sha256=sha(target/'synth.log'),
            vendor_sources_unmodified=True)
        dump(GENERATED/'generation_progress.json',results)
    dump(GENERATED/'result.json',dict(status='GENERATED_NOT_INTEGRATED',ips=results,
        reviewed_manifest_sha256=args.generate_reviewed,hardware_access=False,
        limitation='IP generation success is not board, USB enumeration, timing, or integration validation.'))
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()

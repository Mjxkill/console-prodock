#!/usr/bin/env python3
"""Prepare bounded, disjoint read-only contexts for two independent analyses."""
import hashlib, importlib.util, json, shutil, subprocess
from pathlib import Path
ROOT=Path('/home/michael/console'); OUT=Path(__file__).resolve().parent
PREV=OUT.parent/'r5_usb_difference_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def copy(src,dst,prov):
    shutil.copyfile(src,dst);prov[str(dst.relative_to(OUT))]={'source':str(src),'sha256':sha(src)}
prov={}
for label in ['deepseek','glm']:
    (OUT/label/'task/context').mkdir(parents=True,exist_ok=True)
    (OUT/label/'task/owned').mkdir(exist_ok=True)
for b,path in [('g22',ROOT/'tang/impl/gpu_geometry_g22r0/source'),('r5',ROOT/'tang/impl/prodock_sd_boot_20261029_r4/source')]:
    for label in ['deepseek','glm']:
        for rel,short in [('tang/rtl/console_top.v','top.v'),('tang/rtl/usb/usb_reset_release.v','reset.v'),('tang/constr/gpu.cst','pins.cst')]:
            copy(path/rel,OUT/label/'task/context'/f'{b}_{short}',prov)
    candidates=list(path.rglob('ae350_soc.v'))
    assert len(candidates)==1,candidates
    copy(candidates[0],OUT/'deepseek/task/context'/f'{b}_soc.v',prov)
for label in ['deepseek','glm']:
    copy(PREV/'critical_cells.json',OUT/label/'task/context/critical_cells.json',prov)
    copy(OUT.parent/'r5_hardware_01/README.md',OUT/label/'task/context/hardware_root.md',prov)
# Pull causal reset/clock primitive subgraphs from exact post-route netlists.
s=importlib.util.spec_from_file_location('extract',PREV/'extract.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
output_pins={'F','O','Q','SUM','COUT','CLKOUT','CLKOUT0','CLKOUT1','CLKOUT2','CLKOUT3','LOCK','RESET_O'}
for b,base in [('g22',ROOT/'tang/impl/gpu_geometry_g22r0'),('r5',ROOT/'tang/impl/prodock_sd_boot_20261029_r5')]:
    vo=next((base/'impl/pnr').glob('*.vo'));cells=m.parse(vo.read_text())
    starts={n for n,c in cells.items() if n.startswith(('\\u_usb_ref_start/','\\u_usb_phy_start/','\\u_usb_controller_start/','\\u_pll_f/','\\u_pll_b/')) or '/u_oser_rst/' in n or (m.selected(n) and c['kind'] in m.SPECIAL)}
    drivers={}
    for n,c in cells.items():
        for pin,net in c['ports'].items():
            if pin in output_pins:drivers.setdefault(net,set()).add(n)
    names=set(starts)
    # Combinational expansion; stop at outside registers with their own pins
    # included as boundaries. Payload state is not a clock/reset proof.
    todo=list(starts)
    while todo:
        n=todo.pop();c=cells[n]
        if n not in starts and c['kind'].startswith('DFF'):continue
        for pin,net in c['ports'].items():
            if pin in output_pins:continue
            for parent in drivers.get(net,[]):
                if parent not in names:names.add(parent);todo.append(parent)
    obj={'source':str(vo),'sha256':sha(vo),'scope':'clock/reset primitive cone; stop at outside FF, not payload transitive closure','roots':sorted(starts),'cells':{n:cells[n] for n in sorted(names)}}
    dst=OUT/'deepseek/task/context'/f'{b}_cone.json';write(dst,obj)
    assert dst.stat().st_size<1024*1024,(dst,dst.stat().st_size)
    print(b,len(starts),len(names),dst.stat().st_size)
# Official docs: full extracted files retained, bounded useful pages passed.
docs=[('UG704',Path('/home/michael/gowin/Programmer/doc/EN/UG704-1.0.7E_Arora Ⅴ 138K&75K FPGA Product Programming and Configuration Guide.pdf')),('SUG100',Path('/home/michael/gowin/IDE/doc/EN/SUG100-4.4.6E_Gowin Software User Guide.pdf')),('UG306',Path('/home/michael/gowin/IDE/doc/EN/UG306-1.0.7E_Arora V Clock User Guide.pdf')),('SCHEMATIC',Path('/home/michael/Téléchargements/TANG_MEGA-138K_Pro-Dock-4071f_Schematics.pdf'))]
(OUT/'docs').mkdir(exist_ok=True)
for tag,src in docs:
    dst=OUT/'docs'/f'{tag}.txt';subprocess.run(['pdftotext','-layout',str(src),str(dst)],check=True)
    pages=dst.read_text().split('\f');need=['background','startup','start-up','power-up','reset','sample','boundary','uart','fpga_tx','fpga_rx','F19','PLL_LOCK']
    indices=[i for i,page in enumerate(pages) if tag=='SCHEMATIC' or any(x.lower() in page.lower() for x in need)]
    excerpt='\n\n'.join(f'=== PDF PAGE {i+1} ===\n{pages[i]}' for i in indices)
    ex=OUT/'glm/task/context'/f'{tag}.txt';ex.write_text(excerpt)
    assert ex.stat().st_size<1024*1024
    prov[str(ex.relative_to(OUT))]={'source':str(src),'pdf_sha256':sha(src),'text_sha256':sha(ex),'pdf_pages':[i+1 for i in indices]}
for label in ['deepseek','glm']:
    write(OUT/label/'task/context/PROVENANCE.json',prov)
    (OUT/label/'task/owned/REPORT.md').write_text('Pending analysis.\n')
    (OUT/label/'task/owned/findings.json').write_text('{}\n')
write(OUT/'preparation_provenance.json',prov)

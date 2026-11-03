"""Scope the Sipeed DDR400 reference timing model to the hard PHY clock.

The reference separates reference/UI/PHY clock groups. Here reference/UI
crossings retain the console's existing 8 ns checks. Only the fast PHY clock
is separated, and its entire routed fanout must remain in vendor IO macros.
This model does not prove calibration/electrical correctness on the board.
"""
import collections
import hashlib
import json
from pathlib import Path
from vendor_reference import ROOT as SIPEED_REFERENCE
import re

PROFILE=Path('tang/boards/neo/ddr_phy_timing.json')
REFERENCE=SIPEED_REFERENCE / 'ddr_test/Hynix_400MHz/src/ddr3_1v4_hs.sdc'
PREFIX='u_soc/g_ddr.u_ddr/u_ip/'
FAST_NET='u_soc/ddr3_memory_clk'
BLOCK='''// Vendor DDR400 PHY timing model; fabric reference/UI CDC stays bounded.
set_false_path -from [get_clocks {ddr3_mem_clk}] -to [get_clocks {clk50 ddr3_sys_clk}]
set_false_path -from [get_clocks {clk50 ddr3_sys_clk}] -to [get_clocks {ddr3_mem_clk}]
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clock_fanout(text):
    """Fail closed if the separated fast clock reaches any console fabric."""
    uses=[];errors=[]
    for m in re.finditer(r'^(\w+)\s+(\\\S+|\w+)\s*\((.*?)\);',text,re.M|re.S):
        for pin,net in re.findall(r'\.(\w+)\(([^()]*)\)',m[3]):
            if net.strip().lstrip('\\')==FAST_NET:
                uses.append((m[1],m[2].lstrip('\\'),pin))
    expected={('PLL','CLKOUT2'):1,('DDRDLL','CLKIN'):1,('CLKDIV','HCLKIN'):1,
              ('OSER8_MEM','FCLK'):40,('IDES8_MEM','FCLK'):32,
              ('OSER8','FCLK'):25,('DQS','FCLK'):4}
    if collections.Counter((kind,pin) for kind,name,pin in uses)!=expected:
        errors.append('DDR fast-clock primitive fanout differs from the reviewed 32-bit PHY')
    for kind,name,pin in uses:
        if (kind,pin)==('PLL','CLKOUT2'):
            if name!='u_soc/u_pll_ddr3/u_pll/PLL_inst':errors.append('Changed DDR PLL driver')
        elif not name.startswith(PREFIX):errors.append('Fast DDR clock reaches non-IP fabric: '+name)
    # A new continuous alias could bypass the direct-fanout audit.
    for line in text.splitlines():
        if line.lstrip().startswith('assign ') and FAST_NET in line:
            errors.append('Unreviewed alias of the fast DDR clock')
    return dict(passed=not errors,errors=errors,uses=uses)


def freeze(source,reference_route):
    source=Path(source);reference_route=Path(reference_route).resolve(strict=True)
    selection=json.loads((source/'tang/boards/neo/ddr_variant.json').read_text())
    if selection['variant']!='neo-ddr6-400-fifo-registers':
        raise ValueError('PHY timing experiment requires the explicit DDR6 400 MHz profile')
    if (source/PROFILE).exists():raise ValueError('PHY timing profile already exists')
    ref=REFERENCE.read_bytes()
    reference_clause='set_clock_groups -asynchronous -group [get_clocks {clk_x1}] -group [get_clocks {mem400}] -group [get_clocks {clk}]'
    if reference_clause not in ref.decode():raise ValueError('Sipeed DDR400 reference timing model changed')
    net=reference_route/'impl/pnr/console_neo.vo'
    observed=clock_fanout(net.read_text())
    if not observed['passed']:raise ValueError(observed['errors'])
    sdc=source/'tang/boards/neo/neo.sdc';before=sdc.read_bytes()
    if b'create_clock -name ddr3_mem_clk -period 2.5 ' not in before:
        raise ValueError('Unexpected fast DDR clock')
    after=before+b'\n'+BLOCK.encode()
    evidence=PROFILE.with_name('sipeed_ddr400_reference.sdc.txt')
    (source/evidence).write_bytes(ref)
    record=dict(version=1,reference_path=str(evidence),reference_sha256=sha(ref),
        reference_url='https://github.com/sipeed/TangMega-138KPro-example/blob/d3cebf1703f1bcd06dca8a53bf2b660c86a5ec16/ddr_test/Hynix_400MHz/src/ddr3_1v4_hs.sdc',
        before_sdc_sha256=sha(before),after_sdc_sha256=sha(after),
        observed_route=str(reference_route),observed_netlist_sha256=sha(net.read_bytes()),
        scope=__doc__)
    sdc.write_bytes(after);(source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')


def audit(source,netlist):
    source=Path(source);netlist=Path(netlist)
    r=json.loads((source/PROFILE).read_text());sdc=(source/'tang/boards/neo/neo.sdc').read_bytes()
    result=clock_fanout(netlist.read_text());errors=result['errors']
    if r.get('version')!=1 or sha(sdc)!=r['after_sdc_sha256']:
        errors.append('Changed PHY timing constraint profile')
    if not sdc.endswith(b'\n'+BLOCK.encode()) or sha(sdc[:-(len(BLOCK.encode())+1)])!=r['before_sdc_sha256']:
        errors.append('PHY timing change exceeds the two declared clock-pair exceptions')
    if sha((source/r['reference_path']).read_bytes())!=r['reference_sha256']:
        errors.append('Changed Sipeed DDR400 timing evidence')
    result.update(passed=not errors,scope=__doc__,netlist_sha256=sha(netlist.read_bytes()))
    return result

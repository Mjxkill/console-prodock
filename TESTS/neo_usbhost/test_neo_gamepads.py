"""Two real wire-level USB hosts and coherent AHB snapshots, no fake pad RTL."""
from pathlib import Path
import shutil
from types import SimpleNamespace
import cocotb
from cocotb.triggers import Timer, FallingEdge, RisingEdge, with_timeout
from cocotb.runner import get_runner, get_results
from test_usb_gamepad_host import device, RTL
HERE=Path(__file__).resolve().parent

async def read(d,address):
    await FallingEdge(d.clk)
    d.hsel.value=1;d.htrans.value=2;d.haddr.value=address
    await RisingEdge(d.clk);await Timer(1,units="ns")
    value=int(d.hrdata.value)
    await FallingEdge(d.clk);d.hsel.value=0;d.htrans.value=0
    return value

@cocotb.test()
async def independent_ports(d):
    d.rst.value=1;d.hsel.value=0;d.hwrite.value=0;d.htrans.value=0;d.haddr.value=0
    pads=[]
    for p in range(2):
        fields={n:getattr(d,f"p{p}_{n}") for n in
                ("attach","dev_drive","dev_dp","dev_dm","dp","dm","host_oe","status","identity","report_count")}
        pad=SimpleNamespace(**fields);pad.attach.value=0;pad.dev_drive.value=0
        pad.dev_dp.value=0;pad.dev_dm.value=1;pads.append(pad)
    await Timer(200,units="ns");d.rst.value=0
    assert await read(d,0)==0x4e504144
    assert await read(d,4)==0x00010002
    # Pull-up strengths are modeled with Verilog pullup, as in the single
    # port bench. Hold port 2 at SE0 for 200 ms to stagger attachment.
    pads[1].dev_drive.value=1;pads[1].dev_dm.value=0
    async def delayed_pad():
        await Timer(200,units="ms")
        pads[1].dev_dm.value=1;pads[1].dev_drive.value=0
        await device(pads[1],[])
    tasks=[cocotb.start_soon(device(pads[0],[])),cocotb.start_soon(delayed_pad())]
    for p,pad in enumerate(pads):
        task=tasks[p]
        while int(pad.report_count.value)<2:await Timer(1,units="ms")
        status=await read(d,32*(p+1))
        assert status&9==9
        count=await read(d,32*(p+1)+8)
        report=(await read(d,32*(p+1)+16)<<32)|await read(d,32*(p+1)+12)
        await with_timeout(task,900,"ms")
        assert await read(d,32*(p+1)+8)==count, "snapshot mutated without STATUS read"
        assert ((await read(d,32*(p+1)+16)<<32)|await read(d,32*(p+1)+12))==report
        await read(d,32*(p+1))
        assert await read(d,32*(p+1)+4)==0xe401081f
        assert await read(d,32*(p+1)+8)>=7
        if p==0:
            assert not int(pads[1].report_count.value)
            assert not int(pads[1].status.value)&1
        else:assert int(pads[0].report_count.value)==7
    d._log.info("PASS two independent hosts, physical packet validation and frozen AHB reports")

if __name__=="__main__":
    out=HERE/'sim_build_two';out.mkdir(exist_ok=True)
    rom=out/'rtl/usbhost/usb_hid_host_rom.hex';rom.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(RTL/'usb_hid_host_rom.hex',rom)
    r=get_runner('verilator')
    r.build(sources=[HERE/'neo_gamepads_tb.sv',RTL.parent/'neo_gamepads.v',*sorted(RTL.glob('*.v'))],
            hdl_toplevel='neo_gamepads_tb',build_dir=out,
            build_args=['--timing','-Wno-fatal'])
    result=r.test(hdl_toplevel='neo_gamepads_tb',test_module='test_neo_gamepads')
    count,failed=get_results(result)
    if count!=1 or failed:raise SystemExit('two-host integration failed')

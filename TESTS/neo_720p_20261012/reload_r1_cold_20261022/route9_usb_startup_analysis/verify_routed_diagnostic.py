#!/usr/bin/env python3
"""Read-only structural proof of the existing Neo EP0 startup diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILDS = {
    'n56r8': ('console_neo_n56r8_hdmi_sg4',
        '51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35',
        '33c919d5c8ab6e90ec6b68f44849ff9d6f2c5682a40192d12c55298494afccc9'),
    'r9': ('console_neo_n56r9_route9_dma_c150',
        '1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde',
        'd3888d979ae0195b6e0f806e4baa0c255fa5ce288953541090f85d0dc4736b77')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cell(text, name):
    spelling = ('\\' if '/' in name else '') + name
    found = list(re.finditer(r'^([A-Z][A-Z0-9_]*) ' + re.escape(spelling) +
        r'\s*\(\s*(.*?)\n\);', text, re.M | re.S))
    assert len(found) == 1, name
    match = found[0]
    pins = {k: v.replace('\\', '').strip() for k, v in re.findall(
        r'\.(\w+)\(([^)]*)\)', match.group(2))}
    params = dict(re.findall(r'^defparam ' + re.escape(spelling) +
        r'\s*\.(\w+)=([^;]+);', text, re.M))
    return dict(kind=match.group(1), pins=pins, parameters=params,
                line=text.count('\n', 0, match.start()) + 1)


def verify():
    result = dict(passed=False, hardware_access=False, bitstream_sha256={},
                  input_sha256={}, builds={}, request=[0xa0, 0x21, 0xd1a6, 0, 32])
    for label, (directory, bit_sha, vo_sha) in BUILDS.items():
        build = ROOT / 'tang/impl' / directory
        bit = build / 'impl/pnr/console_neo.fs'
        vo = build / 'impl/pnr/console_neo.vo'
        assert sha(bit) == bit_sha and sha(vo) == vo_sha
        result['bitstream_sha256'][label] = bit_sha
        manifest_path = build / 'sources.json'
        manifest = json.loads(manifest_path.read_text())
        paths = [bit, vo, manifest_path]
        source_paths = ['tang/boards/neo/console_neo.v', 'tang/boards/neo/soft_usb.vh',
            'tang/rtl/board/ae350_soc.v', 'tang/rtl/usb/uart/usb_uart_config.v',
            'tang/rtl/usb/usb_descriptor.v']
        for relative in source_paths:
            source = build / 'source' / relative
            assert sha(source) == manifest[relative], source
            paths.append(source)
        for path in paths:
            result['input_sha256'][str(path)] = sha(path)
        top, usb, soc, config = [p.read_text() for p in paths[3:7]]
        assert '`define CONSOLE_USB_DIAG' in top
        assert '.SERIALSTR("NEO00001"), .SERIALSTR_LEN(8)' in usb
        assert '.PRODUCTSTR("MegaNeo Console"), .PRODUCTSTR_LEN(15)' in usb
        assert ".VENDORID(16'h359F), .PRODUCTID(16'h2011)" in usb
        assert 'wire        usb_app_reset = RESET | usb_busreset;' in usb
        assert 'wire        RESET = rst_usb;' in usb
        assert 'diag_board_meta<={pll_ae350_lock,soc_dbg[2:0]};' in usb
        assert "assign dbg = {1'b1, ddr3_stop, ddr3_lock, ae350_rstn};" in soc
        assert 'wire ae350_rstn = init_sync[1];' in soc
        assert "diagnostic_key == 16'hd1a6 || diagnostic_key == 16'hd1a7" in config
        assert 'diagnostic_snapshot <= diagnostic_data;' in config
        assert 'diagnostic_page[(sub_stage+1)*8 +: 8]' in config
        body = vo.read_text()
        selected = {}
        def get(name):
            value = cell(body, name)
            selected[name] = value
            return value
        alias = 'soc_dbg_144[1]' if label == 'n56r8' else 'soc_dbg_177[1]'
        sources = ['soc_dbg[0]', alias, 'soc_dbg_2_3', 'pll_ae350_lock']
        for n, net in enumerate(sources):
            for prefix, source in [('meta', net), ('sync', f'diag_board_meta[{n}]')]:
                item = get(f'diag_board_{prefix}_{n}_s0')
                assert item['kind'] == 'DFFCE' and item['parameters'] == dict(INIT="1'b0")
                assert item['pins'] == dict(D=source, CLK='phy_clk', CE='VCC',
                    CLEAR='usb_app_reset', Q=f'diag_board_{prefix}[{n}]')
            item = get(f'u_usb_uart_config/diagnostic_snapshot_{156+n}_s0')
            assert item['kind'] == 'DFFCE' and item['parameters'] == dict(INIT="1'b0")
            assert item['pins']['D'] == f'diag_board_sync[{n}]'
            assert item['pins']['CLK'] == 'phy_clk' and item['pins']['CLEAR'] == 'usb_app_reset'
            assert item['pins']['Q'].replace(' ', '') == f'u_usb_uart_config/diagnostic_snapshot[{156+n}]'
        reset = get('usb_app_reset_s1')
        assert reset['kind'] == 'LUT2' and reset['parameters'] == dict(INIT="4'hE")
        assert reset['pins'] == dict(I0='rst_usb', I1='PHY_RESET', F='usb_app_reset')
        # Both USB PLLs are independent of AE350/DDR clock and reset inputs.
        fpll = get('u_pll_f/PLL_inst')
        bpll = get('u_pll_b/PLL_inst')
        assert fpll['pins']['CLKIN'] == 'clk_d' and fpll['pins']['RESET'] == 'GND'
        assert fpll['pins']['CLKOUT0'] == 'clk48' and fpll['pins']['LOCK'] == 'pll_f_lock'
        assert bpll['pins']['CLKIN'] == 'clk48' and bpll['pins']['RESET'] == 'pll_b_reset'
        assert bpll['pins']['CLKOUT1'] == 'phy_clk' and bpll['pins']['LOCK'] == 'pll_b_lock'
        for prefix, clock, reset_output in [('u_usb_ref_start', 'clk_d', 'pll_b_reset'),
                ('u_usb_phy_start', 'clk_d', 'phy_lock_reset'),
                ('u_usb_controller_start', 'phy_clk', 'rst_usb')]:
            item = get(prefix + '/reset_s4')
            assert item['kind'] == 'DFFPE' and item['parameters'] == dict(INIT="1'b1")
            assert item['pins']['CLK'] == clock and item['pins']['Q'] == reset_output
        rst = get('u_soc/init_sync_1_s0')
        assert rst['pins']['Q'] == 'soc_dbg[0]'
        hard = get('u_soc/u_ae350/u_RiscV_AE350_SOC/u_AE350_SOC')
        assert hard['pins']['POR_N'] == hard['pins']['HW_RSTN'] == 'soc_dbg[0]'
        result['builds'][label] = dict(build=str(build), primitives=selected,
            signature_byte_offset=23, board_nibble_byte=19, board_nibble_shift=4,
            board_bits=['ae350_por_hw_rstn', 'pll_ddr_filtered_lock', 'ddr3_stop_enclk2',
                        'pll_ae350_filtered_lock'])
    result['passed'] = True
    result['limits'] = ['Structural proof, not hardware qualification or USB enumeration evidence.',
        'USB PLL/reset independence does not guarantee that a cable/PHY/host link works.',
        'The USB snapshot supplies levels, not clock activity or a transient log.']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    with args.out.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps(dict(passed=True, hardware_access=False,
                         primitives={k:len(v['primitives']) for k,v in result['builds'].items()},
                         output_sha256=sha(args.out))))

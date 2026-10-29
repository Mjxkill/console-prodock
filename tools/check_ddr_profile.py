#!/usr/bin/env python3
"""Check the shared DDR implementation against the frozen Pro Dock reference."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'tang/boards/ddr_prodock.json'
TAGGED_PROFILE = 'tang/boards/neo/ddr_tagged.json'
SELECTION = 'tang/boards/neo/ddr_variant.json'
ADAPTER = 'tang/rtl/board/ddr_ui_adapt.v'
TAGGED_SOURCE = 'tang/boards/neo/ddr_ui_adapt.v'
SPLIT_PROFILE = 'tang/boards/neo/ddr_tagged_split.json'
SPLIT_SOURCE = 'tang/boards/neo/ddr_ui_adapt_split.v'
FIFO = 'tang/rtl/board/ddr_dcfifo.v'
FIFO_PROFILE = 'tang/boards/neo/ddr_fifo_registers.json'
FIFO_SOURCE = 'tang/boards/neo/ddr_dcfifo_registers.v'
OVERRIDES = {'neo-tagged': (TAGGED_PROFILE, TAGGED_SOURCE),
             'neo-tagged-split': (SPLIT_PROFILE, SPLIT_SOURCE),
             'neo-fifo-registers': (FIFO_PROFILE, FIFO_SOURCE)}
DESTINATIONS = {'neo-tagged': ADAPTER, 'neo-tagged-split': ADAPTER,
                'neo-fifo-registers': FIFO}
IP_VARIANT = 'neo-ddr6-fifo-registers'
IP_PROFILE = 'tang/boards/neo/ddr6.json'
IP_ROOT = 'tang/boards/neo/ddr6'
IP300_VARIANT = 'neo-ddr6-300-fifo-registers'
IP325_VARIANT = 'neo-ddr6-325-fifo-registers'
IP400_VARIANT = 'neo-ddr6-400-fifo-registers'
IP_CLOCK_MHZ = {IP300_VARIANT:300, IP325_VARIANT:325, IP400_VARIANT:400}
IP_PROFILES = {IP_VARIANT: (IP_PROFILE, IP_ROOT),
               IP300_VARIANT: ('tang/boards/neo/ddr6_300.json', 'tang/boards/neo/ddr6_300'),
               IP325_VARIANT: ('tang/boards/neo/ddr6_325.json', 'tang/boards/neo/ddr6_325'),
               IP400_VARIANT: ('tang/boards/neo/ddr6_400.json', 'tang/boards/neo/ddr6_400')}
PLL325_CHANGES = {
    'tang/rtl/board/gowin_pll_ddr3.v': [('MULTI_FAC = 24;', 'MULTI_FAC = 26;')],
    'tang/rtl/board/gowin_pll_ddr3_mod.v': [('MDIV_SEL = 24;', 'MDIV_SEL = 26;'),
                                         ('1200/4 = 300 MHz', '1300/4 = 325 MHz')]}
PLL400_CHANGES = {
    'tang/rtl/board/gowin_pll_ddr3_mod.v': [('ODIV2_SEL = 4;', 'ODIV2_SEL = 3;'),
                                         ('1200/4 = 300 MHz', '1200/3 = 400 MHz'),
                                         ('400 MHz ne calibre pas de façon fiable, TESTS_V3 §E1',
                                          'nouvel essai avec reset explicite; historique TESTS_V3 §E1')]}
PLL_CHANGES = {IP325_VARIANT: PLL325_CHANGES, IP400_VARIANT: PLL400_CHANGES}
IP_DESTINATIONS = {
    'ddr3_standalone.v': 'tang/rtl/board/ddr3_standalone_32b/ddr3_standalone.v',
    **{name: 'tang/rtl/board/ddr3_standalone_32b/cfg/'+name
       for name in ('gwmc_param.v','ddr3_name.v','DDR3_define.v')}}
VARIANTS = ('prodock', *OVERRIDES, *IP_PROFILES)


def hynix_efr_clock_range(parameters, clock_mhz):
    """Nominal CL6/CWL5 operating point for the observed H5TQ4G63EFR-RDC.

    SK hynix Rev. 1.2, September 2016, DDR3-1866 table and note 3:
    tCK(AVG) is 2.5..3.3 ns. This is not a full electrical qualification.
    In particular, rounding 3.333 ns to 3.3 would hide an unsupported point.
    """
    supported=(parameters.get('CL')=='6' and parameters.get('CWL')=='5')
    period=1000/clock_mhz if clock_mhz>0 else None
    errors=[]
    if not supported:errors.append('Unverified EFR CL/CWL operating range')
    if period is None or not 2.5<=period<=3.3:
        errors.append('Nominal DDR clock outside EFR CL6/CWL5 tCK range 2.5..3.3 ns')
    return dict(passed=not errors,errors=errors,part='H5TQ4G63EFR-RDC',
                tck_ns=period,tck_min_ns=2.5,tck_max_ns=3.3,
                scope='Nominal clock range only; electrical and board tests still required')


def ip_record(root, baseline, variant=IP_VARIANT):
    ip_profile, ip_root = IP_PROFILES[variant]
    record = json.loads((Path(root) / ip_profile).read_text())
    required = {destination: ip_root+'/'+name for name,destination in IP_DESTINATIONS.items()}
    if variant in PLL_CHANGES:
        required.update({dest:ip_root+'/'+Path(dest).name for dest in PLL_CHANGES[variant]})
    if (record['base_profile'] != baseline['profile'] or
            record['base_variant'] != 'neo-fifo-registers' or record['ip_version'] != '6.0' or
            set(record['overrides']) != set(required) or
            any(record['overrides'][dest]['source'] != source for dest,source in required.items()) or
            record.get('profile') != variant or
            set(record['evidence']) != {ip_root+'/generation.json'}):
        raise ValueError('DDR6 override exceeds the declared IP/configuration scope')
    evidence=json.loads((Path(root)/(ip_root+'/generation.json')).read_text())
    wanted = dict(evidence.get('baseline_parameters', {}))
    if variant in IP_CLOCK_MHZ:
        clock = IP_CLOCK_MHZ[variant]
        wanted['tCK'] = str(1000000//clock)
        changes={k:v for k,v in wanted.items() if evidence['baseline_parameters'].get(k)!=v}
        if (evidence.get('parameter_overrides') != changes or
                evidence.get('expected_parameters') != wanted or
                evidence.get('options', {}).get('Memory_Clock') != str(clock) or
                evidence.get('options', {}).get('AXI4_Interface') != 'false'):
            raise ValueError('DDR6 clock profile changes more than the declared memory period')
    if variant in PLL_CHANGES:
        for dest, changes in PLL_CHANGES[variant].items():
            text=(Path(root)/required[dest]).read_text()
            for old,new in changes:
                if text.count(new)!=1:raise ValueError('Unknown explicit PLL configuration')
                text=text.replace(new,old,1)
            if hashlib.sha256(text.encode()).hexdigest()!=baseline['files'][dest]:
                raise ValueError('PLL changes exceed the declared frequency profile')
    net=IP_DESTINATIONS['ddr3_standalone.v']
    if (evidence.get('passed') is not True or evidence.get('ip_version') != '6.0' or
            evidence.get('part') != 'GW5AST-LV138PG484AC1/I0' or
            evidence.get('netlist_sha256') != record['overrides'][net]['sha256'] or
            evidence.get('baseline_netlist_sha256') != baseline['files'][net] or
            not evidence.get('baseline_parameters') or
            any(evidence.get('generated_parameters',{}).get(k)!=v
                for k,v in wanted.items())):
        raise ValueError('DDR6 generation did not preserve the declared baseline/interface')
    return record


def tagged_record(root, baseline, variant='neo-tagged'):
    profile, source = OVERRIDES[variant]
    record = json.loads((Path(root) / profile).read_text())
    if (record['base_profile'] != baseline['profile'] or
            record['source'] != source or record['destination'] != DESTINATIONS[variant]):
        raise ValueError('DDR override does not match its explicitly allowed source/destination')
    return record


def freeze_variant(root, destination, variant):
    """Override the isolated build copy only; never edit the Pro Dock source."""
    if variant not in VARIANTS:
        raise ValueError('Unknown DDR variant')
    root, destination = Path(root), Path(destination)
    baseline = json.loads((root / PROFILE).read_text())
    if variant in IP_PROFILES:
        ip_profile, _ = IP_PROFILES[variant]
        record = ip_record(root, baseline, variant)
        copies = {item['source']:item['sha256'] for item in record['overrides'].values()}
        copies.update(record['evidence'])
        for rel,digest in copies.items():
            if hashlib.sha256((root/rel).read_bytes()).hexdigest() != digest:
                raise ValueError('DDR6 candidate input changed: '+rel)
        freeze_variant(root, destination, 'neo-fifo-registers')
        for rel in [ip_profile, *copies]:
            target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(root/rel,target)
        for dest,item in record['overrides'].items():
            target=destination/dest;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(root/item['source'],target)
        (destination/SELECTION).write_text(json.dumps({'variant':variant},indent=2)+'\n')
        result=audit(destination,variant)
        if not result['passed']:
            raise ValueError('Frozen DDR6 variant differs: '+str(result['changed']))
        return
    if variant in OVERRIDES:
        profile, source = OVERRIDES[variant]
        record = tagged_record(root, baseline, variant)
        origin = root / source
        if hashlib.sha256(origin.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Neo DDR override does not match its recorded source')
    shutil.copy2(root / PROFILE, destination / PROFILE)
    if variant in OVERRIDES:
        shutil.copy2(root / profile, destination / profile)
        shutil.copy2(origin, destination / source)
        shutil.copy2(origin, destination / record['destination'])
    (destination / SELECTION).write_text(json.dumps({'variant': variant}, indent=2)+'\n')
    result = audit(destination, variant)
    if not result['passed']:
        raise ValueError('Frozen DDR variant differs: '+str(result['changed']))


def audit(root=ROOT, variant='prodock', system_reset=False, ddr_startup=False):
    if variant not in VARIANTS:
        raise ValueError('Unknown DDR variant')
    root = Path(root)
    record = json.loads((root / PROFILE).read_text())
    expected_files = dict(record['files'])
    profile, scope = record['profile'], record['scope']
    base_variant = 'neo-fifo-registers' if variant in IP_PROFILES else variant
    if base_variant in OVERRIDES:
        override = tagged_record(root, record, base_variant)
        expected_files[override['destination']] = override['sha256']
        expected_files[OVERRIDES[base_variant][1]] = override['sha256']
        profile, scope = override['profile'], override['scope']
    if variant in IP_PROFILES:
        override=ip_record(root,record,variant)
        for dest,item in override['overrides'].items():
            expected_files[dest]=item['sha256']
            expected_files[item['source']]=item['sha256']
        expected_files.update(override['evidence'])
        profile,scope=override['profile'],override['scope']
    changed = []
    for rel, expected in expected_files.items():
        path = root / rel
        data=path.read_bytes() if path.is_file() else b''
        if system_reset and rel=='tang/rtl/board/ae350_soc.v':
            from neo.system_reset import original_soc
            try:data=original_soc(root)
            except (ValueError,KeyError,FileNotFoundError):
                changed.append(rel);continue
        if ddr_startup and rel=='tang/rtl/board/ae350_soc.v':
            from neo.ddr_startup import original_soc
            try:data=original_soc(root,data)
            except (ValueError,KeyError,FileNotFoundError):
                changed.append(rel);continue
        if not path.is_file() or hashlib.sha256(data).hexdigest() != expected:
            changed.append(rel)
    return dict(passed=not changed, profile=profile, variant=variant,
                base_profile=record['profile'],
                reference_bitstream_sha256=record['reference_bitstream_sha256'],
                verified_files=len(expected_files) - len(changed), changed=changed,
                system_reset_baseline_reconstructed=system_reset,
                ddr_startup_baseline_reconstructed=ddr_startup,
                scope=scope)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--variant', choices=VARIANTS, default='prodock')
    args = parser.parse_args()
    result = audit(args.root, args.variant)
    text = json.dumps(result, indent=2) + '\n'
    if args.out:
        args.out.write_text(text)
    print(text, end='')
    if not result['passed']:
        raise SystemExit('DDR differs from the Pro Dock reference')

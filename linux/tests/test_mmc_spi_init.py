#!/usr/bin/env python3
"""Exercise real Linux mmc_spi_set_ios before/after the clock-order patch.

Only a temporary copy is patched (--fuzz=0). The compiled translation unit
contains the exact extracted function bodies and explicit mock dependencies.
The adapter mock distinguishes attempted transfers from accepted data after
setup failure. It is not a test of the complete Linux SPI/MMC stack or hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'linux/tests/vendor/mmc_spi.c'
REFERENCE_SHA = '33997892d8f86f31d774959a375b05705b96c8c8d75f9c64f95def9237318b3c'
PATCH = ROOT/'linux/patches/linux/0002-mmc-spi-clock-before-power-on.patch'

PREAMBLE = r'''
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned char u8;
enum {MMC_POWER_OFF, MMC_POWER_UP, MMC_POWER_ON};
enum {SPI_CPHA=1, SPI_CPOL=2, SPI_CS_HIGH=4};
struct device {int unused;};
struct spi_device {struct device dev; unsigned max_speed_hz, mode;};
struct platform_data {void (*setpower)(struct device *,unsigned);};
struct mmc_spi_host {struct spi_device *spi; struct platform_data *pdata;
                     unsigned power_mode, powerup_msecs;};
struct mmc_host {struct mmc_spi_host *private;};
struct mmc_ios {unsigned power_mode, clock, vdd;};
static unsigned configured, setup_calls, clock_changes, init_calls;
static unsigned attempted_data, accepted_data, sleeps, power_calls;
static int setup_error, fail_setup;
static void *mmc_priv(struct mmc_host *mmc) {return mmc->private;}
static const char *mmc_powerstring(unsigned power) {(void)power; return "mock";}
static void dev_dbg(struct device *dev,const char *format,...)
{(void)dev; (void)format;}
static void msleep(unsigned ms) {sleeps+=ms;}
static void power(struct device *dev,unsigned vdd) {(void)dev; (void)vdd; ++power_calls;}
/* Mock exactly the adapter policy needed by this test: a failed setup blocks
 * accepted data. Repeated successful setup at the same rate is idempotent.
 * This is an explicit assumption, not a qualification of the real adapter.
 */
static int spi_setup(struct spi_device *spi)
{
    ++setup_calls;
    if (fail_setup) {setup_error=-EIO; return setup_error;}
    if (configured != spi->max_speed_hz) {
        configured=spi->max_speed_hz; ++clock_changes;
    }
    setup_error=0;
    return 0;
}
static int spi_write(struct spi_device *spi,const void *data,unsigned n)
{
    (void)spi; (void)data; ++attempted_data;
    if (setup_error) return setup_error;
    accepted_data+=n; return 0;
}
/* Observe the effective adapter rate at entry, before simulating init data.
 * The real initsequence has additional SPI setup calls and protocol traffic;
 * its internal implementation is deliberately outside this unit-test scope.
 */
static void mmc_spi_initsequence(struct mmc_spi_host *host)
{
    ++init_calls;
    if (!setup_error && configured != 400000) {
        fprintf(stderr,"CLOCK_ORDER_FAILURE: initsequence sees %u instead of 400000\n",configured);
        exit(9);
    }
    (void)spi_write(host->spi,"x",1);
}
'''
MAIN = r'''
int main(void)
{
    struct spi_device spi={.max_speed_hz=20000000,.mode=3};
    struct mmc_spi_host host={.spi=&spi,.power_mode=MMC_POWER_OFF,.powerup_msecs=3};
    struct mmc_host mmc={.private=&host};
    struct mmc_ios ios={.power_mode=MMC_POWER_UP,.clock=0,.vdd=1};
    configured=20000000;
    mmc_spi_set_ios(&mmc,&ios);
    assert(host.power_mode==MMC_POWER_UP && init_calls==0);
    assert(setup_calls==0 && configured==20000000);
    ios.power_mode=MMC_POWER_ON; ios.clock=400000;
    mmc_spi_set_ios(&mmc,&ios);
    assert(configured==400000 && init_calls==1 && accepted_data==1);
    assert(clock_changes==1 && setup_calls==1);
    /* Same IOS and repeated cs_off must not reprogram the same rate. */
    mmc_spi_set_ios(&mmc,&ios);
    unsigned previous=clock_changes;
    assert(mmc_cs_off(&host)==0 && mmc_cs_off(&host)==0);
    assert(clock_changes==previous && init_calls==1);
    ios.clock=20000000;
    mmc_spi_set_ios(&mmc,&ios);
    assert(configured==20000000 && clock_changes==2 && init_calls==1);
    ios.clock=0;
    mmc_spi_set_ios(&mmc,&ios);
    assert(configured==20000000 && clock_changes==2);
    /* Optional board power callback remains ordered and functional. */
    struct platform_data pdata={.setpower=power}; host.pdata=&pdata;
    ios.power_mode=MMC_POWER_OFF;
    mmc_spi_set_ios(&mmc,&ios);
    ios.power_mode=MMC_POWER_UP;
    mmc_spi_set_ios(&mmc,&ios);
    assert(power_calls==2 && sleeps==13 && configured==20000000);
    ios.power_mode=MMC_POWER_ON; ios.clock=400000;
    mmc_spi_set_ios(&mmc,&ios);
    assert(configured==400000 && clock_changes==3 && init_calls==2);
    /* Persistent setup error: MMC still calls initsequence; only the adapter
     * mock's error gate guarantees no accepted bytes. Do not conflate them. */
    host.power_mode=MMC_POWER_UP; host.pdata=0;
    spi.max_speed_hz=configured=20000000;
    fail_setup=1;
    unsigned accepted_before=accepted_data, attempts_before=attempted_data;
    mmc_spi_set_ios(&mmc,&ios);
    assert(setup_error==-EIO && configured==20000000);
    assert(init_calls==3 && attempted_data==attempts_before+1);
    assert(accepted_data==accepted_before && host.power_mode==MMC_POWER_ON);
    puts("PASS: POWER_UP clock0, 400k before init, 20M/powercycle/400k, cs_off idempotence");
    puts("LIMIT: setup failure still invokes initsequence; mock adapter rejects accepted data");
    return 0;
}
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(text, name):
    """Find the real body, ignoring braces inside comments and strings."""
    pattern = r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    masked = re.sub(pattern, lambda m: ' '*len(m.group()), text, flags=re.S)
    found = re.search(r'^static[^;{}]*\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',
                      masked, re.M)
    if not found:
        raise ValueError('Function not found: '+name)
    start = found.start(); brace = masked.index('{', start); depth = 0
    for index in range(brace, len(masked)):
        depth += (masked[index]=='{') - (masked[index]=='}')
        if depth == 0:
            return text[start:index+1]
    raise ValueError('Unclosed function: '+name)


def check(source, patch):
    started = time.monotonic()
    report = {'passed': False, 'hardware': False, 'kernel_build': False,
              'source_sha256': sha(source), 'reference_sha256': REFERENCE_SHA,
              'patch_sha256': sha(patch), 'commands': []}
    try:
        original = source.read_text()
        with tempfile.TemporaryDirectory(prefix='mmc-spi-init-') as directory:
            temp = Path(directory)
            target = temp/'drivers/mmc/host/mmc_spi.c'
            target.parent.mkdir(parents=True); target.write_text(original)
            def execute(command):
                result = subprocess.run(command, cwd=temp, text=True,
                                        capture_output=True, timeout=30)
                report['commands'].append({'argv':command,'returncode':result.returncode,
                                           'stdout':result.stdout,'stderr':result.stderr})
                return result
            # prepare() may already have patched the SDK. Derive the exact
            # pinned original in temporary storage; never edit that live tree.
            report['source_already_patched'] = sha(source) != REFERENCE_SHA
            if report['source_already_patched']:
                reverse = execute(['patch','--batch','--fuzz=0','--reverse','-p1',
                                   '-i',str(patch.resolve())])
                if reverse.returncode or sha(target) != REFERENCE_SHA:
                    raise ValueError('Source is neither the pinned original nor its patched version')
                original = target.read_text()
            applied = execute(['patch','--batch','--fuzz=0','-p1','-i',str(patch.resolve())])
            if applied.returncode:
                raise ValueError('Patch application failed')
            if 'offset' in applied.stdout.lower() or 'fuzz' in applied.stdout.lower():
                raise ValueError('Patch did not apply at exact expected lines')
            report['patched_sha256'] = sha(target)
            for variant,text in [('original',original),('patched',target.read_text())]:
                bodies = '\n\n'.join(extract(text,name) for name in ('mmc_cs_off','mmc_spi_set_ios'))
                unit = temp/(variant+'.c'); unit.write_text(PREAMBLE+'\n'+bodies+'\n'+MAIN)
                if len(unit.read_text().splitlines()) > 1000:
                    raise ValueError('Generated translation unit exceeds 1000 lines')
                report[variant+'_function_sha256'] = hashlib.sha256(bodies.encode()).hexdigest()
                binary = temp/variant
                built = execute(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                                 '-fsanitize=undefined','-fno-sanitize-recover=all',
                                 str(unit),'-o',str(binary)])
                if built.returncode:
                    raise ValueError(variant+' compilation failed')
                result = execute([str(binary)])
                if variant == 'original':
                    report['initial_counterexample'] = (result.returncode==9 and
                        'CLOCK_ORDER_FAILURE: initsequence sees 20000000 instead of 400000' in result.stderr)
                    if not report['initial_counterexample']:
                        raise ValueError('Original did not reproduce the clock-order defect')
                elif result.returncode or not result.stdout.startswith('PASS:'):
                    raise ValueError('Patched behavior failed')
            report['passed'] = True
    except (ValueError,OSError,subprocess.TimeoutExpired) as error:
        report['error'] = str(error)
    report['elapsed_seconds'] = time.monotonic()-started
    report['source_unchanged'] = sha(source)==report['source_sha256']
    report['passed'] = report['passed'] and report['source_unchanged']
    report['limits'] = ['Only extracted set_ios/cs_off are real Linux code; initsequence body is a clock observer',
                        'No kernel, hardware, SD electrical timing or full stack validation',
                        'No accepted data after setup failure depends on the explicit mock adapter error gate']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--patch', type=Path, default=PATCH)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = check(args.source.resolve(),args.patch.resolve())
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2)+'\n')
    for command in result['commands']:
        print(command['stdout'],end=''); print(command['stderr'],end='')
    print(json.dumps({k:v for k,v in result.items() if k!='commands'}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compile the actual U-Boot SPI driver with a bounded MMIO/shifter model.

Generated headers declare U-Boot types/API only. The real driver, shared core
and model are three separately compiled objects, joined by the normal driver
descriptor and U-Boot's readl/writel/get_timer API. No hardware access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUB = r'''
#ifndef TEST_UBOOT_DM_H
#define TEST_UBOOT_DM_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef unsigned uint;
typedef unsigned long ulong;
#define __iomem
#define BIT(n) (1U << (n))
#define min(a,b) ((a) < (b) ? (a) : (b))
#define DIV_ROUND_UP(a,b) (((a) + (b) - 1) / (b))
#define SPI_MODE_0 0
#define SPI_XFER_BEGIN 1U
#define SPI_XFER_END 2U
#define UCLASS_SPI 1
struct udevice { struct udevice *parent; void *priv, *base, *gpio; unsigned cs; };
void *dev_get_priv(struct udevice *d);
void *dev_read_addr_index_ptr(struct udevice *d, unsigned i);
unsigned spi_chip_select(struct udevice *d);
struct dm_spi_ops {
 int (*claim_bus)(struct udevice *); int (*release_bus)(struct udevice *);
 int (*xfer)(struct udevice *, unsigned, const void *, void *, unsigned long);
 int (*set_speed)(struct udevice *, unsigned); int (*set_mode)(struct udevice *, unsigned);
};
struct udevice_id { const char *compatible; };
struct test_driver {
 const char *name; int id; const struct udevice_id *of_match;
 int (*probe)(struct udevice *); const struct dm_spi_ops *ops; size_t priv_auto;
};
#define U_BOOT_DRIVER(name) struct test_driver name
extern struct test_driver prodock_spi;
u32 readl(const volatile void *p);
void writel(u32 value, volatile void *p);
ulong get_timer(ulong start);
#endif
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(driver, header, core):
    model = HERE / 'spi_uboot_model.c'
    report = dict(passed=False, hardware=False, physical_clock_measured=False,
                  inputs={str(p): digest(p) for p in (driver, header, core, model, Path(__file__))},
                  linkage='three separately compiled objects',
                  core_platform='PRODOCK_SPI_UBOOT',
                  commands=[])
    with tempfile.TemporaryDirectory(prefix='console-uboot-spi-') as td:
        temp = Path(td)
        (temp / 'dm.h').write_text(STUB)
        for name in ('spi.h', 'time.h', 'asm/io.h', 'linux/delay.h', 'asm/unaligned.h'):
            path = temp / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#include <dm.h>\n')
        # These temporary copies are frozen test inputs, not maintained forks.
        (temp / 'prodock-spi-pio.h').write_bytes(header.read_bytes())
        driver_copy = temp / 'prodock_spi.c'
        driver_copy.write_bytes(driver.read_bytes())
        core_copy = temp / 'prodock-spi-pio.c'
        core_copy.write_bytes(core.read_bytes())
        binary = temp / 'test'
        flags = ['gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-Wno-unused-parameter', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                 '-I' + str(temp), '-DPRODOCK_SPI_UBOOT']
        sources = [driver_copy, core_copy, model]
        objects = [temp / (name + '.o') for name in ('driver', 'core', 'model')]
        commands = [flags + ['-c', str(src), '-o', str(obj)]
                    for src, obj in zip(sources, objects)]
        commands += [flags + [str(obj) for obj in objects] + ['-o', str(binary)], [str(binary)]]
        for command in commands:
            start = time.monotonic()
            result = subprocess.run(command, text=True, capture_output=True, timeout=30)
            report['commands'].append(dict(argv=command, returncode=result.returncode,
                elapsed_seconds=time.monotonic() - start, stdout=result.stdout, stderr=result.stderr))
            if result.returncode:
                return report
        report['passed'] = 'UBOOT SPI PASS' in report['commands'][-1]['stdout']
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--driver', type=Path, default=ROOT/'linux/uboot/overlay/drivers/spi/prodock_spi.c')
    ap.add_argument('--header', type=Path, default=ROOT/'linux/drivers/prodock-spi-pio.h')
    ap.add_argument('--core', type=Path, default=ROOT/'linux/drivers/prodock-spi-pio.c')
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    report = check(args.driver.resolve(), args.header.resolve(), args.core.resolve())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n')
    for entry in report['commands']:
        print(entry['stdout'], end='')
        print(entry['stderr'], end='')
    print(json.dumps({k:v for k,v in report.items() if k != 'commands'}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

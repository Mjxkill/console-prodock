#!/usr/bin/env python3
"""Exercise the actual driver's open/poll code with captured HID word layout."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
driver = (ROOT / 'linux/drivers/neo-gamepads.c').read_text()
code = '\n'.join(line for line in driver.split('static int neo_gamepads_probe')[0].splitlines()
                 if not line.startswith('#include'))
harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <linux/input.h>
#define __iomem
#define BIT(n) (1U << (n))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
typedef uint32_t u32;
struct input_dev { void *drvdata; int axes[ABS_CNT], keys[KEY_CNT], syncs; };
static void *input_get_drvdata(struct input_dev *d) { return d->drvdata; }
static u32 readl(void *p) { return *(u32 *)p; }
static void input_report_abs(struct input_dev *d, unsigned c, int v) { d->axes[c]=v; }
static void input_report_key(struct input_dev *d, unsigned c, int v) { d->keys[c]=v; }
static void input_sync(struct input_dev *d) { ++d->syncs; }
'''
tests = r'''
int main(void) {
    u32 regs[5]={9,0xe401081f,17,0x8080,1U<<12};
    struct neo_pad pad={.regs=regs,.armed=true};
    struct input_dev dev={.drvdata=&pad};
    assert(!neo_pad_open(&dev));
    neo_pad_poll(&dev); assert(!pad.armed && !dev.keys[BTN_SOUTH]);
    regs[4]=0;neo_pad_poll(&dev);assert(pad.armed);
    regs[4]=1U<<12;neo_pad_poll(&dev);assert(dev.keys[BTN_SOUTH]);
    assert(!neo_pad_open(&dev)); /* close/reopen while still held */
    neo_pad_poll(&dev);assert(!pad.armed && !dev.keys[BTN_SOUTH]);
    regs[4]=0;neo_pad_poll(&dev);assert(pad.armed);
    for(unsigned i=0;i<10;++i) {
        regs[4]=1U<<(12+i);neo_pad_poll(&dev);
        for(unsigned j=0;j<10;++j)assert(dev.keys[neo_keys[j]]==(i==j));
    }
    regs[4]=0;
    const unsigned raw[]={0,63,64,128,191,192,255};
    const int want[]={-1,-1,0,0,0,1,1};
    for(unsigned i=0;i<7;++i) {
        regs[3]=raw[i]|(raw[6-i]<<8);neo_pad_poll(&dev);
        assert(dev.axes[ABS_X]==want[i] && dev.axes[ABS_Y]==want[6-i]);
    }
    regs[0]=0;neo_pad_poll(&dev);
    assert(!pad.armed && !dev.axes[ABS_X] && !dev.axes[ABS_Y]);
    regs[0]=9;regs[3]=0x8080;regs[1]=0x12345678;neo_pad_poll(&dev);
    assert(!pad.armed); /* unsupported model */
    regs[1]=0xe401081f;neo_pad_poll(&dev);assert(pad.armed);
    u32 regs2[5]={9,0xe401081f,1,0x8080,0};
    struct neo_pad pad2={.regs=regs2};struct input_dev dev2={.drvdata=&pad2};
    neo_pad_open(&dev2);neo_pad_poll(&dev2);assert(pad2.armed);
    regs[4]=1U<<21;neo_pad_poll(&dev);assert(dev.keys[BTN_START]);
    neo_pad_poll(&dev2);assert(!dev2.keys[BTN_START]);
    assert(dev.syncs && dev2.syncs);
    puts("PASS Neo input driver: reopen held button, all keys, axis thresholds, offline/unsupported, independent ports");
}
'''
with tempfile.TemporaryDirectory(prefix='console-neo-pad-') as temp:
    source = Path(temp) / 'test.c'
    binary = Path(temp) / 'test'
    source.write_text(harness + code + tests)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                    '-fsanitize=undefined', '-fno-sanitize-recover=all',
                    str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    # Musl uses 64-bit time_t even on RV32, while the kernel's evdev wire ABI
    # still uses two 32-bit timestamp words. Check the actual target headers.
    source.write_text('''#include <stddef.h>
#include <linux/input.h>
_Static_assert(sizeof(struct input_event)==16, "RV32 evdev event size");
_Static_assert(offsetof(struct input_event,type)==8, "RV32 evdev type offset");
_Static_assert(offsetof(struct input_event,value)==12, "RV32 evdev value offset");
''')
    for build in ('build', 'build-neo'):
        cc = ROOT / 'linux' / build / 'userbin/riscv32-prodock-linux-gcc'
        subprocess.run([str(cc), '-std=c11', '-Werror', '-c', str(source),
                        '-o', str(Path(temp) / (build + '.o'))], check=True)
    print('PASS RV32 evdev ABI with both target toolchains: 16 bytes, type@8, value@12')

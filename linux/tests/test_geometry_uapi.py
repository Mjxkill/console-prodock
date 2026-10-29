#!/usr/bin/env python3
"""Exercise actual Linux G3D1 validators and SUBMIT gate; no board/kernel build.

Runs the KUnit cases with a small host assertion adapter, compiles the UAPI for
RV32, compares camera bounds to integer division, and tests the actual submit()
function with fake MMIO. The latter proves an absent frontend or a bad command
anywhere in a batch causes zero FIFO writes and does not poison the device.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DRIVERS = ROOT / 'linux/drivers'
SOURCES = ['prodock-uapi.h', 'prodock-validate.h', 'prodock-gpu.c', 'prodock-kunit.c']

KUNIT_ADAPTER = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t u32;
struct kunit { unsigned checks; void *allocations[32]; unsigned allocated; };
struct kunit_case { const char *name; void (*run_case)(struct kunit *); };
struct kunit_suite { const char *name; struct kunit_case *test_cases; };
#define GFP_KERNEL 0
static void *kunit_kzalloc(struct kunit *t, size_t n, int flags) {
    (void)flags; void *p=calloc(1,n); assert(t->allocated<32);
    t->allocations[t->allocated++]=p; return p;
}
#define KUNIT_EXPECT_EQ(t,a,b) do { (t)->checks++; assert((a)==(b)); } while(0)
#define KUNIT_EXPECT_TRUE(t,a) KUNIT_EXPECT_EQ(t,!!(a),1)
#define KUNIT_EXPECT_FALSE(t,a) KUNIT_EXPECT_EQ(t,!!(a),0)
#define KUNIT_ASSERT_NOT_NULL(t,a) KUNIT_EXPECT_TRUE(t,(a)!=NULL)
#define KUNIT_CASE(f) {#f,f}
#define MODULE_LICENSE(s)
#define kunit_test_suite(s) int main(void) { \
    struct kunit t={0}; unsigned cases=0; \
    for(struct kunit_case *c=(s).test_cases;c->run_case;c++,cases++) { \
        c->run_case(&t); printf("PASS %s\n",c->name); } \
    for(unsigned i=0;i<t.allocated;i++) free(t.allocations[i]); \
    printf("KUNIT_HOST_PASS cases=%u checks=%u\n",cases,t.checks); return 0; }
'''

WRAPPER = r'''
#include "prodock-validate.h"
_Static_assert(PRODOCK_ABI==1,"legacy ABI");
_Static_assert(PRODOCK_INFO==0x80305000U,"legacy INFO ioctl");
_Static_assert(PRODOCK_SUBMIT==0x48085001U,"legacy SUBMIT ioctl");
_Static_assert(PRODOCK_PRESENT==0x46205002U,"legacy PRESENT ioctl");
_Static_assert(PRODOCK_GEOMETRY_INFO==0x80205005U,"G3D1 ioctl");
_Static_assert(sizeof(struct prodock_geom_vertex)==32,"vertex record");
_Static_assert(sizeof(struct prodock_geom_face)==32,"face record");
int command(const __u32 *c) { return prodock_command(c); }
int scene(const struct prodock_scene *s,unsigned w,unsigned h) {
    return prodock_scene_valid_for(s,w,h);
}
'''

SUBMIT_STUBS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "prodock-validate.h"
typedef uint32_t u32;
typedef uint64_t u64;
struct prodock_gpu { void *accel,*memory; bool faulted;
    u64 cache_ns,feed_ns,wait_ns,sent; };
static u32 registers[32],memory_word;
static unsigned writes,syncs,reads;
static u32 readl(const void *p) { reads++; return *(const u32 *)p; }
#define readl_relaxed readl
static void writel_relaxed(u32 word,void *p) { (void)word;(void)p;writes++; }
static u64 ktime_get_ns(void) { static u64 clock; return ++clock; }
static int gpu_errors(struct prodock_gpu *p) { (void)p; return 0; }
static int prodock_cache_sync(void) { syncs++;return 0; }
static void usleep_range(unsigned a,unsigned b) { (void)a;(void)b; }
#define wmb() ((void)0)
#define mb() ((void)0)
#define read_poll_timeout(fn,val,cond,delay,timeout,extra,addr) \
    ((val)=0,(cond)?0:-ETIMEDOUT)
#define readl_poll_timeout(addr,val,cond,delay,timeout) \
    ((val)=expected,(cond)?0:-ETIMEDOUT)
'''

SUBMIT_TESTS = r'''
static void check(struct prodock_batch *b,u32 signature,int result,unsigned fifo) {
    struct prodock_gpu p={.accel=registers,.memory=&memory_word};
    memset(registers,0,sizeof(registers));registers[0x48/4]=signature;
    writes=syncs=reads=0;assert(submit(&p,b)==result);assert(writes==fifo);
    assert(!p.faulted);assert(p.sent==fifo/8);assert(syncs==(fifo?2U:0U));
    if(result==-EINVAL||result==-ERANGE)assert(reads==0);
}
int main(void) {
    struct prodock_batch b={.count=1,.commands={{31U<<24,0,65536}}};
    check(&b,0,-EOPNOTSUPP,0);check(&b,0x47334430,-EOPNOTSUPP,0);
    check(&b,PRODOCK_GEOMETRY_SIGNATURE,0,8);
    b.count=2;b.commands[1][0]=34U<<24;
    b.commands[1][1]=PRODOCK_GPU_BASE;b.commands[1][2]=PRODOCK_GPU_BASE+32;
    b.commands[1][3]=(1U<<16)|1;
    check(&b,0,-EOPNOTSUPP,0);check(&b,PRODOCK_GEOMETRY_SIGNATURE,0,16);
    b.commands[1][7]=1;check(&b,PRODOCK_GEOMETRY_SIGNATURE,-EINVAL,0);
    b.commands[1][7]=0;b.commands[1][2]=PRODOCK_GPU_BASE+PRODOCK_GPU_BYTES;
    check(&b,PRODOCK_GEOMETRY_SIGNATURE,-ERANGE,0);
    b=(struct prodock_batch){.count=1,.commands={{22U<<24,
        PRODOCK_GPU_BASE,PRODOCK_GPU_BASE+0x200000,(400U<<16)|240,(1600U<<16)|1600}}};
    check(&b,0,0,8); /* An absent optional frontend does not affect ABI1. */
    b.reserved=1;check(&b,PRODOCK_GEOMETRY_SIGNATURE,-EINVAL,0);
    b.reserved=0;b.count=0;check(&b,PRODOCK_GEOMETRY_SIGNATURE,-EINVAL,0);
    b.count=PRODOCK_BATCH_MAX+1;check(&b,PRODOCK_GEOMETRY_SIGNATURE,-EINVAL,0);
    puts("SUBMIT_GATE_PASS absent/legacy/mixed/atomic_invalid_batch");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    before = {s: hashlib.sha256((DRIVERS / s).read_bytes()).hexdigest() for s in SOURCES}
    report = {'passed': False, 'hardware_validation': False, 'sha256': before}
    out = args.out.resolve() if args.out else None
    if out:
        out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='linux-g3d1-') as directory:
        tmp = Path(directory)
        def run(name, command):
            result = subprocess.run(list(map(str, command)), text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    # LSAN cannot inspect processes under this
                                    # runner's ptrace sandbox; ASAN/UBSAN stay on.
                                    env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
            if out:
                (out / (name + '.log')).write_text(result.stdout)
            if result.stdout:
                print(result.stdout, end='')
            result.check_returncode()

        (tmp / 'kunit').mkdir()
        (tmp / 'kunit/test.h').write_text(KUNIT_ADAPTER)
        flags = ['-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', DRIVERS]
        run('kunit_build', ['cc', *flags, '-fsanitize=address,undefined', '-g',
                            '-I', tmp, DRIVERS / 'prodock-kunit.c', '-o', tmp / 'kunit-host'])
        run('kunit', [tmp / 'kunit-host'])
        driver = (DRIVERS / 'prodock-gpu.c').read_text()
        begin = driver.index('static int submit(')
        end = driver.index('\nstatic int present_raw(', begin)
        (tmp / 'submit.c').write_text(SUBMIT_STUBS + driver[begin:end] + SUBMIT_TESTS)
        run('submit_build', ['cc', *flags, '-fsanitize=address,undefined', '-g',
                            tmp / 'submit.c', '-o', tmp / 'submit-test'])
        run('submit', [tmp / 'submit-test'])
        (tmp / 'validate.c').write_text(WRAPPER)
        run('validator_build', ['cc', *flags, '-shared', '-fPIC', tmp / 'validate.c',
                               '-o', tmp / 'validate.so'])
        lib = ctypes.CDLL(str(tmp / 'validate.so'))
        lib.command.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
        lib.command.restype = ctypes.c_int
        def accepted(words):
            return lib.command((ctypes.c_uint32 * 8)(*words)) == 0
        rng = random.Random(0x47334431)
        for _ in range(30000):
            w, h = rng.randrange(0, 1050), rng.randrange(0, 540)
            x, y = rng.randrange(0, 1050), rng.randrange(0, 540)
            fx, fy = rng.randrange(60000, 0x10010000), rng.randrange(60000, 0x10010000)
            expected = (0 < w <= 1024 and 0 < h <= 512 and x <= w and y <= h and
                        65536 <= fx <= 0x10000000 and 65536 <= fy <= 0x10000000)
            if expected:
                expected = max((x << 32) // fx, ((w-x) << 32) // fx,
                               (y << 32) // fy, ((h-y) << 32) // fy) <= 524288
            c = [32 << 24, 4096, 0x7fffffff, fx, fy, (x << 16) | y, (w << 16) | h, 0]
            assert accepted(c) == expected, c
        # Hardware viewports differ from the physical display in half-resolution mode.
        for width, height in [(800, 480), (1280, 720)]:
            w, h = width // 2, height // 2
            assert accepted([32 << 24, 4096, 1000 << 16, 300 << 16, 300 << 16,
                             (w//2 << 16) | (h//2), (w << 16) | h, 0])
            scene = (ctypes.c_uint32 * 392)()
            scene[0], scene[1], scene[2] = 0x800000, width*2, 7
            assert lib.scene(scene, width, height) == 0
        report['camera_reference_cases'] = 30000
        report['profiles'] = ['prodock_800x480', 'neo_1280x720']
        compiler = ROOT / 'linux/build/userbin/riscv32-prodock-linux-gcc'
        if not compiler.exists():
            raise RuntimeError('Existing RV32 compiler required; no toolchain is installed by this test')
        run('rv32_abi_compile', [compiler, *flags, '-c', tmp / 'validate.c', '-o', tmp / 'validate-rv32.o'])
        report['rv32_abi_compile'] = True
    assert before == {s: hashlib.sha256((DRIVERS / s).read_bytes()).hexdigest() for s in SOURCES}
    report['passed'] = True
    if out:
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

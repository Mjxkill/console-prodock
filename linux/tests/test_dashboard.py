#!/usr/bin/env python3
"""Check dashboard fault/rate semantics and optionally draw native-tile previews.

Preview inputs are fixtures, not measurements from a connected board.
"""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import tempfile

HERE = Path(__file__).resolve().parents[1]
SOURCE = r'''
#include <assert.h>
#include <string.h>
#include "prodock-dashboard.h"
static unsigned colour(const struct prodock_debug_text *t,unsigned x,unsigned y)
{ return (t->cells[y*100+x]>>8)&15; }
static int contains(const struct prodock_debug_text *t,unsigned row,const char *needle)
{
    char line[101];
    for(unsigned x=0;x<100;++x)line[x]=t->cells[row*100+x]&255;
    line[100]=0;return strstr(line,needle)!=0;
}
static void save(const struct prodock_debug_text *t,const char *name)
{
    FILE *f=fopen(name,"wb");assert(f);
    for(unsigned i=0;i<1500;++i) {
        assert(fputc(t->cells[i]&255,f)!=EOF);
        assert(fputc(t->cells[i]>>8,f)!=EOF);
    }
    assert(!fclose(f));
}
int main(void)
{
    struct { uint64_t first;struct prodock_debug_text t;uint64_t last; } v={.first=123,.last=456};
    struct prodock_display_info a={.sent_lo=100000,.game_presents=1000,.frames=1100};
    struct prodock_display_info b={.sent_lo=102000,.game_presents=1051,.frames=1155,
                                  .usb_status=0x62,.line_cycles=1711};
    struct pd_sd_stats old={.sectors=31116288,.read_sectors=2048,.written_sectors=1024,
                           .present=1,.counters_valid=1};
    struct pd_sd_stats sd=old;sd.read_sectors+=1408;sd.written_sectors+=512;
    pd_dashboard(&v.t,&b,&a,&sd,&old,1);
    assert(colour(&v.t,79,0)==PD_GREEN);
    assert(contains(&v.t,4,"51.0 FPS") && contains(&v.t,7,"2000 /s"));
    assert(contains(&v.t,6,"704 Kio/s") && contains(&v.t,8,"256 Kio/s"));
    save(&v.t,"active.cells");
    a=b;old=sd;
    b.frames+=55;
    pd_dashboard(&v.t,&b,&a,&sd,&old,1);
    assert(contains(&v.t,3,"GPU AU REPOS") && colour(&v.t,79,0)==PD_GREEN);
    save(&v.t,"idle.cells");
    b.usb_status|=12;sd.present=0;
    pd_dashboard(&v.t,&b,&a,&sd,&old,1);
    assert(colour(&v.t,79,0)==PD_AMBER && contains(&v.t,3,"RESET MEMORISE"));
    assert(contains(&v.t,6,"-- Kio/s"));
    save(&v.t,"warning.cells");
    b.errors=0x80000001;b.underflows=100;b.usb_status|=128;
    pd_dashboard(&v.t,&b,&a,&sd,&old,1);
    assert(colour(&v.t,79,0)==PD_RED && contains(&v.t,10,"80000001"));
    assert(contains(&v.t,7,"PERTE"));
    save(&v.t,"fault.cells");
    b.errors=0;b.underflows=0;b.usb_status=0xffffffffU;
    pd_dashboard(&v.t,&b,&a,&sd,&old,0);
    assert(colour(&v.t,79,0)==PD_AMBER && contains(&v.t,3,"ETAT INCONNU"));
    assert(contains(&v.t,5,"-- % du LCD") && contains(&v.t,4,"-- FPS"));
    save(&v.t,"unknown.cells");
    a.game_presents=0xfffffff0U;a.frames=0xfffffff0U;a.sent_lo=0xfffffff0U;
    b.game_presents=35;b.frames=39;b.sent_hi=1;b.sent_lo=1984;b.usb_status=0x62;
    sd=old;sd.read_sectors--; /* A reset/removal must never produce a huge rate. */
    pd_dashboard(&v.t,&b,&a,&sd,&old,1);
    assert(contains(&v.t,4,"51.0 FPS") && contains(&v.t,7,"2000 /s"));
    assert(contains(&v.t,6,"-- Kio/s"));
    b.sent_hi=0;b.sent_lo=0;
    pd_dashboard(&v.t,&b,&a,&sd,&old,1);
    assert(contains(&v.t,7,"-- /s"));
    b.line_cycles=2556;
    pd_dashboard(&v.t,&b,&a,&sd,&old,1);
    assert(colour(&v.t,3,3)==PD_RED && colour(&v.t,79,0)==PD_RED);
    assert(v.first==123 && v.last==456);
    puts("PASS dashboard: rates, idle, sticky resets, faults, unavailable data, counter wrap/reset, line budget");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='prodock-dashboard-') as tmp:
        work = Path(tmp)
        (work / 'check.c').write_text(SOURCE)
        subprocess.run(['cc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        '-I', str(HERE / 'userspace'), '-I', str(HERE / 'drivers'),
                        str(work / 'check.c'), '-o', str(work / 'check')], check=True)
        subprocess.run([str(work / 'check')], cwd=work, check=True)
        if args.preview:
            from PIL import Image
            font_source = HERE / 'build/src/linux-6.12.112/lib/fonts/font_8x16.c'
            font = bytes(int(x, 16) for x in re.findall(r'^\s*0x([0-9a-fA-F]{2}),', font_source.read_text(), re.M))
            assert len(font) == 4096
            palette = [0x000000, 0xaa0000, 0x00aa00, 0xaa5500, 0x0000aa, 0xaa00aa, 0x00aaaa, 0xaaaaaa,
                       0x555555, 0xff5555, 0x55ff55, 0xffff55, 0x5555ff, 0xff55ff, 0x55ffff, 0xffffff]
            rgb = [((x >> 16) & 255, (x >> 8) & 255, x & 255) for x in palette]
            args.preview.mkdir(parents=True, exist_ok=True)
            for cells in sorted(work.glob('*.cells')):
                image = Image.new('RGB', (800, 240)); pixels = image.load()
                for i, cell in enumerate(struct.unpack('<1500H', cells.read_bytes())):
                    for y in range(16):
                        bits = font[(cell & 255) * 16 + y]
                        for x in range(8):
                            c = (cell >> 8) & 15 if bits & (128 >> x) else (cell >> 12) & 15
                            pixels[i % 100 * 8 + x, i // 100 * 16 + y] = rgb[c]
                image.save(args.preview / (cells.stem + '.png'))
            print('Native 800x240 previews (synthetic inputs):', args.preview)


if __name__ == '__main__':
    main()

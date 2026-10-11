#!/usr/bin/env python3
"""Exhaust all glyph/colour combinations and verify layout/memory boundaries."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "prodock-text-model.h"
#include "prodock-validate.h"
int main(void) {
    uint8_t font[4096];
    uint8_t *atlas=malloc(PD_ATLAS_BYTES);
    uint16_t cells[3000],*b=malloc(PD_MAP_BYTES),*f=malloc(PD_MAP_BYTES);
    for(unsigned i=0;i<4096;++i)font[i]=(i*73+(i>>4)*11)^0x95;
    pd_text_atlas(atlas,font);
    unsigned pixels=0;
    for(unsigned ch=1;ch<256;++ch)for(unsigned fg=0;fg<16;++fg)for(unsigned bg=0;bg<16;++bg) {
        cells[0]=ch|(fg<<8)|(bg<<12);
        pd_text_map(b,f,cells,1,1,-1);
        for(unsigned y=0;y<16;++y)for(unsigned x=0;x<8;++x) {
            unsigned off=(y%8)*8+x;
            unsigned front=atlas[f[(y/8)*128]*64+off];
            unsigned actual=front?front:atlas[b[(y/8)*128]*64+off];
            unsigned expected=240+((font[ch*16+y]&(128>>x))?fg:bg);
            assert(actual==expected);++pixels;
        }
    }
    for(unsigned i=0;i<3000;++i)cells[i]=0x1720;
    pd_text_map(b,f,cells,100,30,2999);
    assert(b[59*128+99]==7*512+1);
    assert(f[59*128+99]==1*512+32*2+1);
    assert(f[60*128]==32*2);assert(f[63*128+127]==32*2);
    pd_text_map(b,f,cells,50,15,-1);
    assert(f[29*128+49]==7*512+32*2+1);
    assert(f[29*128+50]==32*2);assert(f[30*128]==32*2);
    /* Differential pair encoder against the independently built full map,
     * both terminal sizes, changing cursor, null glyphs and all colours. */
    for(unsigned trial=0;trial<32;++trial) {
        unsigned width=trial%2?100:50,height=trial%2?30:15;
        int cursor=(trial*97)%3000;
        for(unsigned i=0;i<3000;++i)cells[i]=(i*137+trial*7919)&65535;
        pd_text_map(b,f,cells,width,height,cursor);
        for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;x+=2) {
            unsigned index=y*100+x;
            uint16_t a=pd_text_cell(cells[index],(int)index==cursor);
            uint16_t z=pd_text_cell(cells[index+1],(int)(index+1)==cursor);
            for(unsigned half=0;half<2;++half) {
                unsigned off=(y*2+half)*128+x;
                assert(pd_text_pair(a,z,half,0)==(b[off]|((uint32_t)b[off+1]<<16)));
                assert(pd_text_pair(a,z,half,1)==(f[off]|((uint32_t)f[off+1]<<16)));
            }
        }
    }
    uint32_t l[8];
    for(unsigned bank=0;bank<2;++bank)for(unsigned plane=0;plane<4;++plane)for(unsigned a=0;a<2;++a){
        pd_text_layer(l,bank,plane,a,400,0,400,240);
        assert(l[0]>=PD_TEXT_BASE+PD_MAP_OFFSET);
        assert(l[0]+PD_MAP_BYTES<=PD_TEXT_BASE+0x200000);
        assert(l[1]+PD_ATLAS_BYTES<=PD_TEXT_BASE+PD_MAP_OFFSET);
        assert(l[2]==400 && l[3]==(240U<<16|400));
        assert(l[5]==0x67 && l[6]==(plane%2?7:5));
        assert(!prodock_range(l[0],32));
    }
    uint32_t cmd[8]={22U<<24,PD_TEXT_BASE,0xa00000,(400U<<16)|240,(1600U<<16)|1600};
    assert(prodock_command(cmd)==-ERANGE);
    free(atlas);free(b);free(f);
    printf("PASS: %u independent text pixels, all foreground/background colours, cursor, clipping and DDR boundaries\n",pixels);
}
'''
with tempfile.TemporaryDirectory(prefix='prodock-text-') as tmp:
    p=Path(tmp);(p/'test.c').write_text(source)
    subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-I',str(ROOT/'linux/drivers'),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

#!/usr/bin/env python3
"""Prove omitted backdrop copies cannot expose pixels from a previous frame."""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from render_luma import Scene,FxModel
from test_gpu_v1 import signed16
from test_gpu_accel import triangle_pixels

def pair(v):return signed16(v>>16),signed16(v)

def main():
    sc=Scene();initial=FxModel(sc.raw,sc.base)
    for cmd in sc.commands(prepare=True):initial.apply(cmd)
    initial.memory[:192000]=bytes([0x5a,0xc3])*96000
    full=[29<<24,0xb00000,(400<<16)|240,800,0,0,(400<<16)|240,0]
    for age in range(1960,2200):
        commands=sc.commands(age);covered=np.zeros((240,400),dtype=bool)
        flags=alpha=0
        for w in commands:
            op=w[0]>>24
            if op==25:flags,alpha=w[1:3]
            elif op==29:
                x,y=pair(w[5]);width,height=pair(w[6])
                covered[y:y+height,x:x+width]=True
            elif op==27 and flags==64 and alpha==256:
                for x,y in triangle_pixels(*sum((list(pair(v)) for v in w[1:4]),[]),width=400,height=240):covered[y,x]=True
        assert covered.all(),(age,int((~covered).sum()))
        # At representative boundaries, compare every byte including guards
        # against the same image with the original full background copy.
        if age in (1960,1961,2000,2080,2120,2159,2160,2168,2170,2180,2199):
            a=FxModel(sc.raw,sc.base,initial.memory);b=FxModel(sc.raw,sc.base,initial.memory)
            for w in commands:a.apply(w)
            for w in commands[:2]:b.apply(w)
            b.apply(full)
            for w in commands[2:]:
                if w[0]>>24!=29:b.apply(w)
            assert a.memory==b.memory,age
    print('PASS: all 240 bloom phases overwrite or restore all 96000 pixels; 11 full memory/guard comparisons from poisoned buffers')

if __name__=='__main__':main()

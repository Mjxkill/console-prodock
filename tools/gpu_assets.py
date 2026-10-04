#!/usr/bin/env python3
"""Pack PNG/JPEG artwork as aligned RGB565/ARGB4444 GPU V1 mipmaps (.gtex + .json)."""
import argparse,hashlib,json,struct
from pathlib import Path
from PIL import Image
MAGIC=0x31545647

def downsample(image):
    """2x2 box filter in premultiplied alpha, stored back as straight RGBA."""
    w,h=image.size;out=Image.new('RGBA',(max(1,(w+1)//2),max(1,(h+1)//2)))
    src=image.load();dst=out.load()
    for y in range(out.height):
        for x in range(out.width):
            samples=[src[xx,yy] for yy in range(2*y,min(2*y+2,h)) for xx in range(2*x,min(2*x+2,w))]
            a=sum(p[3] for p in samples);n=len(samples)
            rgb=tuple((sum(p[c]*p[3] for p in samples)+a//2)//a if a else 0 for c in range(3))
            dst[x,y]=(*rgb,(a+n//2)//n)
    return out

def pack(image,format='rgb565',mipmaps=True):
    if format not in ('rgb565','argb4444'):raise ValueError('Unknown GPU texture format')
    image=image.convert('RGBA');w,h=image.size
    if not(1<=w<=512 and 1<=h<=512):raise ValueError('Texture dimensions must be 1..512')
    levels=[image]
    while mipmaps and levels[-1].size!=(1,1):levels.append(downsample(levels[-1]))
    data=bytearray(((32+len(levels)*16+31)//32)*32);meta=[]
    for lod,im in enumerate(levels):
        stride=(im.width*2+31)&~31;offset=len(data);data.extend(bytes(stride*im.height))
        for y in range(im.height):
            for x in range(im.width):
                r,g,b,a=im.getpixel((x,y))
                value=((r>>3)<<11)|((g>>2)<<5)|(b>>3) if format=='rgb565' else ((a>>4)<<12)|((r>>4)<<8)|((g>>4)<<4)|(b>>4)
                struct.pack_into('<H',data,offset+y*stride+x*2,value)
        struct.pack_into('<4I',data,32+lod*16,offset,(im.width<<16)|im.height,stride,lod)
        meta.append(dict(lod=lod,offset=offset,width=im.width,height=im.height,stride=stride))
    struct.pack_into('<8I',data,0,MAGIC,1,format=='argb4444',len(levels),w,h,len(data),0)
    return bytes(data),dict(abi=1,format=format,width=w,height=h,bytes=len(data),levels=meta,sha256=hashlib.sha256(data).hexdigest())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--format',choices=('rgb565','argb4444'),default='rgb565');p.add_argument('--no-mipmaps',action='store_true');a=p.parse_args()
    data,meta=pack(Image.open(a.input),a.format,not a.no_mipmaps);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(data)
    a.output.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__':main()

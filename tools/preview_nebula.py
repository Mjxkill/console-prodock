#!/usr/bin/env python3
"""Render a NEBULA host capture from its actual GPU commands and descriptors.

This independent reference covers the COPY/CLEAR/additive textured triangles
used by this game, then the native layers, tilemaps and cached sprites. It is
not a screenshot from the physical board and does not measure GPU speed.
"""
import argparse
import json
from pathlib import Path
import struct
import zlib
import numpy as np
from PIL import Image

BASE=0x800000


def signed(x,bits=16):
    return x-(1<<bits) if x&(1<<(bits-1)) else x


def pos(word):return signed(word>>16),signed(word&65535)


def render(path,scanout_inputs=None):
    meta=json.loads(path.with_suffix('.json').read_text())
    memory=bytearray(path.with_suffix('.memory').read_bytes())
    desc=struct.unpack('<392I',path.with_suffix('.scene').read_bytes())
    commands=np.frombuffer(path.with_suffix('.commands').read_bytes(),'<u4').reshape(-1,8)
    target=None;texture=None;material=None;planes={}

    def pixels(addr,w,h,pitch,dtype='<u2'):
        size=np.dtype(dtype).itemsize
        assert addr>=BASE and addr-BASE+(h-1)*pitch+w*size<=len(memory)
        return np.ndarray((h,w),dtype,buffer=memory,offset=addr-BASE,strides=(pitch,size))

    for words in commands:
        c=list(map(int,words));op=c[0]>>24
        if op==22:
            target=pixels(c[1],c[3]>>16,c[3]&65535,c[4]>>16)
        elif op==29:
            source=pixels(c[1],c[2]>>16,c[2]&65535,c[3]);sx,sy=pos(c[4]);x,y=pos(c[5]);w,h=c[6]>>16,c[6]&65535
            target[y:y+h,x:x+w]=source[sy:sy+h,sx:sx+w]
        elif op==28:
            x,y=pos(c[4]);w,h=c[5]>>16,c[5]&65535
            target[max(0,y):min(target.shape[0],y+h),max(0,x):min(target.shape[1],x+w)]=c[2]
        elif op==24:
            texture=pixels(c[1],c[2]>>16,c[2]&65535,c[3]&65535)
        elif op==25:material=c
        elif op==26:planes[c[0]&7]=(signed(c[1]|(c[4]<<32),48),signed(c[2],32),signed(c[3],32))
        elif op==30:pass
        elif op==27:
            vertices=[pos(c[i]) for i in (1,2,3)]
            area=(vertices[1][0]-vertices[0][0])*(vertices[2][1]-vertices[0][1])-(vertices[2][0]-vertices[0][0])*(vertices[1][1]-vertices[0][1])
            if area==0:continue
            if area<0:vertices[1],vertices[2]=vertices[2],vertices[1]
            left=max(0,min(p[0] for p in vertices));right=min(target.shape[1],max(p[0] for p in vertices))
            top=max(0,min(p[1] for p in vertices));bottom=min(target.shape[0],max(p[1] for p in vertices))
            if right<=left or bottom<=top:continue
            yy,xx=np.mgrid[top:bottom,left:right];mask=np.ones(xx.shape,dtype=bool)
            for a,b in zip(vertices,vertices[1:]+vertices[:1]):
                dx=b[0]-a[0];dy=b[1]-a[1]
                edge=dx*(2*yy+1-2*a[1])-dy*(2*xx+1-2*a[0])
                inclusive=dy<0 or (dy==0 and dx>0)
                mask&=(edge>0)|((edge==0)&inclusive)
            if material[1]&1:
                u=(planes[0][0]+xx*planes[0][1]+yy*planes[0][2])//65536
                v=(planes[1][0]+xx*planes[1][1]+yy*planes[1][2])//65536
                mask&=(u>=0)&(v>=0)&(u<texture.shape[1])&(v<texture.shape[0])
                src=texture[np.clip(v,0,texture.shape[0]-1),np.clip(u,0,texture.shape[1]-1)].astype(np.int64)
                a=src>>12;a=np.where(a==15,256,a*17);a=(a*material[2]+128)>>8
                red=(src>>8)&15;green=(src>>4)&15;blue=src&15
                red=(red<<1)|(red>>3);green=(green<<2)|(green>>2);blue=(blue<<1)|(blue>>3)
            else:
                a=np.full(xx.shape,material[2],np.int64)
                red=np.full(xx.shape,(material[3]>>11)&31,np.int64)
                green=np.full(xx.shape,(material[3]>>5)&63,np.int64)
                blue=np.full(xx.shape,material[3]&31,np.int64)
            mask&=a>0
            red=(red*(material[4]&511)+128)>>8;green=(green*((material[4]>>9)&511)+128)>>8;blue=(blue*((material[4]>>18)&511)+128)>>8
            dst=target[top:bottom,left:right];d=dst.astype(np.int64)
            red=np.minimum(31,(red*a+((d>>11)&31)*256+128)>>8)
            green=np.minimum(63,(green*a+((d>>5)&63)*256+128)>>8)
            blue=np.minimum(31,(blue*a+(d&31)*256+128)>>8)
            dst[mask]=((red<<11)|(green<<5)|blue)[mask]
        else:raise ValueError(op)
    assert target is not None
    raw=target.astype('<u2').tobytes()
    # Native scene x2 is selected by Linux only in the fullscreen layout.
    scale=meta.get('scale',2)
    base_pixels=np.repeat(np.repeat(target,scale,axis=0),scale,axis=1).astype(np.uint32)
    # Match scanout's exact RGB565 -> RGB666 bit replication. Indexed
    # overlays retain all six palette bits, including low red/blue bits.
    image=((((base_pixels>>11)<<1)|((base_pixels>>15)&1))<<12)|(((base_pixels>>5)&63)<<6)|((base_pixels&31)<<1)|((base_pixels>>4)&1)
    palette=np.frombuffer(memory,dtype='<u4',count=256,offset=meta['assets']-BASE+64).copy()
    width,height=target.shape[1]*scale,target.shape[0]*scale

    def overlay(indices,x,y):
        left=max(0,x);top=max(0,y);right=min(width,x+indices.shape[1]);bottom=min(height,y+indices.shape[0])
        if left>=right or top>=bottom:return
        source=indices[top-y:bottom-y,left-x:right-x];dst=image[top:bottom,left:right];mask=source!=0
        dst[mask]=palette[source[mask]]

    layers=np.array(desc[8:136],dtype=np.uint32).reshape(16,8)
    sprites=np.array(desc[136:],dtype=np.uint32).reshape(64,4)
    for priority,l in enumerate(layers):
        l=list(map(int,l));flags=l[6]
        if flags&1:
            y,x=pos(l[2]);vh,vw=l[3]>>16,l[3]&65535;sy,sx=l[4]>>16,l[4]&65535
            if flags&4:
                mw=1<<(l[5]&15);mh=1<<((l[5]>>4)&15);tile=8<<((l[5]>>8)&3)
                tilemap=pixels(l[0],mw,mh,mw*2)
                yy,xx=np.mgrid[sy:sy+vh,sx:sx+vw]
                entries=tilemap[(yy//tile)%mh,(xx//tile)%mw].astype(np.int64)
                offsets=(entries&8191)*tile*tile+(yy%tile)*tile+(xx%tile)
                flat=np.frombuffer(memory,dtype=np.uint8,offset=l[1]-BASE,count=8192*tile*tile)
                source=flat[offsets]
            else:
                source=pixels(l[0],l[1]&65535,l[1]>>16,l[5],np.uint8)[sy:sy+vh,sx:sx+vw]
            overlay(source,x,y)
        for p in sprites:
            p=list(map(int,p))
            if not p[2]&(1<<16) or (p[2]>>20)&15!=priority:continue
            w=p[2]&255;h=(p[2]>>8)&255;y,x=pos(p[1]);source=pixels(p[0],w,h,32,np.uint8)
            if p[2]&(1<<17):source=source[:,::-1]
            if p[2]&(1<<18):source=source[::-1,:]
            overlay(source,x,y)
    rgb=np.stack((((image>>12)&63)*255//63,((image>>6)&63)*255//63,(image&63)*255//63),axis=-1).astype(np.uint8)
    if scanout_inputs:
        scanout_inputs.mkdir(parents=True,exist_ok=True)
        (scanout_inputs/'memory.bin').write_bytes(memory)
        (scanout_inputs/'scene.hex').write_text(''.join(f'{word:08x}\n' for word in desc))
        (scanout_inputs/'palette.hex').write_text(''.join(f'{word:08x}\n' for word in palette))
        (scanout_inputs/'expected.hex').write_text(''.join(f'{word:05x}\n' for word in image.flat))
    Image.fromarray(rgb).save(path.with_suffix('.png'))
    result=dict(meta,frame_crc32=f'{zlib.crc32(raw):08x}',lcd_rgb666_sum=f'{int(image.sum(dtype=np.uint64))&0xffffffff:08x}',preview=str(path.with_suffix('.png')))
    path.with_suffix('.reference.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path)
    p.add_argument('--scanout-inputs',type=Path,help='Export actual memory/descriptors/pixels for the RTL bench')
    a=p.parse_args();render(a.capture,a.scanout_inputs)

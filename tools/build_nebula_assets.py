#!/usr/bin/env python3
"""Convert NEBULA's static artwork to native Pro Dock GPU resources.

No animation or game trajectory is baked here. Positions/physics run in the
Linux executable. Index zero is transparent; 240..255 belong to Linux text.
"""
from pathlib import Path
import hashlib
import json
import re
import struct
import zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/nebula/packed'
SRC = ROOT / 'assets/nebula/source'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fleet = Image.open(SRC / 'fleet.png').convert('RGBA')
    ships = []
    for n in range(4):
        w, h = fleet.size
        tile = fleet.crop((n % 2 * w // 2, n // 2 * h // 2,
                           (n % 2 + 1) * w // 2, (n // 2 + 1) * h // 2))
        box = tile.getchannel('A').point(lambda x: 255 if x > 48 else 0).getbbox()
        assert box, n
        ships.append(tile.crop(box))
    swatches = [(0,0,0),(8,15,29),(17,31,49),(30,58,78),(50,91,113),
                (60,214,241),(142,245,250),(233,250,250),(255,187,73),
                (255,103,69),(219,52,97),(146,105,242),(77,53,124),
                (76,229,163),(32,104,85),(180,206,223),(39,66,89),
                (255,230,157),(85,123,159),(106,160,192)]
    sample = Image.new('RGB', (512,512), (0,0,0))
    for i, ship in enumerate(ships):
        small = ship.copy(); small.thumbnail((256,256),Image.Resampling.LANCZOS)
        sample.paste(small,(i%2*256,i//2*256),small)
    quant = sample.quantize(colors=219,method=Image.Quantize.MEDIANCUT)
    raw = quant.getpalette()[:219*3]
    colours = [(0,0,0)] + [tuple(raw[i:i+3]) for i in range(0,len(raw),3)] + swatches
    assert len(colours)==240
    palette_image = Image.new('P',(1,1))
    palette_image.putpalette(sum((list(c) for c in colours),[])+[0]*48)
    blob = bytearray(4096)
    records = []
    constants = []

    def add(name, data, w=0, h=0, pitch=0, kind=0):
        while len(blob)%32:blob.append(0)
        offset=len(blob);blob.extend(data)
        constants.append(f'#define NA_{name} {len(records)}')
        records.append(dict(name=name,offset=offset,bytes=len(data),width=w,height=h,pitch=pitch,kind=kind))
        return len(records)-1

    pal = [((r>>2)<<12)|((g>>2)<<6)|(b>>2) for r,g,b in colours] + [0]*16
    blob[64:1088]=struct.pack('<256I',*pal)

    def indexed(image, pitch=None):
        rgba=image.convert('RGBA')
        q=np.array(rgba.convert('RGB').quantize(palette=palette_image,dither=Image.Dither.NONE),dtype=np.uint8)
        # Black in opaque hull recesses must stay opaque.
        q[(q==0)|(q>=240)]=221
        q[np.array(rgba.getchannel('A'))<96]=0
        p=pitch or ((rgba.width+31)//32*32)
        data=np.zeros((rgba.height,p),dtype=np.uint8);data[:,:rgba.width]=q
        return data.tobytes(),p

    def fit(image,size):
        im=image.copy();im.thumbnail(size,Image.Resampling.LANCZOS)
        out=Image.new('RGBA',size);out.alpha_composite(im,((size[0]-im.width)//2,(size[1]-im.height)//2))
        return out

    background=Image.open(SRC/'nebula.png').convert('RGB').resize((400,320),Image.Resampling.LANCZOS)
    a=np.array(background,dtype=np.uint16)
    packed=(((a[:,:,0]>>3)<<11)|((a[:,:,1]>>2)<<5)|(a[:,:,2]>>3)).astype('<u2')
    add('BACKGROUND',packed.tobytes(),400,320,800,1)
    background.save(OUT/'background_preview.png')

    for scale in (1,2):
        for bank in range(5):
            image=fit(ships[0],(28*scale,32*scale))
            image=image.rotate((bank-2)*-6,resample=Image.Resampling.BICUBIC,expand=False)
            data,pitch=indexed(image)
            add(f'PLAYER_{scale}_{bank}',data,image.width,image.height,pitch)
        for kind in range(3):
            size=(16*scale,16*scale)
            image=fit(ships[1 if kind!=1 else 2].rotate(180),size)
            data,pitch=indexed(image,32)
            add(f'ENEMY_{scale}_{kind}',data,*size,pitch)
        boss=fit(ships[3].rotate(180),(104*scale,92*scale))
        data,pitch=indexed(boss);add(f'BOSS_{scale}',data,boss.width,boss.height,pitch)
        # Small native cached sprites; two resolutions for split/fullscreen.
        for name,colour,shape in [('SHOT',(140,245,250),'shot'),('ENEMYSHOT',(255,140,60),'orb'),
                                  ('SPARK',(255,221,151),'spark'),('PICKUP',(76,229,163),'pickup')]:
            im=Image.new('RGBA',(16*scale,16*scale));d=ImageDraw.Draw(im)
            cx=8*scale
            if shape=='shot':
                d.rounded_rectangle((cx-2*scale,scale,cx+2*scale,15*scale),radius=2*scale,fill=(*colour,255))
                d.line((cx,2*scale,cx,13*scale),fill=(255,255,255,255),width=scale)
            elif shape=='orb':
                d.ellipse((5*scale,5*scale,11*scale,11*scale),fill=(*colour,255))
                d.ellipse((7*scale,6*scale,9*scale,8*scale),fill=(255,245,195,255))
            elif shape=='pickup':
                d.polygon([(cx,2*scale),(14*scale,cx),(cx,14*scale),(2*scale,cx)],fill=(*colour,255))
                d.line((5*scale,cx,11*scale,cx),fill=(255,255,255,255),width=scale)
                d.line((cx,5*scale,cx,11*scale),fill=(255,255,255,255),width=scale)
            else:
                d.line((cx,3*scale,cx,13*scale),fill=(*colour,255),width=scale)
                d.line((3*scale,cx,13*scale,cx),fill=(*colour,255),width=scale)
                d.rectangle((7*scale,7*scale,9*scale,9*scale),fill=(255,255,255,255))
            data,pitch=indexed(im,32);add(f'{name}_{scale}',data,im.width,im.height,pitch)
        for frame in range(8):
            im=Image.new('RGBA',(16*scale,16*scale));p=np.zeros((16*scale,16*scale,4),np.uint8)
            for y in range(im.height):
                for x in range(im.width):
                    xx=(x+.5)/scale-8;yy=(y+.5)/scale-8
                    angle=np.arctan2(yy,xx);r=np.hypot(xx,yy)
                    edge=2+frame*.8+.65*np.sin(angle*7+frame)+.45*np.cos(angle*11-frame*.7)
                    if r<edge and (frame<3 or r>max(0,edge-(8-frame)*.7)):
                        heat=max(0,1-r/(edge+.1)-frame*.04)
                        p[y,x]=[255,int(90+165*heat),int(25+195*heat),255]
            im=Image.fromarray(p);data,pitch=indexed(im,32)
            add(f'EXPLOSION_{scale}_{frame}',data,im.width,im.height,pitch)
        for frame in range(4):
            im=Image.new('RGBA',(40*scale,40*scale));d=ImageDraw.Draw(im)
            colour=(60,214+frame*8,241,255)
            d.ellipse((scale,scale,39*scale,39*scale),outline=colour,width=scale)
            d.arc((3*scale,3*scale,37*scale,37*scale),frame*60,frame*60+95,fill=(233,250,250,255),width=scale)
            data,pitch=indexed(im);add(f'SHIELD_{scale}_{frame}',data,im.width,im.height,pitch)

    font_source=ROOT/'linux/build/src/linux-6.12.112/lib/fonts/font_8x8.c'
    font=bytes(int(x,16) for x in re.findall(r'^\s*0x([0-9a-fA-F]{2}),',font_source.read_text(),re.M))
    assert len(font)==2048
    add('FONT',font)
    for scale in (1,2):
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',27*scale)
        im=Image.new('RGBA',(156*scale,36*scale));d=ImageDraw.Draw(im)
        d.text((78*scale,0),'NEBULA',anchor='mt',font=font,fill=(233,250,250,255),stroke_width=scale,stroke_fill=(60,214,241,255))
        data,pitch=indexed(im);add(f'LOGO_{scale}',data,im.width,im.height,pitch)
    glow=np.zeros((32,32),dtype='<u2')
    for y in range(32):
        for x in range(32):
            radius=np.hypot(x-15.5,y-15.5)/15.5
            alpha=int(15*max(0,1-radius)**1.8)
            glow[y,x]=(alpha<<12)|0xfff
    add('GLOW',glow.tobytes(),32,32,64,2)
    while len(blob)%32:blob.append(0)
    # Header and full resource table are checked before any GPU upload.
    assert 1088+len(records)*24<=4096
    for i,r in enumerate(records):
        blob[1088+i*24:1112+i*24]=struct.pack('<6I',r['offset'],r['bytes'],r['width'],r['height'],r['pitch'],r['kind'])
    crc=zlib.crc32(blob[64:])
    blob[:24]=struct.pack('<6I',0x3142454e,1,len(blob),crc,len(records),0)
    (OUT/'nebula.bin').write_bytes(blob)
    header='/* Generated by tools/build_nebula_assets.py. */\n#ifndef NEBULA_ASSETS_H\n#define NEBULA_ASSETS_H\n'
    header+='\n'.join(constants)+f'\n#define NEBULA_RESOURCE_COUNT {len(records)}\n#define NEBULA_ASSET_BYTES {len(blob)}U\n#define NEBULA_ASSET_CRC 0x{crc:08x}U\n#endif\n'
    (ROOT/'linux/userspace/nebula-assets.h').write_text(header)
    metadata={'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'crc32':f'{crc:08x}',
              'resources':records,'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SRC.glob('*.png'))}}
    (OUT/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('NEBULA assets:',len(records),'resources,',len(blob),'bytes, CRC',f'{crc:08x}')


if __name__=='__main__':main()

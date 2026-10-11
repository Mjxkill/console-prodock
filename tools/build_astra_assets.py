#!/usr/bin/env python3
"""Pack ASTRA's original artwork and native-resolution overlays, without runtime SD I/O."""
from pathlib import Path
import hashlib, json, math, struct, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/astra/packed'
BASE = 0x06000000
CHAPTERS = [
    (0, 'LE GRAND DÉPART', 'SYSTÈME D’ORIGINE  /  CAP SUR L’INCONNU'),
    (35, 'L’OCÉAN DES GALAXIES', 'DES MILLIARDS DE SOLEILS'),
    (70, 'L’HORIZON DES ÉVÉNEMENTS', 'ANOMALIE GRAVITATIONNELLE'),
    (100, 'LE PONT D’EINSTEIN–ROSEN', 'TRAVERSÉE DU TROU DE VER'),
    (130, 'LA GUERRE DES ÉTOILES', 'CONTACTS HOSTILES  /  ÉVASION'),
    (160, 'LES JARDINS DU COSMOS', 'UN AUTRE SOLEIL  /  UN AUTRE MONDE'),
    (190, 'AU-DELÀ DES DIMENSIONS', 'L’ESPACE SE REPLIE'),
    (225, 'ELYSIA', 'PLANÈTE INCONNUE  /  SIGNATURES VIVANTES'),
    (260, 'LA DESCENTE', 'ENTRÉE DANS L’ATMOSPHÈRE'),
    (285, 'UN NOUVEAU COMMENCEMENT', 'ATTERRISSAGE  /  VÉGÉTATION BIOLUMINESCENTE'),
]
def font(n, bold=False):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf', n)
def rgb565(im):
    a=np.asarray(im.convert('RGB'),dtype=np.uint32)
    return (((a[:,:,0]*31+127)//255<<11)|((a[:,:,1]*63+127)//255<<5)|((a[:,:,2]*31+127)//255)).astype('<u2').tobytes()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data=bytearray(1024); regions={}
    def add(name,raw,**meta):
        data.extend(bytes((-len(data))%32)); off=len(data); data.extend(raw)
        regions[name]=dict(address=BASE+off,offset=off,bytes=len(raw),**meta)
    # Zero is transparent. Index 1 is opaque black. Six ramps give particles
    # and antialiased native text stable colours without stealing texture colours.
    pal=[(0,0,0),(0,0,0)]
    for color in [(200,245,255),(50,210,255),(255,165,62),(209,100,255),(80,255,182),(255,244,212)]:
        pal += [tuple(round(c*(i+1)/32) for c in color) for i in range(32)]
    pal += [(255,255,255)]*(256-len(pal))
    palette=Image.new('P',(1,1));palette.putpalette(sum((list(v) for v in pal),[]))
    def indexed(im):
        a=np.asarray(im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)).copy()
        alpha=np.asarray(im)[:,:,3]>=80;a[~alpha]=0;a[alpha&(a==0)]=1;return a.tobytes()
    add('palette',struct.pack('<256I',*[((r*63+127)//255<<12)|((g*63+127)//255<<6)|((b*63+127)//255) for r,g,b in pal]))
    for name,source,size in [('cosmos','cosmos',(1024,352)),('valley','elysia',(800,400)),('planet','planet',(256,128))]:
        im=Image.open(ROOT/f'assets/astra/source/{source}.png').resize(size,Image.Resampling.LANCZOS)
        add(name,rgb565(im),width=size[0],height=size[1],stride=size[0]*2)
    # Analytic gas giant / solar photosphere / moon textures: deterministic
    # material data, mapped and lit on real geometry at runtime.
    y,x=np.mgrid[0:128,0:256];u=x*2*math.pi/256;v=y*math.pi/128
    wave=np.sin(v*23+np.sin(u*3)*.7)+.35*np.sin(v*67+np.cos(u*7))
    solar=np.sin(u*17+v*12+2*np.sin(v*9))*np.sin(u*19-v*6)+.3*np.sin(u*25)*np.cos(v*34)
    for name,channels in [('gas',(172+36*wave,113+27*wave,64+22*wave)),
                          ('sun',(250+5*solar,189+40*solar,50+28*solar)),
                          ('moon',(90+22*wave,105+24*wave,123+27*wave))]:
        im=Image.fromarray(np.clip(np.stack(channels,axis=-1),0,255).astype(np.uint8))
        add(name,rgb565(im),width=256,height=128,stride=512)
    for i,(_,title,subtitle) in enumerate(CHAPTERS):
        im=Image.new('RGBA',(800,80));d=ImageDraw.Draw(im)
        d.rectangle((0,0,799,35),fill=(0,0,0,255));d.rectangle((0,44,799,79),fill=(0,0,0,255))
        d.text((18,7),'A S T R A',font=font(16,True),fill=(200,245,255,255))
        d.text((240,9),title,font=font(14),fill=(200,245,255,255))
        d.text((724,9),f'{i+1:02}/10',font=font(13),fill=(50,210,255,255))
        d.line((18,35,781,35),fill=(18,65,85,255))
        d.text((18,54),subtitle,font=font(12),fill=(200,245,255,255))
        d.text((611,54),'VOYAGE AUTONOME / 5 MIN',font=font(10),fill=(50,210,255,255))
        add(f'hud{i}',indexed(im),width=800,height=80)
    for name,title,subtitle in [('title','A S T R A','UN VOYAGE AU-DELÀ DES MONDES'),('finish','E L Y S I A','CHAQUE FIN EST UN COMMENCEMENT')]:
        im=Image.new('RGBA',(640,128));d=ImageDraw.Draw(im)
        for text,yy,sz in [(title,4,65),(subtitle,98,17)]:
            f=font(sz,sz>30);w=d.textlength(text,font=f)
            d.text(((640-w)/2+2,yy+2),text,font=f,fill=(0,0,0,255))
            d.text(((640-w)/2,yy),text,font=f,fill=(200,245,255,255))
        add(name,indexed(im),width=640,height=128)
    fx=[]
    for kind in range(6):
        a=np.zeros((32,32),dtype=np.uint8)
        for yy in range(32):
            for xx in range(32):
                r=math.hypot(xx-15.5,yy-15.5)
                # Small sparse stars / motes; dark halo avoids hard sprite boxes.
                light=max(0,1-r/4)**2
                if light>.12:a[yy,xx]=2+kind*32+min(31,20+int(light*18))
        fx.append(a.tobytes())
    add('particles',b''.join(fx),frames=6,width=32,height=32)
    add('black',bytes([1])*800*480,width=800,height=480)
    add('progress',bytes([65])*800*2,width=800,height=2)
    data.extend(bytes((-len(data))%32)); crc=zlib.crc32(data[1024:])
    struct.pack_into('<4I',data,0,0x41535452,1,len(data),crc)
    (OUT/'astra.bin').write_bytes(data)
    m=dict(version=1,base=BASE,bytes=len(data),crc32=f'{crc:08x}',sha256=hashlib.sha256(data).hexdigest(),regions=regions,
           duration_seconds=300,battle_seconds=[130,160],chapters=CHAPTERS,
           sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'assets/astra/source').glob('*.png'))})
    (OUT/'manifest.json').write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
    h=['// Generated by tools/build_astra_assets.py','#ifndef ASTRA_ASSETS_H','#define ASTRA_ASSETS_H',
       f'#define ASTRA_BASE 0x{BASE:08x}UL',f'#define ASTRA_BYTES {len(data)}UL',f'#define ASTRA_CRC 0x{crc:08x}U']
    h += [f'#define ASTRA_{n.upper()} 0x{r["address"]:08x}UL' for n,r in regions.items()]
    h += ['static const int16_t as_sines[257]={'+','.join(str(round(math.sin(i*math.pi/128)*16384)) for i in range(257))+'};','#endif','']
    (ROOT/'fw_console/astra_assets.h').write_text('\n'.join(h)); print(json.dumps({k:m[k] for k in ('bytes','crc32','sha256')},indent=2))
if __name__=='__main__':main()

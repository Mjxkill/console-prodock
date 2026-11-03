#!/usr/bin/env python3
"""Pack ASTRILLA's original artwork and native-resolution overlays, without runtime SD I/O."""
from pathlib import Path
import hashlib, json, math, struct, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'games/astrilla/assets/packed'
BASE = 0x04000000
CHAPTERS = [
    (0, 'LE GRAND DÉPART', 'SYSTÈME D’ORIGINE  /  CAP SUR L’INCONNU'),
    (35, 'L’OCÉAN DES GALAXIES', 'DES MILLIARDS DE SOLEILS'),
    (70, 'L’HORIZON DES ÉVÉNEMENTS', 'ANOMALIE GRAVITATIONNELLE'),
    (100, 'LE PONT D’EINSTEIN–ROSEN', 'TRAVERSÉE DU TROU DE VER'),
    (130, 'LA GUERRE DES ÉTOILES', 'CONTACTS HOSTILES  /  ÉVASION'),
    (160, 'PLONGÉE VERS ELYSIA', 'DESCENTE  /  MONTAGNES ET CANYONS'),
    (190, 'SOUS LA CANOPÉE', 'UNE FORÊT HORS DU TEMPS'),
    (225, 'LA POURSUITE', 'À TRAVERS LES ARCHES ET LA BRUME'),
    (260, 'LA CLAIRIÈRE SECRÈTE', 'LE CALME APRÈS LA TEMPÊTE'),
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
    carrier_source=Image.open(ROOT/'games/astrilla/assets/source/carrier.png').convert('RGBA')
    sample=np.asarray(carrier_source);opaque=sample[:,:,:3][sample[:,:,3]>128]
    colours=Image.fromarray(opaque.reshape(1,-1,3)).quantize(colors=60,method=Image.Quantize.MEDIANCUT).getpalette()[:180]
    pal += [tuple(colours[i:i+3]) for i in range(0,180,3)]
    pal += [(255,255,255)]*(256-len(pal))
    palette=Image.new('P',(1,1));palette.putpalette(sum((list(v) for v in pal),[]))
    def indexed(im):
        a=np.asarray(im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)).copy()
        alpha=np.asarray(im)[:,:,3]>=80;a[~alpha]=0;a[alpha&(a==0)]=1;return a.tobytes()
    add('palette',struct.pack('<256I',*[((r*63+127)//255<<12)|((g*63+127)//255<<6)|((b*63+127)//255) for r,g,b in pal]))
    for name,source,size in [('cosmos','cosmos',(1024,352)),('valley','elysia',(800,400)),('planet','planet',(256,128))]:
        im=Image.open(ROOT/f'games/astra/assets/source/{source}.png').resize(size,Image.Resampling.LANCZOS)
        add(name,rgb565(im),width=size[0],height=size[1],stride=size[0]*2)
    # Analytic gas giant / solar photosphere / moon textures: deterministic
    # material data, mapped and lit on real geometry at runtime.
    y,x=np.mgrid[0:128,0:256];u=x*2*math.pi/256;v=y*math.pi/128
    wave=np.sin(v*23+np.sin(u*3)*.7)+.35*np.sin(v*67+np.cos(u*7))
    latitude=v-math.pi/2
    nx=np.cos(latitude)*np.cos(u);ny=np.sin(latitude);nz=np.cos(latitude)*np.sin(u)
    grain=np.sin(nx*71+1.4*np.sin(nz*41))*np.sin(ny*59+nz*43)+.35*np.sin(nx*123-ny*97+nz*67)
    # Spherical crater distance: seamless at the longitude boundary, unlike
    # stripes reused from the gas giant. Maria, bowl and rim are material data.
    moon=112+8*np.sin(nx*29+ny*17)*np.sin(nz*23-ny*31)+5*grain
    rng=np.random.default_rng(20261009)
    for i in range(100):
        direction=rng.normal(size=3);direction/=np.linalg.norm(direction)
        distance=np.sqrt(np.maximum(0,2*(1-(nx*direction[0]+ny*direction[1]+nz*direction[2]))))
        radius=rng.uniform(.025,.17) if i>5 else rng.uniform(.25,.46)
        if i<6:moon-=26*np.exp(-(distance/radius)**4)
        else:
            moon-=24*np.exp(-(distance/(radius*.72))**4)
            moon+=28*np.exp(-((distance/radius-.9)/.13)**2)
    for name,channels in [('gas',(172+36*wave,113+27*wave,64+22*wave)),
                          ('sun',(250+5*grain,153+47*grain,24+14*grain)),
                          ('moon',(moon*1.02,moon,moon*.94))]:
        im=Image.fromarray(np.clip(np.stack(channels,axis=-1),0,255).astype(np.uint8))
        add(name,rgb565(im),width=256,height=128,stride=512)
    for i,(_,title,subtitle) in enumerate(CHAPTERS):
        im=Image.new('RGBA',(800,80));d=ImageDraw.Draw(im)
        d.rectangle((0,0,799,35),fill=(0,0,0,255));d.rectangle((0,44,799,79),fill=(0,0,0,255))
        d.text((18,7),'ASTRILLA',font=font(16,True),fill=(200,245,255,255))
        d.text((240,9),title,font=font(14),fill=(200,245,255,255))
        d.text((724,9),f'{i+1:02}/10',font=font(13),fill=(50,210,255,255))
        d.line((18,35,781,35),fill=(18,65,85,255))
        d.text((18,54),subtitle,font=font(12),fill=(200,245,255,255))
        d.text((611,54),'GOWIN FPGA SHOWCASE',font=font(10),fill=(50,210,255,255))
        add(f'hud{i}',indexed(im),width=800,height=80)
    for name,title,subtitle in [('title','ASTRILLA','GOWIN FPGA  /  UN VOYAGE AU-DELÀ DES MONDES'),('finish','ASTRILLA','ELYSIA  /  CHAQUE FIN EST UN COMMENCEMENT')]:
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
    # Cinematic plates retain enough detail for dolly, bank and filtered pan.
    for name in ('blackhole','wormhole'):
        im=Image.open(ROOT/f'games/astrilla/assets/source/{name}.png').resize((1024,512),Image.Resampling.LANCZOS)
        add(name,rgb565(im),width=1024,height=512,stride=2048)
    for name,size in [('canyon',(1024,512)),('forest',(1024,512)),('clearing',(800,400))]:
        im=Image.open(ROOT/f'games/astrilla/assets/source/{name}.png').resize(size,Image.Resampling.LANCZOS)
        add(name,rgb565(im),width=size[0],height=size[1],stride=size[0]*2)
    cells=[]
    def argb(im):
        a=np.asarray(im.convert('RGBA'),dtype=np.uint32)
        return (((a[:,:,3]*15+127)//255<<12)|((a[:,:,0]*15+127)//255<<8)|((a[:,:,1]*15+127)//255<<4)|((a[:,:,2]*15+127)//255)).astype('<u2')
    for name in ('corvette','carrier','corvette_front','corvette_side','corvette_landed'):
        im=Image.open(ROOT/f'games/astrilla/assets/source/{name}.png').convert('RGBA')
        im.thumbnail((256,192),Image.Resampling.LANCZOS);canvas=Image.new('RGBA',(256,192));canvas.paste(im,((256-im.width)//2,(192-im.height)//2))
        v=argb(canvas);occupied=(v>>12).reshape(6,32,8,32).max(axis=(1,3))>0
        cells.append([int(sum(1<<c for c in range(8) if row[c])) for row in occupied])
        add(name,v.tobytes(),width=256,height=192,stride=512)
    for name,size in [('station',(256,256)),('interceptor',(256,192))]:
        im=Image.open(ROOT/f'games/astrilla/assets/source/{name}.png').convert('RGBA');im.thumbnail(size,Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',size);canvas.paste(im,((size[0]-im.width)//2,(size[1]-im.height)//2))
        add(name,argb(canvas).tobytes(),width=size[0],height=size[1],stride=size[0]*2)
    fern=Image.open(ROOT/'games/astrilla/assets/source/fern.png').convert('RGBA');fern.thumbnail((128,192),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(128,192));canvas.paste(fern,((128-fern.width)//2,192-fern.height));add('fern',argb(canvas).tobytes(),width=128,height=192,stride=256)
    fern.thumbnail((104,176),Image.Resampling.LANCZOS)
    sway=[]
    for phase in range(16):
        im=fern.rotate(4*math.sin(phase*math.tau/16),Image.Resampling.BICUBIC,expand=True)
        canvas=Image.new('RGBA',(128,192));canvas.paste(im,((128-im.width)//2,192-im.height))
        sway.append(indexed(canvas))
    add('fern_native',b''.join(sway),frames=16,width=128,height=192,stride=128)
    # Native indexed flagship: one stable, antialiased view. The
    # per-frame compositor positions it at 800x480 independently of 3D work.
    pose_bytes=[]
    for i in range(1):
        size=320;angle=0
        im=carrier_source.copy();im.thumbnail((size,round(size*.75)),Image.Resampling.LANCZOS)
        im=im.rotate(angle,Image.Resampling.BICUBIC,expand=True)
        canvas=Image.new('RGBA',(352,288));canvas.paste(im,((352-im.width)//2,(288-im.height)//2))
        pose_bytes.append(indexed(canvas))
    add('flagship',b''.join(pose_bytes),frames=1,width=352,height=288,stride=352)
    # Additive glow, with real ARGB alpha instead of opaque dark halos.
    y,x=np.mgrid[0:64,0:64];r=np.sqrt((x-31.5)**2+(y-31.5)**2)/31
    alpha=np.clip(np.exp(-r*r*7)*(1-np.minimum(r,1)),0,1)
    flare=((np.rint(alpha*15).astype(np.uint16)<<12)|0xfff).astype('<u2')
    add('glow',flare.tobytes(),width=64,height=64,stride=128)
    sheet=Image.open(ROOT/'games/astrilla/assets/source/explosions.png').convert('RGBA')
    hw,hh=sheet.width//2,sheet.height//2
    fire=[sheet.crop((i%2*hw,i//2*hh,(i%2+1)*hw,(i//2+1)*hh)).resize((128,128),Image.Resampling.LANCZOS) for i in range(4)]
    native_fire=[];large_fire=[]
    for phase in range(8):
        f=phase*3/7;i=min(2,int(f));im=Image.blend(fire[i],fire[i+1],f-i)
        add(f'fire{phase}',argb(im).tobytes(),width=128,height=128,stride=256)
        size=38+phase*11;small=im.resize((size,size),Image.Resampling.LANCZOS);canvas=Image.new('RGBA',(128,128));canvas.paste(small,((128-size)//2,(128-size)//2));native_fire.append(indexed(canvas))
        big=im.resize((80+phase*16,80+phase*16),Image.Resampling.LANCZOS);canvas=Image.new('RGBA',(192,192));canvas.paste(big,((192-big.width)//2,(192-big.height)//2));large_fire.append(indexed(canvas))
    add('fire_native',b''.join(native_fire),frames=8,width=128,height=128,stride=128)
    add('fire_large',b''.join(large_fire),frames=8,width=192,height=192,stride=192)
    yy,xx=np.mgrid[:32,:64];shape=np.maximum(0,1-((xx-31.5)/31)**2-((yy-15.5)/15)**2)**2
    add('shadow',(np.rint(shape*8).astype('<u2')<<12).tobytes(),width=64,height=32,stride=128)
    motes=[]
    yy,xx=np.mgrid[:32,:32];glow=np.maximum(0,1-np.sqrt((xx-15.5)**2+(yy-15.5)**2)/4)**2
    for phase in range(16):
        brightness=.10+.90*(.5+.5*math.sin(phase*math.tau/16))**2
        level=np.rint(glow*brightness*31).astype(np.uint8)
        motes.append(np.where(level>1,2+4*32+level,0).astype(np.uint8).tobytes())
    add('firefly',b''.join(motes),frames=16,width=32,height=32)
    # Deterministic material atlas for actual 3D hulls. Texture detail follows
    # the rotating mesh; it is not a pre-rendered spacecraft view.
    yy,xx=np.mgrid[:128,:128]
    panel=172+((xx//24+yy//40)%2)*12+((xx*17+yy*29)%9)-4
    panel=np.where((xx%32<1)|(yy%24<1),128,panel)
    panel=np.where(((xx%32==5)|(xx%32==26))&((yy%16==4)|(yy%16==12)),214,panel)
    add('hull3d',rgb565(Image.fromarray(np.stack([panel]*3,axis=-1).astype(np.uint8))),width=128,height=128,stride=256)
    for name,source,box in [('rock3d','spire',(380,400,650,850)),('bark3d','tree',(360,800,700,1350)),('leaf3d','tree',(300,90,620,410))]:
        im=Image.open(ROOT/f'games/astrilla/assets/source/{source}.png').crop(box).convert('RGB').resize((128,128),Image.Resampling.LANCZOS)
        add(name,rgb565(im),width=128,height=128,stride=256)
    im=Image.new('RGBA',(640,128));d=ImageDraw.Draw(im)
    for text,y,size in [('LOADING',5,58),('ASTRILLA  /  PRÉPARATION DU VOYAGE',94,17)]:
        f=font(size,True);d.text(((640-d.textlength(text,font=f))/2,y),text,font=f,fill=(200,245,255,255))
    add('loading',indexed(im),width=640,height=128,stride=640)
    data.extend(bytes((-len(data))%32)); crc=zlib.crc32(data[1024:])
    struct.pack_into('<4I',data,0,0x41535452,1,len(data),crc)
    (OUT/'astrilla.bin').write_bytes(data)
    m=dict(version=1,base=BASE,bytes=len(data),crc32=f'{crc:08x}',sha256=hashlib.sha256(data).hexdigest(),regions=regions,
           duration_seconds=300,battle_seconds=[130,160],chapters=CHAPTERS,
           sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(list((ROOT/'games/astrilla/assets/source').glob('*.png'))+[ROOT/f'games/astra/assets/source/{n}.png' for n in ('cosmos','elysia','planet')])})
    (OUT/'manifest.json').write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
    h=['// Generated by tools/build_astrilla_assets.py','#ifndef ASTRILLA_ASSETS_H','#define ASTRILLA_ASSETS_H',
       f'#define ASTRILLA_BASE 0x{BASE:08x}UL',f'#define ASTRILLA_BYTES {len(data)}UL',f'#define ASTRILLA_CRC 0x{crc:08x}U']
    h += [f'#define ASTRILLA_{n.upper()} 0x{r["address"]:08x}UL' for n,r in regions.items()]
    h += ['#define ASTRILLA_SHIP_CELLS {'+','.join('{'+','.join(str(x) for x in row)+'}' for row in cells)+'}',
          'static const int16_t as_sines[257]={'+','.join(str(round(math.sin(i*math.pi/128)*16384)) for i in range(257))+'};','#endif','']
    (ROOT/'games/common/astrilla/astrilla_assets.h').write_text('\n'.join(h)); print(json.dumps({k:m[k] for k in ('bytes','crc32','sha256')},indent=2))
if __name__=='__main__':main()

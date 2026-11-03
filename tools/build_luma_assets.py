#!/usr/bin/env python3
"""Convert the generated Luma art into the R31 indexed GPU asset ABI.

No synthesis; sources are preserved. Alpha becomes index 0. Frames keep the
same sheet registration. Conversion uses one palette shared by art and HUD.
"""
from pathlib import Path
import hashlib,json,struct,zlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'games/luma/assets/packed'
BASE=0x04000000

def font(n,serif=False):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/'+('DejaVuSerif' if serif else 'DejaVuSans')+'.ttf',n)

def panel(w,h):
    im=Image.new('RGBA',(w,h),(9,24,25,255));d=ImageDraw.Draw(im)
    d.rectangle((1,1,w-2,h-2),outline=(145,125,70),width=1)
    d.line((8,3,w-9,3),fill=(57,72,62));return im

def center(d,y,s,f,fill,w):
    d.text(((w-d.textlength(s,font=f))/2,y),s,font=f,fill=fill,stroke_width=0)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    world=Image.open(ROOT/'games/luma/assets/source/world.png').convert('RGB')
    assert world.size==(1536,1024)
    frames=[]
    for name in ('hero','enemies'):
        sheet=Image.open(ROOT/f'games/luma/assets/source/{name}.png').convert('RGBA')
        for row in range(4):
            for col in range(4):
                box=tuple(round(v) for v in (col*sheet.width/4,row*sheet.height/4,(col+1)*sheet.width/4,(row+1)*sheet.height/4))
                frames.append(sheet.crop(box).resize((64,64),Image.Resampling.LANCZOS))
    hud=panel(272,48);d=ImageDraw.Draw(hud)
    d.text((14,7),'LUMA',font=font(19,True),fill=(246,221,155))
    for x in range(96,244,28):
        d.polygon([(x,17),(x+3,13),(x+6,16),(x+9,13),(x+12,17),(x+12,22),(x+6,29),(x,22)],fill=(214,76,64))
        d.line((x+2,18,x+5,16,x+7,16),fill=(255,163,101),width=2)
    d.text((16,30),'LE SANCTUAIRE DES LUCIOLES',font=font(9),fill=(150,186,166))
    chapters=[]
    titles=[('I  ·  LE SENTIER OUBLIÉ','Une lueur veille au-delà de la rivière.'),
            ('II  ·  LA CLAIRIÈRE','Les esprits de la forêt s’éveillent.'),
            ('III  ·  LE GARDIEN','La pierre se souvient de la lumière.'),
            ('IV  ·  LE SANCTUAIRE','Trois éclats. Une promesse retrouvée.'),
            ('LA FORÊT SE SOUVIENT','Et la lumière reprend son voyage…')]
    for title,sub in titles:
        im=panel(576,56);d=ImageDraw.Draw(im)
        center(d,7,title,font(16,True),(245,220,155),576)
        center(d,31,sub,font(12),(163,192,177),576);chapters.append(im)
    title=panel(440,122);d=ImageDraw.Draw(title)
    center(d,10,'L U M A',font(37,True),(255,226,163),440)
    center(d,60,'LE SANCTUAIRE DES LUCIOLES',font(13),(178,207,178),440)
    center(d,91,'Un voyage au cœur de la forêt',font(13,True),(223,199,139),440)
    badge=panel(144,30);d=ImageDraw.Draw(badge);center(d,7,'VOYAGE AUTOMATIQUE',font(9),(202,192,143),144)
    # The palette is trained on native map pixels and weighted actor/UI colors.
    colors=[np.asarray(world).reshape(-1,3)[::4]]
    for im in frames+[hud,title,badge]+chapters:
        a=np.asarray(im);colors.append(np.repeat(a[:,:,:3][a[:,:,3]>=128],4,axis=0))
    pixels=np.concatenate(colors);pixels=pixels[:len(pixels)//1024*1024]
    train=Image.fromarray(pixels.reshape(-1,1024,3)).quantize(colors=223,method=Image.Quantize.MEDIANCUT)
    pal=[(0,0,0)]+list(zip(*[iter(train.getpalette()[:223*3])]*3))
    # 224..239 reserved for localized water shimmer, 240..255 for effects.
    pal += [(12+2*i,72+7*i,78+7*i) for i in range(16)]
    pal += [(255,242,177),(157,247,218),(245,188,70),(91,172,155),(22,43,37),(75,73,105),
            (235,235,231),(122,196,249),(191,127,238),(31,55,43),(246,98,59),(211,174,90),
            (255,255,230),(130,176,66),(58,99,76),(0,0,0)]
    assert len(pal)==256
    palette=Image.new('P',(1,1));palette.putpalette(sum((list(c) for c in pal),[]))
    def quant(im):
        a=np.asarray(im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)).copy()
        if im.mode=='RGBA':a[np.asarray(im)[:,:,3]<128]=0
        # Avoid accidental black key for opaque very dark colors.
        if im.mode=='RGBA':a[(a==0)&(np.asarray(im)[:,:,3]>=128)]=244
        else:a[a==0]=244
        return a
    data=bytearray(1024);regions={}
    def add(name,raw,**meta):
        data.extend(bytes((-len(data))%32));off=len(data);data.extend(raw)
        regions[name]=dict(address=BASE+off,offset=off,bytes=len(raw),**meta)
        return BASE+off
    palette_words=[((r*63+127)//255<<12)|((g*63+127)//255<<6)|((b*63+127)//255) for r,g,b in pal]
    add('palette',struct.pack('<256I',*palette_words))
    a=quant(world)
    # Only stream pixels get palette animation, never the bridge, sky or actor.
    rgb=np.asarray(world).astype(np.int16);yy,xx=np.indices(a.shape)
    water=(xx>685)&(xx<904)&(rgb[:,:,1]>rgb[:,:,0]*1.6)&(rgb[:,:,2]>rgb[:,:,0]*1.7)&(rgb[:,:,2]>65)&(rgb[:,:,2]>=rgb[:,:,1]-32)
    water &= ~((yy>467)&(yy<541))
    a[water]=224+np.clip((rgb[:,:,1][water]-72)//7,0,15).astype(np.uint8)
    add('world',a.tobytes(),width=1536,height=1024)
    for group,start in [('hero',0),('enemies',16)]:
        raw=bytearray()
        for im in frames[start:start+16]:
            q=quant(im)
            for ty in range(2):
                for tx in range(2):raw.extend(q[ty*32:ty*32+32,tx*32:tx*32+32].tobytes())
        add(group,raw,frames=16,frame_bytes=4096)
    for name,im in [('hud',hud),('title',title),('badge',badge)]+[(f'chapter{i}',im) for i,im in enumerate(chapters)]:
        add(name,quant(im).tobytes(),width=im.width,height=im.height)
    effects=[]
    for kind in range(16):
        im=Image.new('L',(32,32),0);d=ImageDraw.Draw(im)
        if kind==0: # sparse contact shadow; palette opacity represented by coverage
            for y in range(11,21):
                for x in range(2,30):
                    if ((x-16)**2/196+(y-16)**2/25)<1 and (x+y)%2==0:d.point((x,y),fill=244)
        elif kind<5:
            r=kind;d.ellipse((16-r,16-r,16+r,16+r),fill=243);d.line((16-r,16,16+r,16),fill=240);d.line((16,16-r,16,16+r),fill=240);d.point((16,16),fill=252)
        elif kind<9:
            r=(kind-4)*3;d.arc((16-r,16-r//2,16+r,16+r//2),15,160,fill=241,width=1);d.arc((16-r,16-r//2,16+r,16+r//2),195,330,fill=243,width=1)
        elif kind<13:
            r=(kind-8)*3;d.line((16-r,16,16+r,16),fill=242,width=2);d.line((16,16-r,16,16+r),fill=240,width=2);d.line((16-r,16-r,16+r,16+r),fill=242,width=1)
        elif kind==13:d.polygon((16,7,22,15,16,25,10,15),fill=247);d.line((16,9,16,21),fill=252)
        elif kind==14:d.polygon((10,12,21,10,17,19,11,21),fill=253);d.line((12,18,19,12),fill=251)
        else:d.ellipse((10,10,21,21),outline=241,width=2)
        effects.append(im.tobytes())
    add('effects',b''.join(effects),frames=16,frame_bytes=1024)
    # Half-resolution RGB565 background for the effects chapter. This is the final
    # camera crop, converted to a night palette, without changing source art.
    table=np.array(pal,dtype=np.uint16)
    crop=quant(world)[0:480,736:1536]
    rgb=table[crop].astype(np.uint32)
    rgb=rgb*np.array([86,110,156],dtype=np.uint32)//256
    def rgb565(rgb):
        return (((rgb[:,:,0]*31+127)//255<<11)|((rgb[:,:,1]*63+127)//255<<5)|((rgb[:,:,2]*31+127)//255)).astype('<u2')
    add('fx_bg',rgb565(rgb[::2,::2]).tobytes(),width=400,height=240,stride=800)
    portal=table[quant(world)[256:512,608:864]]
    add('fx_portal',rgb565(portal.astype(np.uint32)).tobytes(),width=256,height=256,stride=512)
    yy,xx=np.indices((64,64));v=(xx*3+yy*5+(xx^yy)*2)%17
    gem=np.stack((60+v*4,150+v*5,195+v*3),axis=-1).astype(np.uint32)
    add('fx_gem',rgb565(gem).tobytes(),width=64,height=64,stride=128)
    for i,(name,sub) in enumerate([
        ('V  ·  LE PASSAGE','Lumières additives · Anneaux translucides'),
        ('VI  ·  ENTRE DEUX MONDES','Texture animée · Rotation · Distorsion'),
        ('VII  ·  LE CŒUR DE LUMIÈRE','Cristal 3D · Perspective · Profondeur'),
        ('VIII  ·  L’ÉVEIL','Ondes de choc · Particules · Lueurs croisées')]):
        im=panel(576,56);d=ImageDraw.Draw(im)
        center(d,7,name,font(16,True),(245,220,155),576)
        center(d,31,sub,font(12),(163,192,177),576)
        add(f'fx_caption{i}',quant(im).tobytes(),width=576,height=56)
    add('fx_black',bytes([255])*1024)
    add('fx_black_map',bytes(32*16*2))
    # A native-resolution, keyed portrait preserves the generated alpha.
    portrait=Image.open(ROOT/'games/luma/assets/source/hero_portrait.png').convert('RGBA')
    portrait=portrait.resize((352,440),Image.Resampling.LANCZOS)
    add('fx_portrait',quant(portrait).tobytes(),width=352,height=440)
    # Typography remains native LCD resolution. A compact sequence of sizes
    # lets the logo grow without spending raster time on its transparent area.
    logo=Image.new('RGBA',(416,144));d=ImageDraw.Draw(logo)
    center(d,0,'LUMA',font(103,True),(255,229,160),416)
    d.line((36,126,380,126),fill=(171,219,212),width=1)
    d.polygon([(208,120),(214,126),(208,132),(202,126)],fill=(255,229,160))
    for i in range(16):
        w=176+16*i;h=60+4*i
        im=logo.resize((w,h),Image.Resampling.LANCZOS)
        add(f'fx_logo{i}',quant(im).tobytes(),width=w,height=h)
    credit=Image.new('RGBA',(416,80));d=ImageDraw.Draw(credit)
    center(d,5,'LE SANCTUAIRE DES LUCIOLES',font(17,True),(255,231,171),416)
    center(d,38,'La lumière ne s’éteint jamais.',font(14),(182,219,214),416)
    add('fx_credit',quant(credit).tobytes(),width=416,height=80)
    # Dark full-screen finale backdrop, with baked nebula-like radial light.
    yy,xx=np.indices((240,400));rad=np.maximum(0,1-((xx-280)**2/160**2+(yy-118)**2/160**2))
    sky=np.stack((9+rad*10,15+rad*32,30+rad*39),axis=-1).astype(np.uint32)
    add('fx_sky',rgb565(sky).tobytes(),width=400,height=240,stride=800)
    data.extend(bytes((-len(data))%32));crc=zlib.crc32(data[1024:])
    struct.pack_into('<4I',data,0,0x414d554c,1,len(data),crc)
    (OUT/'luma.bin').write_bytes(data)
    manifest=dict(version=1,base=BASE,bytes=len(data),crc32=f'{crc:08x}',sha256=hashlib.sha256(data).hexdigest(),regions=regions,
                  sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'games/luma/assets/source').glob('*.png'))})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    header=['// Generated by tools/build_luma_assets.py. Do not edit.','#ifndef LUMA_ASSETS_H','#define LUMA_ASSETS_H',f'#define LUMA_BASE 0x{BASE:08x}UL',f'#define LUMA_BYTES {len(data)}UL',f'#define LUMA_CRC 0x{crc:08x}U']
    for name,r in regions.items():header.append(f'#define LUMA_{name.upper()} 0x{r["address"]:08x}UL')
    header+=['#endif',''];(ROOT/'games/luma/src/luma_assets.h').write_text('\n'.join(header))
    # Native-size converted sprite contact sheet for visual inspection.
    preview=Image.new('RGBA',(512,256))
    for i,im in enumerate(frames):
        q=quant(im);p=Image.fromarray(q,'P');p.putpalette(palette.getpalette());p.info['transparency']=0
        preview.paste(p.convert('RGBA'),((i%8)*64,(i//8)*64))
    preview.save(OUT/'actors.png')
    print(json.dumps({k:manifest[k] for k in ('bytes','crc32','sha256')},indent=2))
if __name__=='__main__':main()

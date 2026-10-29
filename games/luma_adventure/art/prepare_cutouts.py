#!/usr/bin/env python3
"""Prepare local BiRefNet segmentation of each sprite cell; pack reviewed output."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('sheet');p.add_argument('--pack',action='store_true');a=p.parse_args()
    spec=next(s for s in json.loads((ROOT/'brief.json').read_text())['images'] if s['name']==a.sheet)
    cols,rows=spec['grid'];cw,ch=spec['width']//cols,spec['height']//rows
    if a.pack:
        out=ROOT/'source'/(a.sheet+'_cutouts');m=json.loads((out/'submission.json').read_text());assert m['status']=='generated'
        files=m['files'];assert len(files)==cols*rows
        sheet=Image.new('RGBA',(spec['width'],spec['height']))
        for n,file in enumerate(files):
            im=Image.open(out/file['file']).convert('RGBA');assert im.size==(cw,ch)
            sheet.alpha_composite(im,((n%cols)*cw,(n//cols)*ch))
        target=ROOT/'source'/(a.sheet+'_rgba.png');sheet.save(target)
        (ROOT/'provenance'/(a.sheet+'_rgba.json')).write_text(json.dumps(dict(source=a.sheet+'.png',source_sha256=hashlib.sha256((ROOT/'source'/(a.sheet+'.png')).read_bytes()).hexdigest(),file=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),method=f'ComfyUI local BiRefNet on {cols*rows} independent cells, inverse mask -> JoinImageWithAlpha',segmentation=m),indent=2)+'\n')
        print('Packed '+target.name);return
    meta=json.loads((ROOT/'provenance'/(a.sheet+'.json')).read_text());im=meta['server_image'];name=(im['subfolder']+'/' if im['subfolder'] else '')+im['filename']+' [output]'
    graph={'load':dict(class_type='LoadImage',inputs=dict(image=name)),'model':dict(class_type='LoadBackgroundRemovalModel',inputs=dict(bg_removal_name='birefnet.safetensors'))}
    last=None
    for n in range(cols*rows):
        key=f'crop_{n:02}';graph[key]=dict(class_type='ImageCrop',inputs=dict(image=['load',0],width=cw,height=ch,x=n%cols*cw,y=n//cols*ch))
        if last:
            batch=f'batch_{n:02}';graph[batch]=dict(class_type='ImageBatch',inputs=dict(image1=[last,0],image2=[key,0]));last=batch
        else:last=key
    graph.update(mask=dict(class_type='RemoveBackground',inputs=dict(bg_removal_model=['model',0],image=[last,0])),invert=dict(class_type='InvertMask',inputs=dict(mask=['mask',0])),rgba=dict(class_type='JoinImageWithAlpha',inputs=dict(image=[last,0],alpha=['invert',0])),save=dict(class_type='SaveImage',inputs=dict(images=['rgba',0],filename_prefix='luma_'+a.sheet+'_cutout')))
    path=ROOT/'workflows'/(a.sheet+'_cutouts.json');path.write_text(json.dumps(graph,indent=2)+'\n');print(path)

if __name__=='__main__':main()

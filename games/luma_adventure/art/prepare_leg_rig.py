#!/usr/bin/env python3
"""Prepare a local ComfyUI leg-only counterphase, retaining the original torso.

The generated illustration provides both limbs. This explicit compositor mask
excludes the hand-held lantern and does not introduce a model-generated pose.
"""
import json
import argparse
import hashlib
import shutil
import urllib.request
import uuid
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--export',action='store_true');args=parser.parse_args()
    if args.export:
        folder=ROOT/'source/hero_leg_rig';meta=json.loads((folder/'submission.json').read_text());assert meta['status']=='generated'
        source=folder/meta['files'][0]['file'];target=ROOT/'source/hero_stride_opposite.png';shutil.copy2(source,target)
        (ROOT/'provenance/hero_stride_opposite.json').write_text(json.dumps(dict(status='derived',method='Local ComfyUI masked leg counterphase; original upper body/lantern preserved',sha256=hashlib.sha256(target.read_bytes()).hexdigest(),source='hero_stride_a',submission=meta),indent=2)+'\n')
        path=ROOT/'brief.json';brief=json.loads(path.read_text())
        if not any(s['name']=='hero_stride_opposite' for s in brief['images']):brief['images'].append(dict(name='hero_stride_opposite',derived_only=True,type='sprites',width=512,height=512,grid=[1,1],ids=['stride_opposite'],recipe='prepare_leg_rig.py, run_local_workflow.py, prepare_leg_rig.py --export'))
        path.write_text(json.dumps(brief,ensure_ascii=False,indent=2)+'\n');print('Exported derived counterphase with source/job provenance.');return
    mask=Image.new('RGB',(512,512));d=ImageDraw.Draw(mask)
    d.polygon([(201,345),(308,345),(366,460),(352,501),(105,501),(105,435),(160,393),(180,365)],fill='white')
    path=ROOT/'workflows/hero_legs_mask.png';mask.save(path)
    boundary=uuid.uuid4().hex;name='luma_hero_legs_mask_20261024.png'
    payload=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n').encode()+path.read_bytes()+(f'\r\n--{boundary}--\r\n').encode()
    req=urllib.request.Request('http://gx10-2:8188/upload/image',payload,{'Content-Type':'multipart/form-data; boundary='+boundary})
    with urllib.request.urlopen(req,timeout=20) as response:uploaded=json.load(response)
    meta=json.loads((ROOT/'source/hero_stride_a_cutouts/submission.json').read_text());file=meta['files'][0]['server_file'];source=file['filename']+' [output]'
    def node(kind,**inputs):return dict(class_type=kind,inputs=inputs)
    graph=dict(load=node('LoadImage',image=source),region=node('LoadImage',image=uploaded['name']),region_mask=node('ImageToMask',image=['region',0],channel='red'),foreground=node('InvertMask',mask=['load',1]),legs=node('MaskComposite',destination=['foreground',0],source=['region_mask',0],x=0,y=0,operation='multiply'),upper=node('MaskComposite',destination=['foreground',0],source=['region_mask',0],x=0,y=0,operation='subtract'),legs_image=node('MaskToImage',mask=['legs',0]),legs_flip=node('ImageFlip',image=['legs_image',0],flip_method='y-axis: horizontally'),new_legs=node('ImageToMask',image=['legs_flip',0],channel='red'),rgb_flip=node('ImageFlip',image=['load',0],flip_method='y-axis: horizontally'),rgb=node('ImageCompositeMasked',destination=['load',0],source=['rgb_flip',0],x=0,y=0,resize_source=False,mask=['new_legs',0]),alpha=node('MaskComposite',destination=['upper',0],source=['new_legs',0],x=0,y=0,operation='add'),inverse=node('InvertMask',mask=['alpha',0]),rgba=node('JoinImageWithAlpha',image=['rgb',0],alpha=['inverse',0]),save=node('SaveImage',images=['rgba',0],filename_prefix='luma_hero_leg_rig'))
    (ROOT/'workflows/hero_leg_rig.json').write_text(json.dumps(graph,indent=2)+'\n')
    print('Prepared local masked leg rig; reference upper body and lantern unchanged.')

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Discover and generate LUMA assets using the existing local ComfyUI service.

No installation, server lifecycle commands, queue deletion or interruption.
Every submission, original output, source prompt and run metadata is retained.
"""
import argparse
import hashlib
import json
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def read_json(path):return json.loads(path.read_text())
def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(data):return hashlib.sha256(data).hexdigest()

def request(base,path,data=None,timeout=30):
    payload=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(base+path,payload,{'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as response:return response.read()

def choices(nodes,node,field):
    value=nodes.get(node,{}).get('input',{}).get('required',{}).get(field,[[]])[0]
    return value if isinstance(value,list) else []

def discover(base,verbose=True):
    nodes=json.loads(request(base,'/object_info'))
    stats=json.loads(request(base,'/system_stats'))
    write_json(ROOT/'provenance/object_info.json',nodes)
    write_json(ROOT/'provenance/system_stats.json',stats)
    models={node:choices(nodes,node,key) for node,key in [('UNETLoader','unet_name'),('CLIPLoader','clip_name'),('VAELoader','vae_name'),('LoraLoaderModelOnly','lora_name'),('CheckpointLoaderSimple','ckpt_name')]}
    write_json(ROOT/'provenance/available_models.json',models)
    status_path=ROOT/'provenance/service_status.json'
    if status_path.exists():
        previous=read_json(status_path)
        if previous.get('status')!='responding':
            archive=ROOT/'provenance/service_before_start.json'
            if not archive.exists():shutil.copy2(status_path,archive)
    write_json(status_path,dict(checked_unix=time.time(),endpoint=base,status='responding',system_stats='system_stats.json',models='available_models.json',scope='Read-only API discovery; does not claim successful generation or alter service lifecycle.'))
    if verbose:print(json.dumps(dict(endpoint=base,models=models),ensure_ascii=False,indent=2),flush=True)
    return nodes,models

def choose_workflow(spec,nodes,models):
    unets=models['UNETLoader']; clips=models['CLIPLoader']; vaes=models['VAELoader']; loras=models['LoraLoaderModelOnly']
    edit=bool(spec.get('reference'))
    qwen=next((m for m in unets if ('qwen_image_edit_2509' if edit else 'qwen_image_2512') in m),None)
    clip=next((m for m in clips if 'qwen_2.5_vl_7b' in m.lower()),None)
    vae=next((m for m in vaes if 'qwen' in m.lower()),None)
    if qwen and clip and vae:
        lora=next((m for m in loras if ('2509' if edit else '2512') in m and '4step' in m.lower()),None)
        if spec.get('quality')=='full':lora=None
        g={
          'unet':{'class_type':'UNETLoader','inputs':{'unet_name':qwen,'weight_dtype':'default'}},
          'clip':{'class_type':'CLIPLoader','inputs':{'clip_name':clip,'type':'qwen_image','device':'default'}},
          'vae':{'class_type':'VAELoader','inputs':{'vae_name':vae}},
          'shift':{'class_type':'ModelSamplingAuraFlow','inputs':{'model':['lora' if lora else 'unet',0],'shift':3.0}},
          'latent':{'class_type':'EmptySD3LatentImage','inputs':{'width':spec['width'],'height':spec['height'],'batch_size':1}},
          'positive':{'class_type':'CLIPTextEncode','inputs':{'clip':['clip',0],'text':spec['prompt']}},
          'negative':{'class_type':'CLIPTextEncode','inputs':{'clip':['clip',0],'text':''}},
          'sample':{'class_type':'KSampler','inputs':{'model':['shift',0],'seed':spec['seed'],'steps':4 if lora else spec.get('steps',40),'cfg':1.0 if lora else 4.0,'sampler_name':'euler','scheduler':'simple','positive':['positive',0],'negative':['negative',0],'latent_image':['latent',0],'denoise':1.0}},
          'decode':{'class_type':'VAEDecode','inputs':{'samples':['sample',0],'vae':['vae',0]}},
          'save':{'class_type':'SaveImage','inputs':{'images':['decode',0],'filename_prefix':'luma_'+spec['name']}}
        }
        if lora:g['lora']={'class_type':'LoraLoaderModelOnly','inputs':{'model':['unet',0],'lora_name':lora,'strength_model':1.0}}
        if edit:
            ref=spec['reference'];meta=read_json(ROOT/'provenance'/(ref['sheet']+'.json'));im=meta['server_image']
            filename=(im['subfolder']+'/' if im['subfolder'] else '')+im['filename']+' [output]'
            g['reference']={'class_type':'LoadImage','inputs':{'image':filename}}
            source=['reference',0]
            if ref.get('crop'):
                x,y,w,h=ref['crop'];g['ref_crop']={'class_type':'ImageCrop','inputs':{'image':source,'x':x,'y':y,'width':w,'height':h}};source=['ref_crop',0]
            for key,prompt in [('positive',spec['prompt']),('negative','')]:
                g[key]={'class_type':'TextEncodeQwenImageEditPlus','inputs':{'clip':['clip',0],'prompt':prompt,'vae':['vae',0],'image1':source}}
    else:
        raise RuntimeError('No verified Qwen-Image-2512 UNET/CLIP/VAE set. Available models saved; choose and review another installed workflow before submitting.')
    missing={n['class_type'] for n in g.values()}-set(nodes)
    if missing:raise RuntimeError('Required installed node classes missing: '+', '.join(sorted(missing)))
    return g

def generate(base,spec,nodes,models,resume=False):
    target=ROOT/'source'/f"{spec['name']}.png"
    meta_path=ROOT/'provenance'/f"{spec['name']}.json"
    workflow_path=ROOT/'workflows'/f"{spec['name']}.json"
    if target.exists():
        print(f"Preserved existing original: {target.name}",flush=True);return
    if resume and meta_path.exists():
        metadata=read_json(meta_path);job=metadata['prompt_id']
    else:
        if meta_path.exists():
            previous=read_json(meta_path)
            if previous.get('status')!='error':raise RuntimeError('A previous job exists without an output. Use --resume: '+previous['prompt_id'])
            archive=ROOT/'provenance'/'failed_attempts'/previous['prompt_id'];archive.mkdir(parents=True,exist_ok=True)
            for file in [meta_path,workflow_path,ROOT/'provenance'/f"{spec['name']}_history.json"]:
                if file.exists():shutil.copy2(file,archive/file.name)
        graph=choose_workflow(spec,nodes,models)
        queue=json.loads(request(base,'/queue'))
        if queue.get('queue_running') or queue.get('queue_pending'):
            raise RuntimeError('Existing ComfyUI jobs are running or queued. No submission made; preserve their queue and retry after completion.')
        print(f"Workflow {spec['name']}: UNET={graph['unet']['inputs']['unet_name']}, CLIP={graph['clip']['inputs']['clip_name']}",flush=True)
        write_json(workflow_path,graph)
        submitted=json.loads(request(base,'/prompt',{'prompt':graph,'client_id':'luma-art-20261023'}))
        if 'prompt_id' not in submitted:raise RuntimeError(json.dumps(submitted))
        job=submitted['prompt_id']
        metadata=dict(status='queued',endpoint=base,prompt_id=job,seed=spec['seed'],prompt=spec['prompt'],dimensions=[spec['width'],spec['height']],workflow=workflow_path.relative_to(ROOT).as_posix(),workflow_sha256=digest(workflow_path.read_bytes()),submitted_unix=time.time(),response=submitted)
        write_json(meta_path,metadata)
    print(f"Queued {spec['name']}: {job}",flush=True)
    start=time.monotonic()
    while time.monotonic()-start<2400:
        history=json.loads(request(base,'/history/'+urllib.parse.quote(job)))
        if job in history:
            result=history[job];write_json(ROOT/'provenance'/f"{spec['name']}_history.json",result)
            if result.get('status',{}).get('status_str')=='error':
                metadata['status']='error';metadata['execution_status']=result.get('status');write_json(meta_path,metadata)
                raise RuntimeError(json.dumps(result.get('status'),ensure_ascii=False)[:4000])
            for output in result.get('outputs',{}).values():
                for im in output.get('images',[]):
                    data=request(base,'/view?'+urllib.parse.urlencode({k:im[k] for k in ('filename','subfolder','type')}))
                    target.write_bytes(data)
                    metadata.update(status='generated',output=target.relative_to(ROOT).as_posix(),sha256=digest(data),server_image=im,completed_unix=time.time(),elapsed_seconds=round(time.monotonic()-start,2))
                    write_json(meta_path,metadata)
                    print(f"Generated {spec['name']}: {len(data)} bytes in {metadata['elapsed_seconds']}s",flush=True);return
        time.sleep(3)
    metadata['status']='waiting';write_json(meta_path,metadata)
    raise TimeoutError('Generation still queued/running. Use --resume; do not submit a duplicate: '+job)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint',default='http://gx10-2:8188')
    parser.add_argument('--discover',action='store_true')
    parser.add_argument('--only',nargs='*')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if urllib.parse.urlparse(args.endpoint).hostname not in ('gx10-2','localhost','127.0.0.1'):raise SystemExit('Only the authorized local gx10-2 service or its local SSH tunnel is allowed.')
    nodes,models=discover(args.endpoint,args.discover)
    if args.discover:return
    for spec in read_json(ROOT/'brief.json')['images']:
        if args.only and spec['name'] not in args.only:continue
        if spec.get('derived_only'):continue
        generate(args.endpoint,spec,nodes,models,args.resume)

if __name__=='__main__':main()

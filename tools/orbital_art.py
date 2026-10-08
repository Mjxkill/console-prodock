#!/usr/bin/env python3
"""Generate ORBITAL source art on a local ComfyUI (gx10-1/gx10-2), Qwen-Image in 4 steps.

Text to image, or edit of up to three reference pictures (Qwen-Image-Edit) to keep the
identity of an existing design. Enemies are requested on a flat green screen and keyed
by tools/build_orbital_assets.py. Prompts and seeds are kept in assets/orbital/prompts.md.
"""
import argparse,json,time,urllib.request,urllib.parse,uuid
from pathlib import Path

def call(host,path,data=None,headers=None):
    request=urllib.request.Request(f'http://{host}:8188{path}',data=data,headers=headers or {})
    with urllib.request.urlopen(request,timeout=60) as r:return r.read()
def upload(host,path):
    boundary=uuid.uuid4().hex;name=f'orbital_{path.name}'
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: image/png\r\n\r\n').encode()+path.read_bytes()+(f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{boundary}--\r\n').encode()
    return json.loads(call(host,'/upload/image',body,{'Content-Type':f'multipart/form-data; boundary={boundary}'}))['name']
def workflow(prompt,seed,width,height,references):
    edit=bool(references)
    g={'unet':{'class_type':'UNETLoader','inputs':{'unet_name':'qwen_image_edit_2509_fp8_e4m3fn.safetensors' if edit else 'qwen_image_2512_fp8_e4m3fn.safetensors','weight_dtype':'default'}},
       'lora':{'class_type':'LoraLoaderModelOnly','inputs':{'model':['unet',0],'lora_name':'Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors' if edit else 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors','strength_model':1.0}},
       'shift':{'class_type':'ModelSamplingAuraFlow','inputs':{'model':['lora',0],'shift':3.0}},
       'clip':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen_2.5_vl_7b_fp8_scaled.safetensors','type':'qwen_image','device':'default'}},
       'vae':{'class_type':'VAELoader','inputs':{'vae_name':'qwen_image_vae.safetensors'}},
       'latent':{'class_type':'EmptySD3LatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
       'sample':{'class_type':'KSampler','inputs':{'model':['shift',0],'seed':seed,'steps':4,'cfg':1.0,'sampler_name':'euler','scheduler':'simple','positive':['pos',0],'negative':['neg',0],'latent_image':['latent',0],'denoise':1.0}},
       'decode':{'class_type':'VAEDecode','inputs':{'samples':['sample',0],'vae':['vae',0]}},
       'save':{'class_type':'SaveImage','inputs':{'images':['decode',0],'filename_prefix':'orbital'}}}
    if edit:
        images={}
        for i,name in enumerate(references):
            g[f'load{i}']={'class_type':'LoadImage','inputs':{'image':name}};images[f'image{i+1}']=[f'load{i}',0]
        g['pos']={'class_type':'TextEncodeQwenImageEditPlus','inputs':{'clip':['clip',0],'prompt':prompt,'vae':['vae',0],**images}}
        g['neg']={'class_type':'TextEncodeQwenImageEditPlus','inputs':{'clip':['clip',0],'prompt':'','vae':['vae',0],**images}}
    else:
        g['pos']={'class_type':'CLIPTextEncode','inputs':{'clip':['clip',0],'text':prompt}};g['neg']={'class_type':'CLIPTextEncode','inputs':{'clip':['clip',0],'text':''}}
    return g
def generate(host,prompt,out,seed=1,width=1024,height=1024,references=()):
    names=[upload(host,Path(p)) for p in references]
    job=json.loads(call(host,'/prompt',json.dumps({'prompt':workflow(prompt,seed,width,height,names)}).encode(),{'Content-Type':'application/json'}))['prompt_id']
    start=time.monotonic()
    while time.monotonic()-start<900:
        history=json.loads(call(host,f'/history/{job}'))
        if job in history:
            status=history[job].get('status',{})
            if status.get('status_str')=='error':raise RuntimeError(json.dumps(status)[:2000])
            for node in history[job]['outputs'].values():
                for image in node.get('images',[]):
                    Path(out).write_bytes(call(host,'/view?'+urllib.parse.urlencode(dict(filename=image['filename'],subfolder=image['subfolder'],type=image['type']))))
                    return time.monotonic()-start
        time.sleep(2)
    raise TimeoutError(job)

def batch(host,spec,out,only=()):
    """Generate every picture of assets/orbital/art.json that is missing (or named in only)."""
    data=json.loads(Path(spec).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for image in data['images']:
        target=out/f"{image['name']}.png"
        if (target.exists() and image['name'] not in only) or (only and image['name'] not in only):continue
        prompt=image['prompt'].format(style=data['style'],sprite=data['sprite'],keep=data['keep'])
        seconds=generate(host,prompt,target,image.get('seed',1),image.get('width',1024),image.get('height',1024),[out/f'{r}.png' for r in image.get('reference',[])])
        print(f"{image['name']}: {seconds:.0f} s",flush=True)
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',default='gx10-1');p.add_argument('--only',nargs='*',default=[],help='regenerate these names')
    p.add_argument('--spec',type=Path,default=root/'assets/orbital/art.json');p.add_argument('--out',type=Path,default=root/'assets/orbital/source/gen');a=p.parse_args()
    batch(a.host,a.spec,a.out,a.only)

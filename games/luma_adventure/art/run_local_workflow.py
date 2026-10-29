#!/usr/bin/env python3
"""Run one reviewed local ComfyUI graph, retain history, download every output."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from comfy_pipeline import request,write_json

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workflow',type=Path);p.add_argument('--name',required=True);p.add_argument('--output',type=Path);p.add_argument('--endpoint',default='http://gx10-2:8188');p.add_argument('--playlist',action='store_true')
    a=p.parse_args()
    if a.playlist:
        assert a.output,'A playlist needs an explicit output root'
        for path in json.loads(a.workflow.read_text()):
            path=Path(path);out=a.output/path.stem
            if (out/'submission.json').exists() and json.loads((out/'submission.json').read_text()).get('status')=='generated':
                print('Preserved completed '+path.stem,flush=True);continue
            subprocess.run([sys.executable,__file__,str(path),'--name',path.stem,'--output',str(out),'--endpoint',a.endpoint],check=True)
        return
    graph=json.loads(a.workflow.read_text());out=a.output or ROOT/'source'/a.name;out.mkdir(parents=True,exist_ok=True)
    if (out/'submission.json').exists():
        old=json.loads((out/'submission.json').read_text())
        if old.get('status')=='generated' and old.get('workflow_sha256')==hashlib.sha256(a.workflow.read_bytes()).hexdigest():
            for item in old['files']:assert hashlib.sha256((out/item['file']).read_bytes()).hexdigest()==item['sha256']
            print('Preserved completed '+a.name,flush=True);return
        raise RuntimeError('Existing job/result retained. Inspect its history or use a new revision name; refusing duplicate submission: '+old.get('prompt_id','unknown'))
    nodes=json.loads(request(a.endpoint,'/object_info'))
    for node in graph.values():
        schema=nodes[node['class_type']]
        if schema.get('api_node'):raise RuntimeError('External API node forbidden: '+node['class_type'])
    queue=json.loads(request(a.endpoint,'/queue'))
    if queue.get('queue_running') or queue.get('queue_pending'):raise RuntimeError('GPU queue is occupied; wait for the existing work, then retry.')
    response=json.loads(request(a.endpoint,'/prompt',dict(prompt=graph,client_id='luma-art-20261023')))
    job=response['prompt_id'];meta=dict(prompt_id=job,endpoint=a.endpoint,workflow=str(a.workflow),workflow_sha256=hashlib.sha256(a.workflow.read_bytes()).hexdigest(),submitted_unix=time.time(),status='queued')
    write_json(out/'submission.json',meta);print('Submitted '+a.name+' '+job,flush=True);start=time.monotonic()
    while time.monotonic()-start<2400:
        history=json.loads(request(a.endpoint,'/history/'+job))
        if job in history:
            write_json(out/'history.json',history);record=history[job]
            if record.get('status',{}).get('status_str')=='error':
                meta.update(status='error',execution_status=record['status']);write_json(out/'submission.json',meta)
                raise RuntimeError(json.dumps(record['status'],ensure_ascii=False)[:5000])
            files=[]
            for node_id,value in record.get('outputs',{}).items():
                for kind in ('images','audio'):
                    for file in value.get(kind,[]):
                        name=Path(file['filename']).name
                        body=request(a.endpoint,'/view?'+urllib.parse.urlencode({k:file[k] for k in ('filename','subfolder','type')}))
                        target=out/name;target.write_bytes(body);files.append(dict(node=node_id,kind=kind,file=name,server_file=file,sha256=hashlib.sha256(body).hexdigest()))
            if files:
                meta.update(status='generated',elapsed_seconds=round(time.monotonic()-start,2),files=files);write_json(out/'submission.json',meta)
                print(f'Completed {a.name}: {len(files)} files, {meta["elapsed_seconds"]}s',flush=True);return
        time.sleep(2)
    raise TimeoutError(job)

if __name__=='__main__':main()

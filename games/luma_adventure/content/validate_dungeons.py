#!/usr/bin/env python3
"""Solve authored room witnesses against doors, shots, crates, plates and order.

This checks structural puzzle feasibility. It does not claim combat AI,
controller timing, rendered appearance, duration or hardware qualification.
"""
from collections import deque
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent;D=ROOT/'dungeons'
def tile(p):return (round((p['x']-16)/32),round((p['y']-16)/32))

class RoomSolver:
    def __init__(self,w):
        self.w=w;self.e={e['id']:e for e in w['entities']};self.p=tile(w['spawn']);self.flags=0;self.cursor=0;self.crates={e['id']:tile(e) for e in w['entities'] if e['kind']=='crate'};self.steps=0;self.trace=[]
        self.plates=[e for e in w['entities'] if e['kind']=='plate'];self.plate_mask=sum(e['grants'] for e in self.plates);self.sequence_mask=sum(e['grants'] for e in w['entities'] if e['kind']=='sequence')
    def flags_at(self,p):
        result=self.flags&~self.plate_mask
        for e in self.plates:
            if tile(e)==p or tile(e) in self.crates.values():result|=e['grants']
        return result
    def enabled(self,e,p=None):
        flags=self.flags_at(self.p if p is None else p)
        return flags&e.get('requires',0)==e.get('requires',0) and not flags&e.get('forbids',0)
    def free(self,p,origin=None,ignore_crate=None,projectile=False):
        x,y=p
        if not (1<=x<self.w['width']-1 and 1<=y<self.w['height']-1):return False
        if self.w['terrain']['rows'][y][x] in ('#tH' if projectile else '#tH~'):return False
        if any(p==q and k!=ignore_crate for k,q in self.crates.items()):return False
        return not any(e['kind']=='door' and tile(e)==p and not self.enabled(e,origin or self.p) for e in self.e.values())
    def walk(self,target,near=False):
        queue=deque([self.p]);prev={self.p:None};goal=None
        while queue:
            p=queue.popleft()
            if p==target or (near and math.dist(p,target)<=1.5):goal=p;break
            for q in [(p[0]+1,p[1]),(p[0]-1,p[1]),(p[0],p[1]+1),(p[0],p[1]-1)]:
                if q not in prev and self.free(q,p):prev[q]=p;queue.append(q)
        assert goal is not None,(self.w['id'],'unreachable',self.p,target,self.flags_at(self.p),self.crates)
        path=[];p=goal
        while prev[p] is not None:path.append(p);p=prev[p]
        self.steps+=len(path);self.p=goal;return list(reversed(path))
    def line_clear(self,target):
        x,y=self.p;xx,yy=target;dx=xx-x;dy=yy-y;n=max(abs(dx),abs(dy))
        assert math.hypot(dx,dy)*32<=414,'Target beyond projectile lifetime'
        return all(self.free((round(x+dx*i/n),round(y+dy*i/n)),self.p,projectile=True) for i in range(1,n)) if n else True
    def apply(self,a):
        e=self.e[a['target']];kind=a['action'];walk=[]
        if kind=='push':
            assert e['kind']=='crate';walk=self.walk(tile(a['from']));dx,dy=a['direction'];assert abs(dx)+abs(dy)==1
            for _ in range(a['count']):
                box=self.crates[e['id']];assert self.p==(box[0]-dx,box[1]-dy),(self.w['id'],'push stance',self.p,box)
                dest=(box[0]+dx,box[1]+dy);assert self.free(dest,self.p,ignore_crate=e['id']),(self.w['id'],'blocked crate',dest)
                self.crates[e['id']]=dest;self.p=box;self.steps+=1
        elif kind=='shoot':
            assert e['kind']=='target';walk=self.walk(tile(a['from']));assert self.enabled(e);assert self.line_clear(tile(e)),(self.w['id'],'blocked shot')
            self.flags^=e['grants']
        elif kind=='defeat':
            assert e['kind'] in ('enemy','boss');walk=self.walk(tile(e),near=True);assert self.enabled(e);self.flags|=e['grants']
        else:
            walk=self.walk(tile(e),near=True);assert self.enabled(e),(self.w['id'],'requirements/forbids',e['id'])
            if kind=='exit':assert e['kind']=='door'
            elif e['kind']=='switch':self.flags^=e['grants']
            elif e['kind']=='sequence':
                if e['cost']!=self.cursor+1:self.flags&=~self.sequence_mask;self.cursor=0
                if e['cost']==self.cursor+1:self.cursor+=1;self.flags|=e['grants']
            else:self.flags|=e['grants']
        self.trace.append(dict(action=a,walking_tiles=len(walk),flags=self.flags_at(self.p),player=list(self.p),crates={k:list(v) for k,v in self.crates.items()}))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',default='dungeons',choices=['dungeons','canopy_candidate'])
    args=parser.parse_args();directory=ROOT/args.directory
    manifest=json.loads((directory/'manifest.json').read_text());solutions=json.loads((directory/'solutions.json').read_text());reports=[]
    assert len(manifest['worlds'])==len(solutions['rooms'])
    for filename,witness in zip(manifest['worlds'],solutions['rooms']):
        w=json.loads((ROOT/filename).read_text());assert w['indoors'] and w['id']==witness['id']
        assert len(w['terrain']['rows'])==24 and all(len(r)==32 for r in w['terrain']['rows'])
        assert len(w['entities'])<=64 and len({e['id'] for e in w['entities']})==len(w['entities'])
        for e in w['entities']:
            assert not e.get('requires',0)&e.get('forbids',0),(w['id'],e['id'],'contradictory requirements')
            assert e.get('behavior','melee') in ('melee','turret')
            assert e.get('hp',0)>=0 and e.get('shot_period',0)>=0
        solver=RoomSolver(w)
        for a in witness['solution']:solver.apply(a)
        assert witness['solution'][-1]['action']=='exit'
        reports.append(dict(world=witness['world'],id=w['id'],status='PASS',walking_tiles=solver.steps,final_flags=solver.flags_at(solver.p),actions=solver.trace))
    assert reports[-1]['final_flags']&32
    result=dict(status='PASS',scope='Structural movement, positive/negative door prerequisites, projectile range/line, crate pushes, held plates, ordered sequences, declared combat rewards and exits. Actual runtime inputs/combat/save/reset/rendering/duration remain separate checks.',rooms=reports,inputs={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in manifest['worlds']+[args.directory+'/solutions.json']})
    (directory/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS: '+str(len(reports))+' rooms solved by their concrete action witnesses; '+str(sum(r['walking_tiles'] for r in reports))+' walking/pushing tiles. Runtime duration not inferred.')

if __name__=='__main__':main()

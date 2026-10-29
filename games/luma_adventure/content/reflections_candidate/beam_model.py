#!/usr/bin/env python3
"""Independent discrete beam model and movement witness validation.

The ray model does not invoke engine code. Mirrors/crates are solid to the
player; doors remain transparent to light, preventing receiver/door feedback.
"""
from copy import deepcopy
from functools import reduce
from operator import or_
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_dungeons import RoomSolver,tile

DIRS=((1,0),(0,1),(-1,0),(0,-1))
REFLECT=((3,2,1,0),(1,0,3,2))
def union(values):return reduce(or_,values,0)
def enabled(e,flags):return flags&e.get('requires',0)==e.get('requires',0) and not flags&e.get('forbids',0)

def trace(w,orientations=None,crates=None,flags=0):
    mirrors={tile(e):e for e in w['entities'] if e['kind']=='mirror'}
    receivers={tile(e):e for e in w['entities'] if e['kind']=='receiver'}
    orientations=orientations or {e['id']:e.get('orientation',0) for e in mirrors.values()}
    occupied=set(crates.values()) if isinstance(crates,dict) else set(crates) if crates is not None else {tile(e) for e in w['entities'] if e['kind']=='crate'}
    mask=0;paths=[];used=set();hit=set();loops=0
    for source in (e for e in w['entities'] if e['kind']=='emitter'):
        if not enabled(source,flags) or tile(source) in occupied:continue
        x,y=tile(source);direction=source['direction'];visited=set();path=[];reason='edge'
        while True:
            dx,dy=DIRS[direction];x+=dx;y+=dy
            if not(0<=x<w['width'] and 0<=y<w['height']):break
            state=(x,y,direction)
            if state in visited:reason='loop';loops+=1;break
            visited.add(state)
            if w['terrain']['rows'][y][x] in '#tH':reason='wall';break
            if (x,y) in occupied:reason='crate';break
            path.append(state)
            if (x,y) in receivers:
                receiver=receivers[x,y];mask|=receiver['grants'];hit.add(receiver['id'])
            if (x,y) in mirrors:
                mirror=mirrors[x,y];used.add(mirror['id']);direction=REFLECT[orientations[mirror['id']]][direction]
        paths.append(dict(source=source['id'],cells=path,stop=reason))
    return dict(flags=mask,paths=paths,mirrors=sorted(used),receivers=sorted(hit),loops=loops)

def configurations(w,crates=None,flags=0):
    mirrors=[e for e in w['entities'] if e['kind']=='mirror'];goal=w['design']['beam_goal'];answers=[]
    for bits in range(1<<len(mirrors)):
        orientations={e['id']:(bits>>i)&1 for i,e in enumerate(mirrors)};result=trace(w,orientations,crates,flags)
        if result['flags']&goal['on']==goal['on'] and not result['flags']&goal['off']:
            answers.append(dict(bits=bits,orientations=orientations,used_mirrors=result['mirrors'],receiver_flags=result['flags']))
    assert answers,(w['id'],'no beam configuration solves the goal')
    return answers

def choose_configuration(w,crates=None,flags=0,farthest=False):
    mirrors=[e for e in w['entities'] if e['kind']=='mirror'];answers=configurations(w,crates,flags)
    initial=sum(e.get('orientation',0)<<i for i,e in enumerate(mirrors))
    if farthest:
        initial=max(range(1<<len(mirrors)),key=lambda state:(min((state^a['bits']).bit_count() for a in answers),-state))
        for i,e in enumerate(mirrors):e['orientation']=(initial>>i)&1
    answer=min(answers,key=lambda a:((initial^a['bits']).bit_count(),a['bits']))
    proof=dict(initial_bits=initial,solution_bits=answer['bits'],minimum_rotations_for_fixed_crates_and_source_flags=(initial^answer['bits']).bit_count(),
        complete_assignments_examined=1<<len(mirrors),valid_assignments=len(answers),source_flags=flags,
        final_crate_positions={k:list(v) for k,v in (crates or {}).items()} if isinstance(crates,dict) else None,
        goal=w['design']['beam_goal'],used_mirrors=answer['used_mirrors'],scope='Exhaustive mirror assignments with stated fixed crate positions and non-receiver source flags; not a global minimum over crate moves or walking.')
    return answer['orientations'],proof

class BeamRoomSolver(RoomSolver):
    def __init__(self,w):
        super().__init__(w)
        self.mirrors={e['id']:tile(e) for e in w['entities'] if e['kind']=='mirror'}
        self.orientations={e['id']:e.get('orientation',0) for e in w['entities'] if e['kind']=='mirror'}
        self.receiver_mask=union(e['grants'] for e in w['entities'] if e['kind']=='receiver')
        self._beam_cache={}
    def flags_at(self,p):
        base=super().flags_at(p)&~self.receiver_mask
        key=(tuple(self.orientations.items()),tuple(sorted(self.crates.items())),base)
        if key not in self._beam_cache:self._beam_cache[key]=trace(self.w,self.orientations,self.crates,base)['flags']
        return base|self._beam_cache[key]
    def free(self,p,origin=None,ignore_crate=None,projectile=False):
        if p in self.mirrors.values():return False
        return super().free(p,origin,ignore_crate,projectile)
    def apply(self,a):
        if a['action']=='rotate':
            e=self.e[a['target']];assert e['kind']=='mirror';assert a.get('count',1) in (1,2)
            path=self.walk(tile(a['from'])) if 'from' in a else self.walk(tile(e),near=True)
            assert (self.p[0]-tile(e)[0])**2+(self.p[1]-tile(e)[1])**2<=2.25,(self.w['id'],'mirror interaction out of range')
            self.orientations[e['id']]^=a.get('count',1)&1
            self.trace.append(dict(action=a,walking_tiles=len(path),flags=self.flags_at(self.p),player=list(self.p),crates={k:list(v) for k,v in self.crates.items()}))
        else:super().apply(a)
        self.trace[-1]['mirrors']=dict(self.orientations)
    def rotation_action(self,eid):
        trial=deepcopy(self);trial.walk(self.mirrors[eid],near=True)
        return dict(action='rotate',target=eid,count=1,**{'from':dict(x=trial.p[0]*32+16,y=trial.p[1]*32+16)})

def validate_contract(w):
    entities=w['entities'];receivers=[e for e in entities if e['kind']=='receiver'];receiver_mask=union(e['grants'] for e in receivers)
    assert len(entities)<=64 and len({e['id'] for e in entities})==len(entities)
    assert len({tile(e) for e in entities})==len(entities),(w['id'],'initial entities overlap')
    assert len([e for e in entities if e['kind']=='emitter'])<=4
    assert len([e for e in entities if e['kind']=='mirror'])<=12
    assert all(e['grants']>0 and e['grants']&(e['grants']-1)==0 for e in receivers)
    assert sum(e['grants'] for e in receivers)==receiver_mask,'Receiver bits must be unique'
    for e in entities:
        x,y=tile(e);assert 0<x<w['width']-1 and 0<y<w['height']-1
        assert e['x']==x*32+16 and e['y']==y*32+16
        assert not(e.get('requires',0)&e.get('forbids',0))
        if e['kind']=='emitter':
            assert e['direction'] in range(4)
            assert not receiver_mask&(e.get('requires',0)|e.get('forbids',0)),'No receiver/source feedback'
        if e['kind']=='mirror':assert e['orientation'] in (0,1)
        if e['kind'] not in ('receiver','lamp','mirror','emitter','door','sign'):
            assert not e.get('grants',0)&receiver_mask,'Receiver bit reused by another producer'
    return receiver_mask

#!/usr/bin/env python3
"""Original deterministic crate puzzles, generated backwards and solved by A*.

No timer or padding is used. Difficulty is described by concrete pushes and
search states, never converted into an invented play duration.
"""
from collections import deque
from functools import lru_cache
from heapq import heappop,heappush
from itertools import permutations
import random

DIRS=((1,0),(-1,0),(0,1),(0,-1))
def plus(p,d):return (p[0]+d[0],p[1]+d[1])
def minus(p,d):return (p[0]-d[0],p[1]-d[1])

def reachable(floor,boxes,start):
    boxes=set(boxes);seen={start};queue=[start]
    for p in queue:
        for d in DIRS:
            q=plus(p,d)
            if q in floor and q not in boxes and q not in seen:seen.add(q);queue.append(q)
    return frozenset(seen)

def solve(floor,boxes,start,goals,max_states=60000):
    floor=frozenset(floor);goals=tuple(sorted(goals));boxes=tuple(sorted(boxes));goal_set=frozenset(goals)
    backwards=[]
    for goal in goals:
        distance={goal:0};queue=[goal]
        for p in queue:
            for d in DIRS:
                before=minus(p,d);stance=minus(before,d)
                if before in floor and stance in floor and before not in distance:distance[before]=distance[p]+1;queue.append(before)
        backwards.append(distance)
    assignments=tuple(permutations(range(len(boxes))))
    @lru_cache(maxsize=100000)
    def heuristic(bs):
        return min(sum(backwards[g].get(bs[b],10000) for g,b in enumerate(perm)) for perm in assignments)
    @lru_cache(maxsize=100000)
    def reach(bs,p):return reachable(floor,bs,p)
    first=(boxes,min(reach(boxes,start)));cost={first:0};previous={};heap=[(heuristic(boxes),0,0,first)];serial=0;expanded=0
    while heap and expanded<max_states:
        _,g,_,state=heappop(heap)
        if cost.get(state)!=g:continue
        bs,p=state;expanded+=1
        if frozenset(bs)==goal_set:
            solution=[]
            while state in previous:
                state,move=previous[state];solution.append(move)
            return dict(pushes=g,expanded=expanded,solution=list(reversed(solution)),optimal=True)
        area=reach(bs,p);occupied=set(bs)
        for b in bs:
            for d in DIRS:
                stance=minus(b,d);dest=plus(b,d)
                if stance not in area or dest not in floor or dest in occupied:continue
                nxt=tuple(sorted((occupied-{b})|{dest}));h=heuristic(nxt)
                if h>=10000:continue
                new=(nxt,min(reach(nxt,b)))
                if cost.get(new,10**9)<=g+1:continue
                cost[new]=g+1;previous[new]=(state,dict(box=list(b),direction=list(d),stance=list(stance)))
                serial+=1;heappush(heap,(g+1+h,g+1,serial,new))
    return dict(pushes=None,expanded=expanded,solution=None,optimal=False)

def generate(seed,box_count=3,min_pushes=14,attempts=18):
    rng=random.Random(seed);best=None
    for attempt in range(attempts):
        floor={(x,y) for y in range(1,8) for x in range(1,10)}
        protected={(1,4),(2,4),(9,4),(8,4)}
        for p in rng.sample(sorted(floor-protected),rng.randint(9,15)):floor.remove(p)
        floor=set(reachable(floor,(),(1,4)))
        if len(floor)<45 or (9,4) not in floor:continue
        goals=tuple(rng.sample(sorted(floor),box_count));boxes=list(goals)
        player=rng.choice(sorted(floor-set(boxes)));seen=set()
        for _ in range(100):
            area=reachable(floor,boxes,player);options=[]
            for i,b in enumerate(boxes):
                for d in DIRS:
                    near=plus(b,d);far=plus(near,d)
                    if near not in area or far not in floor or far in boxes:continue
                    new=boxes.copy();new[i]=near;key=(tuple(sorted(new)),min(reachable(floor,new,far)))
                    if key not in seen:options.append((i,near,far,key))
            if not options:break
            i,near,player,key=rng.choice(options);boxes[i]=near;seen.add(key)
        if set(boxes)==set(goals):continue
        answer=solve(floor,boxes,player,goals)
        if answer['solution'] is None:continue
        result=dict(seed=seed,attempt=attempt,width=11,height=9,rows=[''.join('.' if (x,y) in floor else '#' for x in range(11)) for y in range(9)],boxes=[list(p) for p in boxes],goals=[list(p) for p in goals],player=list(player),proof=answer)
        if best is None or answer['pushes']>best['proof']['pushes']:best=result
        if answer['pushes']>=min_pushes:return result
    if best is None:raise RuntimeError('No solvable puzzle generated for seed '+str(seed))
    if best['proof']['pushes']<min_pushes:raise RuntimeError(f'Only {best["proof"]["pushes"]} pushes found for seed {seed}; minimum {min_pushes} not met.')
    return best

def solve_lights(masks,target,forbids=0):
    queue=deque([0]);previous={0:None}
    while queue:
        state=queue.popleft()
        if state&target==target and not state&forbids:
            answer=[]
            while previous[state] is not None:state,i=previous[state];answer.append(i)
            return list(reversed(answer))
        for i,mask in enumerate(masks):
            nxt=state^mask
            if nxt not in previous:previous[nxt]=(state,i);queue.append(nxt)
    raise ValueError('Unreachable lamp pattern')

if __name__=='__main__':
    import json
    for seed in (1062401,1062402,1062403):
        p=generate(seed);print(json.dumps(dict(seed=seed,attempt=p['attempt'],pushes=p['proof']['pushes'],states=p['proof']['expanded'],rows=p['rows'],boxes=p['boxes'],goals=p['goals'],player=p['player'])),flush=True)

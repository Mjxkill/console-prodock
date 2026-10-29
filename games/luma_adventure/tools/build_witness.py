#!/usr/bin/env python3
"""Compile authored puzzle witnesses for an input-only C regression player."""
import argparse,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,action='append');parser.add_argument('--out',type=Path,default=root/'build/puzzle_witness.h');args=parser.parse_args()
if args.source:sources=args.source
else:
 paths=json.loads((root/'content/campaign.json').read_text())['worlds'];sources=sorted({(root/'content'/path).parent/'solutions.json' for path in paths if ((root/'content'/path).parent/'solutions.json').exists()})
groups=sorted([json.loads(source.read_text())['rooms'] for source in sources],key=lambda rooms:rooms[0]['world'])
rooms=[room for group in groups for room in group]
assert len({r['world'] for r in rooms})==len(rooms)
lines=['/* Generated test witnesses; never linked into the game. */','typedef struct {unsigned world;const char *action,*target;float x,y,dx,dy;unsigned count;} PuzzleStep;','static const PuzzleStep puzzle_steps[]={']
for room in rooms:
 for s in room['solution']:
  point=s.get('from',{});direction=s.get('direction',[0,0])
  values=[str(room['world']),json.dumps(s['action']),json.dumps(s['target']),str(point.get('x',0)),str(point.get('y',0)),str(direction[0]),str(direction[1]),str(s.get('count',1))]
  lines.append('{'+','.join(values)+'},')
lines+=['};','typedef struct {unsigned first,last,begin,end;} PuzzleGroup;','static const PuzzleGroup puzzle_groups[]={']
offset=0
for group in groups:
 end=offset+sum(len(room['solution']) for room in group);lines.append('{'+','.join(map(str,[group[0]['world'],group[-1]['world'],offset,end]))+'},');offset=end
lines+=['};']
args.out.write_text('\n'.join(lines)+'\n')

#!/usr/bin/env python3
"""Prepare local ComfyUI candidates without touching the live atlas or maps."""
import json
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ART=HERE.parents[2]
sys.path.insert(0,str(ART))
from comfy_pipeline import request,choices,choose_workflow

def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    endpoint='http://gx10-2:8188'
    # Snapshots are obtained with the existing authorized read-only curl
    # capability. Preparation itself stays offline and submits no GPU job.
    nodes=json.loads((HERE/'provenance/object_info.json').read_text())
    stats=json.loads((HERE/'provenance/system_stats.json').read_text())
    models={node:choices(nodes,node,key) for node,key in [('UNETLoader','unet_name'),('CLIPLoader','clip_name'),('VAELoader','vae_name'),('LoraLoaderModelOnly','lora_name'),('CheckpointLoaderSimple','ckpt_name')]}
    for folder in ('workflows','provenance','renders','imported'): (HERE/folder).mkdir(exist_ok=True)
    write(HERE/'provenance/object_info.json',nodes);write(HERE/'provenance/system_stats.json',stats);write(HERE/'provenance/models.json',models)
    write(HERE/'provenance/discovery.json',dict(endpoint=endpoint,checked_unix=time.time(),status='responding',service_lifecycle_actions=[]))
    style="Original cozy fantasy adventure game props, warm hand-painted storybook illustration, the same consistent slightly overhead three-quarter camera for every object, amber upper-left light, cool deep teal shadows, copper metal, carved old wood, muted mossy slate stone. Simple bold silhouettes readable at 32 pixels, three broad value groups, sparse small details. No photorealism, no characters, no text, no letters, no symbols resembling writing. "
    props=dict(name='sanctuary_props',seed=2026102401,width=1152,height=768,type='sprites',grid=[3,2],ids=['crate','switch','plate','target','lamp','turret'],
        prompt=style+"A PROFESSIONAL SPRITE SHEET with exactly THREE COLUMNS and TWO ROWS, SIX equal square cells. One complete isolated game prop centered in each cell, generous empty margins, no overlap. First row from left to right: (1) a square wooden seed CRATE with crossed timber braces and copper corners, closed flat lid, unmistakably a pushable box; (2) a mechanical SWITCH with a long copper lever tilted left, set into a squat mossy stone pedestal, large handle visible; (3) a very flat circular PRESSURE PLATE lying on the floor, dark central wooden disk inset into a thick copper ring, no pedestal, no vertical parts. Second row from left to right: (4) an archery TARGET made of a large upright circular copper ring with a dark turquoise center and bright cream bullseye, held by two short stone feet; (5) a small tall freestanding LAMP with a cream glass globe held within curved copper leaf ribs on a narrow dark teal stem and round stone foot, no lever and no target ring; (6) a stationary magical TURRET, a squat mossy stone owl automaton on a broad circular base, two amber eye lenses and a short round copper emitter projecting forwards from its chest, no wheels, no legs. Entire canvas a plain uniform saturated MAGENTA backdrop. No surrounding landscape, no ground square, no scenery, no base tile, no border, no visible grid, no drop shadow outside objects. Six separate usable assets, all fully inside their cells.")
    material="A single flat seamless material texture filling the whole square edge to edge, painted for a top-down storybook adventure game. Strict overhead surface with uniform diffuse lighting everywhere. Extremely low contrast, small evenly distributed brush texture, a few tiny chips. Absolutely no central highlight, no vignette, no borders, no scenery, no objects, no frame, no perspective, no light beam, no large cracks, no drawn tile grid. All edges have matching brightness and color statistics. Calm continuous material, useful after downsampling to 32 pixel game tiles. "
    floor=dict(name='indoor_floor',seed=2026102402,width=1024,height=1024,type='terrain',grid=[4,4],ids=['indoor_floor']+[f'indoor_floor_{i:02}' for i in range(1,16)],prompt=material+"Material: old smooth limestone floor, muted medium-light gray sage and soft pale olive, warm ivory speckles very sparse, broad quiet muted colors. No plants, no grass, no pathways, no brown earth. Restrained hand-painted surface using a small family of closely related sage-gray colors.")
    wall=dict(name='indoor_wall',seed=2026102403,width=1024,height=1024,type='terrain',grid=[4,4],ids=['indoor_wall']+[f'indoor_wall_{i:02}' for i in range(1,16)],prompt=material+"Material: dark blue-green slate capstone, cool deep muted teal with a little gray jade mineral grain, a dense solid stone surface. Much darker than a sage limestone floor. No bricks, no individual outlined blocks, no moss clumps, no plants. Restrained hand-painted surface using a small family of closely related deep teal colors.")
    specs=[props,floor,wall];write(HERE/'brief.json',dict(schema=1,status='candidate_not_integrated',endpoint=endpoint,images=specs))
    for spec in specs:
        graph=choose_workflow(spec,nodes,models)
        assert all(not nodes[n['class_type']].get('api_node') for n in graph.values())
        write(HERE/'workflows'/(spec['name']+'.json'),graph)
    print('Prepared three reviewed local workflows; live atlas/content untouched.')

if __name__=='__main__':main()

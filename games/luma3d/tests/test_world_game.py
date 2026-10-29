#!/usr/bin/env python3
"""Replay authored JSON through the real C simulation, without renderer or state injection.

The generated fixture independently implements the declared triangle, capsule,
water and bridge contract. Production adapters must match this contract.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def cfloat(value):
    return f'{float(value):.9f}f'


def row(values):
    return '{' + ','.join(cfloat(x) for x in values) + '}'


def main():
    s = json.loads((ROOT / 'world/scene.json').read_text())
    h = json.loads((ROOT / 'world/heightfield.json').read_text())
    assert h['width'] == h['height'] == 81 and h['spacing'] == 2 and h['origin'] == [0, 0]
    assert h['interpolation'] == 'triangular_00_to_11'
    heights = ',\n'.join(row(x) for x in h['heights'])
    route = ','.join(row([p['x'], p['y'], p['z']]) for p in s['gameplay']['route'])
    items = ','.join(row(p['position']) for p in s['gameplay']['collectibles'])
    circles = []
    bridges = []
    for c in s['colliders']:
        if c['kind'] == 'circle':
            circles.append(row([c['x'], c['z'], c['radius'], c['min_y'], c['max_y']]))
        elif c['kind'] == 'walkable_bridge':
            bridges.append(row([c['x'], c['z'], c['length'], c['width'], c['y'], c['arch_height'], c['yaw']]))
        else:
            raise ValueError(f"Unimplemented collider in independent test: {c['kind']}")
    waters = []
    ribbons = []
    for w in s['water_zones']:
        if w['kind'] == 'ellipse':
            waters.append(f'if (powf((x-{cfloat(w["x"])})/{cfloat(w["rx"]+0.3)},2)+powf((z-{cfloat(w["z"])})/{cfloat(w["rz"]+0.3)},2)<1 && {cfloat(w["level"])}-ground(x,z)>.65f && y<{cfloat(w["level"])}+.2f) return 1;')
        elif w['kind'] == 'ribbon':
            for a,b in zip(w['points'], w['points'][1:]):
                ribbons.append(row([*a,*b,w['width']*.5,w['level']]))
        else:
            raise ValueError(f"Unimplemented water in independent test: {w['kind']}")
    code = '''#include "luma3d_game.h"
#include <math.h>
#include <stdio.h>
#include <assert.h>
#define COUNT(a) (sizeof(a)/sizeof((a)[0]))
'''
    code += 'static const float terrain[81][81]={' + heights + '};\n'
    code += 'static const float circles[][5]={' + ','.join(circles) + '};\n'
    code += 'static const float bridges[][7]={' + ','.join(bridges) + '};\n'
    code += 'static const float ribbons[][6]={' + ','.join(ribbons) + '};\n'
    code += 'static const L3Vec3 route[]={' + route + '}, items[]={' + items + '};\n'
    code += '''
static float ground(float x,float z) {
    x=fminf(159.9999f,fmaxf(0,x)); z=fminf(159.9999f,fmaxf(0,z));
    int ix=(int)(x/2), iz=(int)(z/2); float u=x/2-ix,v=z/2-iz;
    float a=terrain[iz][ix],b=terrain[iz][ix+1],c=terrain[iz+1][ix+1],d=terrain[iz+1][ix];
    return u>=v ? a+(b-a)*u+(c-b)*v : a+(c-d)*u+(d-a)*v;
}
static int on_bridge(float x,float z,float margin,float *y) {
    for (unsigned i=0;i<COUNT(bridges);++i) {
        const float *b=bridges[i]; float dx=x-b[0],dz=z-b[1];
        float u=cosf(b[6])*dx-sinf(b[6])*dz,v=sinf(b[6])*dx+cosf(b[6])*dz;
        if (fabsf(u)<=b[2]/2 && fabsf(v)<=b[3]/2-margin) {
            *y=b[4]+b[5]*sinf(3.14159265358979f*(u/b[2]+.5f)); return 1;
        }
    }
    return 0;
}
static float height(void *ctx,float x,float z) {
    (void)ctx; float y=ground(x,z),deck;
    if (on_bridge(x,z,0,&deck)) y=fmaxf(y,deck);
    return y;
}
static int blocked(void *ctx,float x,float y,float z,float r,float h) {
    (void)ctx;
    for (unsigned i=0;i<COUNT(circles);++i) {
        const float *c=circles[i];
        if (y<c[4] && y+h>c[3] && hypotf(x-c[0],z-c[1])<r+c[2]) return 1;
    }
    float deck;
    if (on_bridge(x,z,r,&deck) && y>=deck-.1f) return 0;
'''
    code += '\n'.join(waters)
    code += '''
    for (unsigned i=0;i<COUNT(ribbons);++i) {
        const float *p=ribbons[i]; float dx=p[2]-p[0],dz=p[3]-p[1];
        float f=fminf(1,fmaxf(0,((x-p[0])*dx+(z-p[1])*dz)/(dx*dx+dz*dz)));
        if (hypotf(x-p[0]-f*dx,z-p[1]-f*dz)<p[4]+r && p[5]-ground(x,z)>.65f && y<p[5]+.2f) return 1;
    }
    return 0;
}
int main(void) {
    L3World w={0}; L3Game g;
    w.height=height; w.blocked=blocked; w.max_x=w.max_z=160;
'''
    code += 'w.spawn=(L3Vec3)' + row(s['spawn']['position']) + ';\n'
    code += 'w.spawn_yaw=' + cfloat(s['spawn']['heading']) + ';\n'
    code += 'w.goal=(L3Vec3)' + row(s['gameplay']['goal']['position']) + ';\n'
    code += 'w.goal_radius=' + cfloat(s['gameplay']['goal']['radius']) + ';\n'
    code += '''
    w.route=route; w.route_count=COUNT(route); w.collectibles=items; w.collectible_count=COUNT(items);
    assert(l3_game_init(&g,&w,1));
    float worst_stuck=0,max_camera_burial=0;
    for (int frame=0;frame<36000;++frame) {
        L3Vec3 before=g.player.position;
        l3_game_step(&g,NULL,1.0f/60);
        assert(hypotf(g.player.position.x-before.x,g.player.position.z-before.z)<.12f);
        assert(!blocked(NULL,g.player.position.x,g.player.position.y,g.player.position.z,.3f,1.65f));
        worst_stuck=fmaxf(worst_stuck,g.autopilot_stuck_seconds);
        max_camera_burial=fmaxf(max_camera_burial,height(NULL,g.camera.eye.x,g.camera.eye.z)-g.camera.eye.y);
        if (g.autopilot_stuck_seconds>3) {
            fprintf(stderr,"STUCK frame=%d time=%.2f position=(%.3f,%.3f,%.3f) route=%u direction=%d pickups=%u\\n",frame,g.time,g.player.position.x,g.player.position.y,g.player.position.z,g.route_index,g.route_direction,g.collected_count);
            return 2;
        }
        if (g.completed_routes>=2) {
            printf("{\\"passed\\":%s,\\"frames\\":%d,\\"simulation_seconds\\":%.3f,\\"walked_metres\\":%.3f,\\"collected\\":%u,\\"objective_complete\\":%d,\\"route_legs\\":%u,\\"worst_stuck_seconds\\":%.3f,\\"camera_burial_metres\\":%.3f}\\n",g.objective_complete?"true":"false",frame+1,(frame+1)/60.0,g.distance_walked,g.collected_count,g.objective_complete,g.completed_routes,worst_stuck,max_camera_burial);
            return !g.objective_complete;
        }
    }
    fputs("TIMEOUT: no complete physical return through the valley\\n",stderr); return 3;
}
'''
    build = ROOT / 'build/gameplay'
    build.mkdir(parents=True, exist_ok=True)
    source = build / 'world_fixture.c'
    source.write_text(code)
    binary = build / 'test_world'
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror',f'-I{ROOT / "include"}',str(ROOT / 'src/game.c'),str(source),'-lm','-o',str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    print(result.stdout, end='')
    print(result.stderr, end='')
    report = {'passed': result.returncode == 0, 'returncode': result.returncode,
              'stdout': result.stdout, 'stderr': result.stderr,
              'context': 'Local JSON witness through real gameplay; independent collision adapter; no rendering/hardware claim',
              'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          [ROOT/'world/scene.json', ROOT/'world/heightfield.json', ROOT/'src/game.c',ROOT/'include/luma3d_game.h',Path(__file__)]}}
    if result.returncode == 0:
        report['measurement'] = json.loads(result.stdout)
    (build / 'result.json').write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()

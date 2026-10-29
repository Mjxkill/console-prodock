#!/usr/bin/env python3
"""G3D1: independent integer geometry + exact GPU pixels under DDR/CDC stalls."""
import argparse,hashlib,json,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from gpu_geometry_model import Geometry,Camera,mesh_bytes,pack,q16
from test_gpu_v1 import Model,xy
from test_gpu_accel import triangle_pixels

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'TESTS/gpu_geometry_20261010/rtl');p.add_argument('--source-root',type=Path,default=ROOT);p.add_argument('--read-min',type=int,default=3);p.add_argument('--neo-response',action='store_true');p.add_argument('--mem-half-period',type=float,default=6.666);p.add_argument('--world',action='store_true');p.add_argument('--world-phase',type=int);p.add_argument('--bus-stage',action='store_true');p.add_argument('--mixed-raster',action='store_true');p.add_argument('--invalid-descriptors',action='store_true');p.add_argument('--reset-phases',action='store_true');p.add_argument('--viewport-extrema',action='store_true');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 if a.world_phase is not None and not a.world:p.error('--world-phase requires --world')
 if a.mixed_raster and a.world:p.error('--mixed-raster uses the diagnostic scene')
 if (a.reset_phases or a.invalid_descriptors or a.viewport_extrema) and a.world:p.error('Reset/descriptor/extrema tests use the diagnostic scene')
 if a.world:
  from render_world3d import World,State
  from astra_preview_model import FastPixels
  class FastModel(FastPixels,Model):pass
  world=World();pixels=FastModel();g=Geometry(pixels);remapped=[];texture_addresses={};texture_end=0x1700000
  g.upload(0x1740000,world.mesh)
  states=[(0,world.state(0)),(1111,State(0,-.7,13.8,0,0,0,-.7,14,64)),(1111,State(0,-2,1,0,8,4,-2,7,90))]
  if a.world_phase is not None:states=[(a.world_phase,world.state(a.world_phase))]
  for frame,state in states:
   commands,_=world.commands(frame,state)
   for c in commands:
    op=c[0]>>24
    if op==22:c[2]=0x900000
    if op==24:
     base=c[1];size=(c[2]&65535)*(c[3]&65535)
     if base not in texture_addresses:
      texture_addresses[base]=texture_end;g.upload(texture_end,world.assets[base-world.base:base-world.base+size]);texture_end+=size
     c[1]=texture_addresses[base]
    if op==34:c[1]=c[1]-0x06000000+0x1740000;c[2]=c[2]-0x06000000+0x1740000
    remapped.append(c)
  assert texture_end<=0x1740000
  initial=bytes(pixels.memory)
  for c in remapped:g.command(c)
  bad_count=0
 else:
  pixels=Model();g=Geometry(pixels)
  # A single mixed scene retains overlapping depth/alpha results from every draw.
  tex=bytearray()
  for y in range(32):
   for x in range(32):tex+=struct.pack('<H',((x*31//31)<<11)|((y*63//31)<<5)|((x^y)&31))
  g.upload(0x1700000,tex)
  points=[(-1,-1,2),(1,-1,2),(0,1,2),(-1,-1,.1),(1,-1,3),(0,1,3),(-9,-2,2),(8,-2,2),(0,7,2)]
  faces=[([0,2,1],[(0,0),(16,31),(31,0)],(0,0,-1),(256,200,160),0),
         ([3,5,4],[(0,0),(16,31),(31,0)],(0,0,-1),(160,256,180),0),
         ([6,8,7],[(0,0),(16,31),(31,0)],(0,0,-1),(180,180,256),0)]
  vb,fb=0x1740000,0x1748000
  v,f=mesh_bytes(points,faces);g.upload(vb,v);g.upload(fb,f)
  tiny_v,tiny_f=mesh_bytes([(0,0,.25),(.003125,0,.25),(0,.003125,.25)],
   [([0,2,1],[(-32767,-32767),(32767,-32767),(-32767,32767)],(0,0,-1),(256,256,256),1)])
  g.upload(0x1750000,tiny_v);g.upload(0x1758000,tiny_f)
  broken=bytearray(f[:64]);broken[32]=len(points);g.upload(0x1760000,broken)
  # Exercise the complete vertex-cache address range, including index 255.
  wide_points=[(-1,-1,2)]+[(0,0,4)]*253+[(1,-1,2),(0,1,2)]
  wide_v,wide_f=mesh_bytes(wide_points,[([0,255,254],[(0,0),(16,31),(31,0)],(0,0,-1),(256,256,256),0)])
  g.upload(0x1768000,wide_v);g.upload(0x176c000,wide_f)
  seam_v,seam_f=mesh_bytes([(10,0,3.25),(-12.5,0,-3.5),(0,-1,2),(0,1,2)],
   [([0,1,2],[(0,0),(31,31),(0,31)],(0,0,-1),(256,256,256),3),
    ([1,0,3],[(31,31),(0,0),(31,0)],(0,0,-1),(256,256,256),3)])
  g.upload(0x1770000,seam_v);g.upload(0x1770400,seam_f)
  reserved_v=bytearray(v);reserved_v[31]=0x80;g.upload(0x1788000,reserved_v)
  reserved_f=bytearray(f[:32]);reserved_f[23]=0x80;g.upload(0x178c000,reserved_f)
  if a.viewport_extrema:
   edge_v,edge_f=mesh_bytes([(-.0625,-.0625,.0625),(.0625,-.0625,.0625),(.0625,.0625,.0625),(-.0625,.0625,.0625)],
    [([0,2,1],[(-32768,-32768),(32767,32767),(32767,-32768)],(0,0,-1),(256,256,256),3),
     ([0,3,2],[(-32768,-32768),(-32768,32767),(32767,32767)],(0,0,-1),(256,256,256),3)])
   g.upload(0x1790000,edge_v);g.upload(0x1798000,edge_f)
  initial=bytes(pixels.memory)
  g.command(pack(22<<24,0x800000,0x900000,xy(160,100),xy(352,384)))
  g.command(pack(23<<24,xy(0,0),xy(160,100)))
  g.command(pack(28<<24,3,0x1084,65535,xy(0,0),xy(160,100)))
  g.command(pack(24<<24,0x1700000,xy(32,32),64,2|(2<<2)))
  g.command(Camera().words())
  for row in range(3):g.command(pack(31<<24,row,*g.matrix[row*4:row*4+4]))
  g.command(pack(33<<24,0,(-32767)&65535,64|(192<<16)))
  g.command(pack(25<<24,1|2|4|16,256,65535,256|(256<<9)|(256<<18)))
  g.command(pack(34<<24,vb,fb,len(points)<<16|len(faces),1))
  # Same mesh, changed transforms at run time, translucent and behind-camera cases.
  for tx,tz,alpha in [(2,1,128),(-2,0,180),(0,-4,200),(0,79,220),(0,2,256),(30,1,100),(-30,1,150),(0,-1,210),(1,6,256)]:
   g.command(pack(31<<24,0,65536,0,0,q16(tx)))
   g.command(pack(31<<24,2,0,0,65536,q16(tz)))
   g.command(pack(25<<24,1|2|16,alpha,65535,256|(256<<9)|(256<<18)))
   g.command(pack(34<<24,vb,fb,len(points)<<16|len(faces),1))
  # A matrix overflow must fail before a vertex reaches the cache or rasterizer.
  g.command(pack(31<<24,0,0x7fffffff,0x7fffffff,0,0))
  g.input+=pack(34<<24,vb,fb,len(points)<<16|len(faces),1)
  pixels.apply(g.material)  # An accepted DRAW restores material even on abort.
  g.command(pack(31<<24,0,65536,0,0,q16(1)))
  # Malformed hardware commands fail explicitly, then a valid draw recovers.
  for bad in [pack(31<<24,3),pack(34<<24,vb+1,fb,9<<16|3,1),pack(34<<24,vb,fb,257<<16|3,1),pack(32<<24),pack(34<<24,vb,fb,9<<16|3,1)]:g.input+=bad
  bad_count=6
  g.command(Camera().words())
  g.command(pack(34<<24,vb,fb,len(points)<<16|len(faces),1))
  # Extreme UV gradients on a one-pixel triangle take the counted approximation.
  for row in range(3):g.command(pack(31<<24,row,*[65536 if col==row else 0 for col in range(4)]))
  g.command(pack(34<<24,0x1750000,0x1758000,3<<16|1,1))
  assert g.slivers==2
  # A malformed second face must still restore the caller's material after the
  # first face changed its tint. The rejected face emits no raster work.
  g.command(pack(34<<24,vb,0x1760000,len(points)<<16|1,1))
  g.input[-5]=len(points)<<16|2;bad_count+=1
  g.command(pack(34<<24,0x1768000,0x176c000,256<<16|1,1))
  g.command(pack(34<<24,0x1770000,0x1770400,4<<16|2,0))
  # Reserved mesh fields are part of the ABI, not silently ignored data.
  g.input+=pack(34<<24,0x1788000,fb,len(points)<<16|1,1);pixels.apply(g.material);bad_count+=1
  g.input+=pack(34<<24,vb,0x178c000,len(points)<<16|1,1);pixels.apply(g.material);bad_count+=1;g.vertices+=len(points)
  if a.invalid_descriptors:
   # The pixel engine rejects these descriptors. Geometry must not turn an
   # invalid tint into a valid one by lighting it, nor accept its target size.
   valid_material=list(g.material)
   for word,value in [(4,257|(256<<9)|(256<<18)),(4,0x84020100),(3,65536),
                      (6,0x01000001),(7,1),(0,(25<<24)|1),(1,16),(2,257)]:
    invalid=list(valid_material);invalid[word]=value
    g.input+=invalid;pixels.commands+=invalid;pixels.rejected+=1
    g.input+=pack(34<<24,vb,fb,len(points)<<16|1,1);bad_count+=1
   g.command(valid_material)
   for invalid in [pack(22<<24,0x800001,0x900000,xy(160,100),xy(352,384)),
                   pack((22<<24)|1,0x800000,0x900000,xy(160,100),xy(352,384))]:
    g.input+=invalid;pixels.commands+=invalid;pixels.rejected+=1
    g.input+=Camera().words();bad_count+=1
    g.input+=pack(34<<24,vb,fb,len(points)<<16|1,1);bad_count+=1
   g.command(pack(22<<24,0x800000,0x900000,xy(160,100),xy(352,384)))
   g.command(Camera().words())
   g.command(pack(34<<24,vb,fb,len(points)<<16|len(faces),1))
  if a.viewport_extrema:
   # Empty scissor preserves the earlier pixel evidence while the geometry
   # oracle checks full 1024x512 differences, near=1/16 and extreme signed UV.
   g.command(pack(22<<24,0x800000,0x900000,xy(1024,512),xy(2048,2048)))
   g.command(pack(23<<24,0,0))
   g.command(Camera(near=4096,fx=q16(512),fy=q16(256),cx=512,cy=256,width=1024,height=512).words())
   g.command(pack(34<<24,0x1790000,0x1798000,4<<16|2,1))
   g.command(pack(22<<24,0x800000,0x900000,xy(160,100),xy(352,384)))
   g.command(pack(23<<24,0,xy(160,100)))
   g.command(Camera().words())
  if a.mixed_raster:
   # Switch from geometry to the older textured rasterizer and back, sharing
   # the native DDR stage. Its independent oracle uses the 800-pixel layout.
   for c in [pack(14<<24,0x10,1,256,0),pack(15<<24,15,xy(0,0),xy(32,32),10),
             pack(16<<24,-200*65536,65536,0),pack(17<<24,-200*65536,0,65536),
             pack(19<<24,xy(200,200),xy(223,200),xy(200,223))]:g.input+=c
   for x,y in triangle_pixels(200,200,223,200,200,223):
    pixels.put(0x800000+2*(y*800+x),pixels.get(0x1700000+2*((y-200)*800+x-200)))
   g.command(pack(34<<24,vb,fb,len(points)<<16|len(faces),1))
 # Dump full shader command oracle, so earlier overwritten pixels cannot hide faults.
 (out/'initial.hex').write_text(''.join(f'{v:02x}\n' for v in initial))
 (out/'expected.hex').write_text(''.join(f'{v:02x}\n' for v in pixels.memory))
 (out/'commands.hex').write_text(''.join(f'{v:08x}\n' for v in g.input))
 (out/'shader.hex').write_text(''.join(f'{v:08x}\n' for v in pixels.commands))
 shutil.copy2(ROOT/'tang/rtl/video/font8x16.hex',out/'font8x16.hex')
 tb=(ROOT/'TESTS/rtl/gpu_accel_tb.sv').read_text()
 if a.bus_stage:
  tb=tb.replace('    gpu_accel #(','''    wire ps,pw,pr;wire [1:0] pt;wire [31:0] pa,pd,presult;
    video_bus_stage stage(.clk(hc),.resetn(rst),.s_hsel(sel),.s_hwrite(wr),.s_htrans(trans),.s_haddr(address),.s_hwdata(data),.s_hready(hready),.s_hrdata(result),
      .m_hsel(ps),.m_hwrite(pw),.m_htrans(pt),.m_haddr(pa),.m_hwdata(pd),.m_hready(pr),.m_hrdata(presult));
    gpu_accel #(''')
  tb=tb.replace('.hsel(sel),.hwrite(wr),.haddr(address),.hwdata(data),.htrans(trans),\n        .hrdata(result),.hready(hready)',
                '.hsel(ps),.hwrite(pw),.haddr(pa),.hwdata(pd),.htrans(pt),\n        .hrdata(presult),.hready(pr)')
 at='    reg [31:0] value;'
 tb=tb.replace(at,'''    reg [31:0] shader_expected [0:65535];integer shader_index=0;
    initial $readmemh("shader.hex",shader_expected,0,SHADER_WORDS-1);
    always @(posedge mc)if(rst && dut.u_v1.shader_start)begin
        for(integer w=0;w<8;w++)begin
            if(dut.u_v1.shader_command[w*32+:32]!==shader_expected[shader_index])
                $fatal(1,"Geometry command %0d word %0d = %h expected %h state=%0d",shader_index/8,w,dut.u_v1.shader_command[w*32+:32],shader_expected[shader_index],dut.u_v1.state);
            shader_index++;
        end
    end
'''.replace('SHADER_WORDS',str(len(pixels.commands)))+at)
 if not a.world:
  tb=tb.replace(at,'''    integer shared_edge_checks=0;
    always @(posedge mc)if(rst && dut.u_v1.state[dut.u_v1.CL_STORE] && dut.u_v1.vb==32'h1770000 && dut.u_v1.plane==0 && dut.u_v1.iy==0)begin
        if(dut.u_v1.ix!=2 || dut.u_v1.iz!=16384)
            $fatal(1,"Shared edge depends on winding: x=%0d z=%0d",dut.u_v1.ix,dut.u_v1.iz);
        shared_edge_checks++;
    end
'''+at)
  tb=tb.replace("        read_reg('hc,value);", "        if(shared_edge_checks!=2)$fatal(1,\"Shared edge coverage %0d\",shared_edge_checks);\n        read_reg('hc,value);")
 if a.world:
  tb=tb.replace(at,'''    integer profile_start=0,profile_end=309,profile_pixels=0,profile_geometry=0;
    always @(posedge mc)if(rst)begin
        if(dut.u_v1.u_pixels.busy)profile_pixels++;
        else if(dut.u_v1.busy)profile_geometry++;
        if(dut.done_count==profile_end)begin
            $display("PROFILE frame=%0d memory_cycles=%0d pixel_cycles=%0d geometry_cycles=%0d",profile_end/309-1,cycle-profile_start,profile_pixels,profile_geometry);
            profile_start=cycle;profile_pixels=0;profile_geometry=0;profile_end+=309;
        end
    end
'''+at)
 tb=tb.replace('        read_reg(\'hc,value);',f'''        if(shader_index!={len(pixels.commands)})$fatal(1,"Missing geometry commands");
        read_reg('h4c,value);if(value!={bad_count})$fatal(1,"Geometry errors %0d",value);
        read_reg('h50,value);if(value!={g.vertices})$fatal(1,"Vertex count %0d",value);
        read_reg('h54,value);if(value!={g.triangles})$fatal(1,"Triangle count %0d",value);
        read_reg('h58,value);if(value!={g.culled})$fatal(1,"Cull count %0d",value);
        read_reg('h5c,value);if(value!={g.clipped})$fatal(1,"Clip count %0d",value);
        read_reg('h60,value);if(value!={g.slivers})$fatal(1,"Sliver count %0d",value);
        read_reg('hc,value);''')
 if a.reset_phases:
  # CPU/GPU reset does not reset the board's DDR arbiter. Let accepted reads
  # finish during reset, and check cancellation without clearing its queues.
  tb=tb.replace('reg hc=0, mc=0, rst=0;', 'reg hc=0, mc=0, rst=0, memory_resetn=0, checking=0;')
  tb=tb.replace('.clk(mc),.rst_n(rst)', '.clk(mc),.rst_n(memory_resetn)')
  tb=tb.replace('always @(posedge mc) if(rst) begin', 'always @(posedge mc) if(memory_resetn) begin')
  tb=tb.replace('ready=rst &&', 'ready=memory_resetn &&')
  tb=tb.replace('if(rst && dut.u_v1.', 'if(rst && checking && dut.u_v1.')
  phases=[7,8,21,27,37,42,46]
  prelude='''#200; rst=1; memory_resetn=1;
        for(integer trial=0;trial<7;trial++)begin
            automatic integer phase;
            case(trial)
'''+''.join(f'              {i}:phase={phase};\n' for i,phase in enumerate(phases))+'''
            endcase
            for(integer i=0;i<11*8;i++)write_reg('h10,commands[i]);
            wait(dut.u_v1.state[phase]);
            @(negedge hc);rst=0;
            repeat(32)@(negedge hc);
            rst=1;
            repeat(1000)@(negedge mc);
            if(dut.done_count!=0 || dut.u_blitter.busy || dut.u_v1.busy || bv || dut.queue_valid)
                $fatal(1,"Old work replayed after reset phase %0d",phase);
            // A fresh DRAW cannot reuse the pre-reset matrix/camera/material.
            for(integer i=10*8;i<11*8;i++)write_reg('h10,commands[i]);
            wait(dut.done_count==1);repeat(100)@(negedge mc);
            if(dut.u_v1.geom_errors!=1 || dut.u_v1.vertices!=0)
                $fatal(1,"Pre-reset descriptors survived phase %0d",phase);
            @(negedge hc);rst=0;repeat(32)@(negedge hc);rst=1;
            repeat(1000)@(negedge mc);
            $display("RESET PASS phase=%0d",phase);
        end
        $readmemh("initial.hex",memory);
        checking=1;
'''
  tb=tb.replace('#200; rst=1;',prelude)
 (out/'geometry_tb.sv').write_text(tb)
 src=['gpu_accel','gpu_geometry','gpu_geom_div','video_bus_stage','blitter','gpu_raster','gpu_v1','gpu_texture_cache','gpu_copy565','gpu_perspective','gpu_triangle','gpu_blit_dma','font_ram']
 sources=[out/'geometry_tb.sv']+[a.source_root/f'tang/rtl/video/{n}.v' for n in src]+[a.source_root/f'tang/rtl/board/{n}.v' for n in ('ddr_dcfifo','cdc_word','ddr_gpu_arb')]
 if a.neo_response:sources += [ROOT/'tang/boards/neo/neo_gpu_response.v']
 with (out/'build.log').open('w') as log:subprocess.run(['verilator','--binary','--timing','-Wno-fatal','--top-module','gpu_accel_tb',f'-GREAD_MIN={a.read_min}',f'-GNEO_RESPONSE={int(a.neo_response)}',f'-GMEM_HALF_PERIOD={a.mem_half_period}','--Mdir',str(out/'obj'),*[str(s) for s in sources]],stdout=log,stderr=log,check=True)
 with (out/'simulation.log').open('w') as log:r=subprocess.run([str(out/'obj/Vgpu_accel_tb'),f'+ncmd={len(g.input)//8}','+rgbinit=3',f'+v1_bad={bad_count+pixels.rejected}',f'+v1_pass={pixels.passed}'],cwd=out,stdout=log,stderr=log)
 print((out/'simulation.log').read_text());r.check_returncode()
 result=dict(status='PASS',neo_response=a.neo_response,mem_half_period=a.mem_half_period,world=a.world,bus_stage=a.bus_stage,mixed_raster=a.mixed_raster,invalid_descriptors=a.invalid_descriptors,reset_phases=7 if a.reset_phases else 0,invalid_commands=bad_count,shader_rejected=pixels.rejected,input_commands=len(g.input)//8,shader_commands=len(pixels.commands)//8,vertices=g.vertices,triangles=g.triangles,culled=g.culled,clipped=g.clipped,slivers=g.slivers,bytes_compared=len(pixels.memory),read_min=a.read_min)
 result['passed_pixels']=pixels.passed
 result['sha256']={str(s):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='sha256'})
if __name__=='__main__':main()

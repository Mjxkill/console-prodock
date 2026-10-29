"""Explicit, same-cycle reset copies for a frozen Neo GPU experiment.

No new synchronizer stage: all twelve drivers sample mrst[0] on the same
mem_clk edge, with the same asynchronous assertion as the original four.
The first four outputs retain their meaning. Children receive separate
drivers to avoid routing one geometry reset through every pixel sub-engine.
"""
import hashlib
import json
import re
from pathlib import Path
from .gpu_debug import replace_once
from .timing_closure import global_clock_routes


def split_resets(source):
    source = Path(source)
    edits = {
        'tang/rtl/video/gpu_accel.v': [
            ('reg [3:0] engine_resetn', 'reg [11:0] engine_resetn'),
            ('engine_resetn <= {4{mrst[0]}};', 'engine_resetn <= {12{mrst[0]}};'),
            ('gpu_geometry u_v1(.clk(mem_clk),',
             'gpu_geometry u_v1(.child_resetn(engine_resetn[9:4]),.clk(mem_clk),'),
            ('gpu_raster u_raster (',
             'gpu_raster u_raster (.child_resetn(engine_resetn[11:10]),'),
        ],
        'tang/rtl/video/gpu_geometry.v': [
            ('module gpu_geometry(\n', 'module gpu_geometry(\n input wire [5:0] child_resetn,\n'),
            ('gpu_v1 u_pixels(.clk(clk),.rst(rst),',
             'gpu_v1 u_pixels(.child_resetn(child_resetn[5:2]),.clk(clk),.rst(!child_resetn[0]),'),
            ('gpu_geom_div u_divx(.clk(clk),.rst(rst),',
             'gpu_geom_div u_divx(.clk(clk),.rst(!child_resetn[1]),'),
            ('gpu_geom_div u_divy(.clk(clk),.rst(rst),',
             'gpu_geom_div u_divy(.clk(clk),.rst(!child_resetn[1]),'),
        ],
        'tang/rtl/video/gpu_v1.v': [
            ('module gpu_v1(\n', 'module gpu_v1(\n    input wire [3:0] child_resetn,\n'),
            ('gpu_copy565 u_copy(.clk(clk),.rst(rst),',
             'gpu_copy565 u_copy(.clk(clk),.rst(!child_resetn[0]),'),
            ('gpu_texture_cache u_cache(.clk(clk),.rst(rst),',
             'gpu_texture_cache u_cache(.clk(clk),.rst(!child_resetn[1]),'),
            ('u_triangle(.clk(clk),.rst(rst),',
             'u_triangle(.clk(clk),.rst(!child_resetn[2]),'),
            ('gpu_perspective u_per0(.clk(clk),.rst(rst),',
             'gpu_perspective u_per0(.clk(clk),.rst(!child_resetn[3]),'),
            ('gpu_perspective u_per1(.clk(clk),.rst(rst),',
             'gpu_perspective u_per1(.clk(clk),.rst(!child_resetn[3]),'),
        ],
        'tang/rtl/video/gpu_raster.v': [
            ('    input wire clk, rst, start,',
             '    input wire [1:0] child_resetn,\n    input wire clk, rst, start,'),
            ('.clk(clk),.rst(rst),.start(triangle_start),',
             '.clk(clk),.rst(!child_resetn[0]),.start(triangle_start),'),
            ('gpu_perspective u_perspective0 (.clk(clk),.rst(rst),',
             'gpu_perspective u_perspective0 (.clk(clk),.rst(!child_resetn[1]),'),
            ('gpu_perspective u_perspective1 (.clk(clk),.rst(rst),',
             'gpu_perspective u_perspective1 (.clk(clk),.rst(!child_resetn[1]),'),
        ],
    }
    prepared, changed = {}, {}
    for rel, replacements in edits.items():
        original = (source/rel).read_text()
        text = original
        for old, new in replacements:
            text = replace_once(text, old, new)
        prepared[rel] = text
        changed[rel] = dict(before=hashlib.sha256(original.encode()).hexdigest(),
                            after=hashlib.sha256(text.encode()).hexdigest())
    for rel, text in prepared.items():
        (source/rel).write_text(text)
    (source/'tang/boards/neo/gpu_reset.json').write_text(json.dumps(dict(
        profile='neo-gpu-reset-copies-12', drivers=12,
        same_cycle=True, changed=changed), indent=2)+'\n')
    return changed


def constrain_local(source):
    """Use only after instrumentation, which exposes stable top-level names."""
    source = Path(source)
    manifest = json.loads((source/'tang/boards/neo/gpu_reset.json').read_text())
    if manifest['profile'] != 'neo-gpu-reset-copies-12':
        raise ValueError('Unknown GPU reset profile')
    gpu = (source/'tang/rtl/video/gpu_accel.v').read_text()
    if '8\'d0,engine_resetn,mrst' not in gpu:
        raise ValueError('Missing twelve-bit reset observation')
    cst = source/'tang/boards/neo/neo.cst'
    text = cst.read_text()
    if 'gpu_debug_state[' in text:
        raise ValueError('GPU reset constraints already present')
    # Subsequent payload experiment also retains N35r1's explicit control
    # reset routing; N35 itself remains an immutable twelve-copy experiment.
    first = 43 if (source/'tang/boards/neo/gpu_payload.json').exists() else 44
    nets = [f'gpu_debug_state[{i}]' for i in range(first, 56)]
    cst.write_text(text+'\n// Neo experiment: local distribution of twelve same-cycle reset copies.\n'+
                  ''.join(f'CLOCK_LOC "{net}" LOCAL_CLOCK;\n' for net in nets))
    return nets


def queue_reset_local(cst, netlist):
    """N35 counter-experiment: route mrst[1] locally, keeping its netlist."""
    modules = re.findall(r'^module gpu_accel\b.*?^endmodule', netlist, re.M|re.S)
    if len(modules) != 1:raise ValueError('Expected one gpu_accel')
    cells = re.findall(r'^\s*DFFCE mrst_1_s0\s*\((.*?)\);', modules[0], re.M|re.S)
    if len(cells) != 1:raise ValueError('Missing queue reset driver')
    ports = dict(re.findall(r'\.(\w+)\(([^()]*)\)', cells[0]))
    if ports != dict(Q='gpu_debug_state_43',D='gpu_debug_state_42',CLK='gpu_clk',CLEAR='n1205_6',CE='VCC'):
        raise ValueError('Unknown queue reset mapping')
    net='gpu_debug_state[43]'
    if net in cst:raise ValueError('Queue reset already constrained')
    return cst+'\n// N35 counter-experiment: same netlist, queue reset off global routing.\n'+f'CLOCK_LOC "{net}" LOCAL_CLOCK;\n', [net]


def control_local_constraints(cst, netlist, primary=False):
    """N38 counter-experiment: keep four observed non-clock controls off LW.

    Validate each mapped driver before using its synthesized hierarchical name.
    The geometry CE, pixel-buffer reset, command CE and scanout reset are not
    clocks. No DDR IP or USB constraint is changed.
    """
    specs=[
        ('gpu_geometry','u_accel/u_v1/','LUT2','n60343_s0',
         dict(F='n60343_3',I0='gpu_debug_state_46',I1='state[61]'),"4'h8"),
        ('gpu_v1','u_accel/u_v1/u_pixels/','LUT2','n34374_s1',
         dict(F='n34374_4',I0='state[13]',I1='gpu_debug_state_48'),"4'hB"),
        ('gpu_v1','u_accel/u_v1/u_pixels/','LUT2','n38025_s0',
         dict(F='n38025_3',I0='shader_start',I1='state[0]'),"4'h8"),
        ('gpu_scanout','u_gpu/','DFFCE','mrst_1_s0',
         dict(Q='mrst[1]',D='mrst[0]',CLK='gpu_clk',CLEAR='n3390_6',CE='VCC'),None)]
    nets=[]
    for module,prefix,kind,cell,wanted,init in specs:
        modules=re.findall(r'^module '+module+r'\b.*?^endmodule',netlist,re.M|re.S)
        if len(modules)!=1:raise ValueError('Unknown control module '+module)
        cells=re.findall(r'^\s*'+kind+' '+cell+r'\s*\((.*?)\);',modules[0],re.M|re.S)
        if len(cells)!=1 or dict(re.findall(r'\.(\w+)\(([^()]*)\)',cells[0]))!=wanted:
            raise ValueError('Unknown control driver '+cell)
        if init and not re.search(r'defparam '+cell+r'\.INIT\s*=\s*'+re.escape(init)+';',modules[0]):
            raise ValueError('Changed control function '+cell)
        net=prefix+wanted['F' if kind=='LUT2' else 'Q']
        if re.search(r'CLOCK_LOC\s+"'+re.escape(net)+'"',cst):raise ValueError('Control already constrained')
        nets.append(net)
    route='BUFG = CE|SR|LOGIC' if primary else 'LOCAL_CLOCK'
    return cst+'\n// N38 counter-experiment: same netlist, four non-clock GPU controls off LW.\n'+''.join(
        f'CLOCK_LOC "{net}" {route};\n' for net in nets),nets


def audit_control_routing(report, nets, primary=False):
    text=Path(report).read_text()
    try:table=global_clock_routes(text)
    except ValueError as exc:return dict(passed=False,errors=[str(exc)])
    kinds={net:{kind for name,kind,_ in table if name==net} for net in nets}
    routes={net:'+'.join(sorted(k)) for net,k in kinds.items() if k}
    errors=[net+' still uses LW' for net,k in kinds.items() if 'LW' in k]
    if primary:errors += [net+' is not on PRIMARY' for net in nets if kinds[net]!={'PRIMARY'}]
    return dict(passed=not errors,errors=errors,
                requested_primary=nets if primary else [],requested_local=[] if primary else nets,global_routes=routes,
                scope='Requested controls must be absent from LW; PRIMARY promotion is recorded explicitly')


def prefetch_payload(source):
    """Capture an idle transaction slot without loading REQUEST with its CE.

    PENDING still controls validity and holds every payload bit under DDR
    backpressure. Idle payload is private/unspecified. No transaction cycle,
    ownership or acknowledgement changes. Frozen Neo copy only.
    """
    source=Path(source)
    path=source/'tang/rtl/video/gpu_accel.v'
    original=path.read_text();text=original
    text=replace_once(text,
        '            v1_tx_addr<=0;v1_tx_data<=0;v1_tx_mask<=-1;v1_tx_write<=0;\n','')
    text=replace_once(text,'''                v1_pending<=1;v1_tx_addr<=v1_select ? v1_addr:raster_addr;
                v1_tx_data<=v1_select ? v1_data:raster_data;
                v1_tx_mask<=v1_select ? v1_mask:raster_mask;
                v1_tx_write<=v1_select ? v1_write:raster_write;
''','''                v1_pending<=1;
''')
    text=replace_once(text,'    assign v1_valid=v1_pending;','''    // Prefetch only while the transaction slot is empty. REQUEST drives
    // PENDING alone; held payload and accepted DDR cycles remain unchanged.
    always @(posedge mem_clk)begin
        if(!v1_pending)begin
            v1_tx_addr<=v1_select ? v1_addr:raster_addr;
            v1_tx_data<=v1_select ? v1_data:raster_data;
            v1_tx_mask<=v1_select ? v1_mask:raster_mask;
            v1_tx_write<=v1_select ? v1_write:raster_write;
        end
    end
    assign v1_valid=v1_pending;''')
    path.write_text(text)
    record=dict(profile='neo-gpu-idle-payload-capture',
                before=hashlib.sha256(original.encode()).hexdigest(),
                after=hashlib.sha256(text.encode()).hexdigest())
    (source/'tang/boards/neo/gpu_payload.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def register_shader_phase(source):
    """Keep the active shader interval locally, instead of decoding five states.

    shader_start is asserted exactly on entry to each shader wait state;
    shader_done ends that interval. The public request/response cycles and
    the pixel engine's reset remain unchanged. Frozen Neo copy only.
    """
    source=Path(source)
    path=source/'tang/rtl/video/gpu_geometry.v'
    original=path.read_text()
    text=replace_once(original, ' reg fetch_valid;reg [28:0] fetch_addr;', ''' reg fetch_valid;reg [28:0] fetch_addr;
 reg shader_read_phase;
 always @(posedge clk)
  if(rst)shader_read_phase<=0;
  else if(shader_start)shader_read_phase<=1;
  else if(shader_done)shader_read_phase<=0;
 // START already marks the first wait-state cycle, before the retained bit.
 wire shader_read_enable=shader_start || shader_read_phase;''')
    text=replace_once(text,
        'rd_valid&&(state[PASS]||state[MAT_WAIT]||state[PL_SENT]||state[TRI_WAIT]||state[RESTORED])',
        'rd_valid&&shader_read_enable')
    path.write_text(text)
    record=dict(profile='neo-gpu-shader-read-phase',
                before=hashlib.sha256(original.encode()).hexdigest(),
                after=hashlib.sha256(text.encode()).hexdigest())
    (source/'tang/boards/neo/gpu_shader_phase.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def local_geometry_payloads(source):
    """Remove two wide control cones without changing transaction cycles.

    The clip BRAM outputs/plane remain stable until the edge has been consumed.
    Sample their private operands every cycle, retaining CL_READ as a latency
    stage. Pixel buffers need no clearing: the reset byte mask protects unwritten
    lanes, and background/depth reads initialize lanes that need old contents.
    Reset/state control therefore drives the mask and validity, not 512 payload
    bits. These edits apply only to the frozen Neo source tree.
    """
    source=Path(source)
    geometry=source/'tang/rtl/video/gpu_geometry.v'
    pixels=source/'tang/rtl/video/gpu_v1.v'
    original_geometry=geometry.read_text()
    original_pixels=pixels.read_text()
    capture='''     edge_a<=poly_a;edge_b<=poly_b;
     clip_z0<=az;clip_z1<=bz;
     clip_ratio<=plane>=2 ? ratio[plane-2]:0;
     case(plane)
      2:begin clip_side0<=ax;clip_side1<=bx;end
      3:begin clip_side0<=-$signed({ax[31],ax});clip_side1<=-$signed({bx[31],bx});end
      4:begin clip_side0<=ay;clip_side1<=by;end
      default:begin clip_side0<=-$signed({ay[31],ay});clip_side1<=-$signed({by[31],by});end
     endcase
'''
    changed_geometry=replace_once(original_geometry,
        '    state[CL_READ]:begin\n'+capture,
        '    state[CL_READ]:begin\n')
    changed_geometry=replace_once(changed_geometry,
        ' wire signed [31:0] eax=edge_a[31:0]',
        ''' // Private prefetch registers. Polygon input addresses are held from
 // CL_DIST through CL_INTER; CL_READ still supplies the original latency.
 always @(posedge clk)begin
'''+capture+''' end
 wire signed [31:0] eax=edge_a[31:0]''')
    old='''        if(rst)begin color_buf<=0;z_buf<=0;pixel_mask<=-1;chunk_dirty<=0;end
        else if(state[CHUNK])begin color_buf<=0;z_buf<=0;pixel_mask<=-1;chunk_dirty<=0;end
        else begin
'''
    new='''        // The mask/validity owns reset; unwritten payload is private.
        if(rst || state[CHUNK])begin pixel_mask<=-1;chunk_dirty<=0;end
        else begin
            if((state[PIX_STORE] || state[PIX_OPAQUE]) && pixel_visible)begin
                pixel_mask[lane*2+:2]<=0;
                chunk_dirty<=1;
            end
        end
    end
    always @(posedge clk)begin
'''
    changed_pixels=replace_once(original_pixels,old,new)
    # Payload writes can occur while reset asserts; the discarded mask and
    # engine state prevent them from becoming a native DDR transaction.
    pair='''                pixel_mask[lane*2+:2]<=0;
                chunk_dirty<=1;
'''
    if changed_pixels.count(pair)!=3:raise ValueError('Unknown pixel-mask ownership')
    prefix,body=changed_pixels.split('    always @(posedge clk)begin\n            if(color_load)',1)
    body=body.replace(pair,'',2)
    body=replace_once(body,'''            else if(state[PIX_OPAQUE] && pixel_visible)z_buf[lane*16+:16]<=depth;
        end
    end
''','''            else if(state[PIX_OPAQUE] && pixel_visible)z_buf[lane*16+:16]<=depth;
    end
''')
    changed_pixels=prefix+'    always @(posedge clk)begin\n            if(color_load)'+body
    changed={str(path.relative_to(source)):dict(
        before=hashlib.sha256(old.encode()).hexdigest(),
        after=hashlib.sha256(new.encode()).hexdigest()) for path,old,new in
        ((geometry,original_geometry,changed_geometry),(pixels,original_pixels,changed_pixels))}
    geometry.write_text(changed_geometry)
    pixels.write_text(changed_pixels)
    (source/'tang/boards/neo/gpu_local_payloads.json').write_text(json.dumps(dict(
        profile='neo-geometry-local-payloads',changed=changed),indent=2)+'\n')
    return changed


def stream_native_payload(source):
    """Keep native payload sampling local; the requesting engine holds it.

    Both producers hold their native request until the registered acceptance
    pulse. Sampling their payload every cycle thus keeps exactly the same
    pending transaction, without a 318-load enable on v1_pending. Validity and
    the registered acknowledgement guard are unchanged. Neo frozen copy only.
    """
    source=Path(source);path=source/'tang/rtl/video/gpu_accel.v'
    original=path.read_text()
    old='''    // Prefetch only while the transaction slot is empty. REQUEST drives
    // PENDING alone; held payload and accepted DDR cycles remain unchanged.
    always @(posedge mem_clk)begin
        if(!v1_pending)begin
            v1_tx_addr<=v1_select ? v1_addr:raster_addr;
            v1_tx_data<=v1_select ? v1_data:raster_data;
            v1_tx_mask<=v1_select ? v1_mask:raster_mask;
            v1_tx_write<=v1_select ? v1_write:raster_write;
        end
    end
'''
    new='''    // Both producers hold this payload through the registered acceptance
    // pulse. Private data can be sampled continuously; PENDING owns validity.
    always @(posedge mem_clk)begin
        v1_tx_addr<=v1_select ? v1_addr:raster_addr;
        v1_tx_data<=v1_select ? v1_data:raster_data;
        v1_tx_mask<=v1_select ? v1_mask:raster_mask;
        v1_tx_write<=v1_select ? v1_write:raster_write;
    end
'''
    changed=replace_once(original,old,new)
    path.write_text(changed)
    record=dict(profile='neo-native-payload-continuous-sampling',
                before=hashlib.sha256(original.encode()).hexdigest(),
                after=hashlib.sha256(changed.encode()).hexdigest())
    (source/'tang/boards/neo/gpu_stream_payload.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def register_transform_check(source):
    """Capture transform overflow with its sum, preserving every FSM cycle.

    Two signed 49-bit terms fit exactly in a signed 50-bit sum. The following
    V_STORE cycle consumes the registered range flag, rather than distributing
    a 64-bit comparison into the coordinate/coefficient enables.
    """
    source=Path(source);path=source/'tang/rtl/video/gpu_geometry.v'
    original=path.read_text()
    text=replace_once(original,' reg signed [48:0] transform_pair0,transform_pair1;',
        ''' reg signed [48:0] transform_pair0,transform_pair1;
 wire signed [49:0] transform_sum=$signed(transform_pair0)+$signed(transform_pair1);
 reg transform_overflow;''')
    text=replace_once(text,
        "    state[V_SUM]:begin sum64<=transform_pair0+transform_pair1;state<=81'b1<<(V_STORE);end",
        "    state[V_SUM]:begin sum64<=transform_sum;transform_overflow<=(transform_sum[49:32]!={18{transform_sum[31]}});state<=81'b1<<(V_STORE);end")
    text=replace_once(text,
        "     if(sum64>2147483647||sum64< -64'sd2147483648)state<=81'b1<<(FAIL);",
        "     if(transform_overflow)state<=81'b1<<(FAIL);")
    path.write_text(text)
    record=dict(profile='neo-transform-overflow-registered-with-sum',
                before=hashlib.sha256(original.encode()).hexdigest(),
                after=hashlib.sha256(text.encode()).hexdigest())
    (source/'tang/boards/neo/gpu_transform_check.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def prefetch_bounds_ratio(source):
    """Prefetch the next clipping coefficients before their DSP multiply.

    V_STORE enters the X multiply; V_BOUNDS_X enters the Y multiply. Sample
    X by default and Y during V_BOUNDS_X, keeping every FSM cycle unchanged.
    The explicit fabric registers cut the bounds_y -> mux -> remote DSP path.
    """
    source=Path(source);path=source/'tang/rtl/video/gpu_geometry.v'
    original=path.read_text()
    old=''' wire signed [31:0] bounds_ratio0=bounds_y ? ratio[2]:ratio[0];
 wire signed [31:0] bounds_ratio1=bounds_y ? ratio[3]:ratio[1];'''
    new=''' reg signed [31:0] bounds_ratio0 /* synthesis syn_preserve=1 */;
 reg signed [31:0] bounds_ratio1 /* synthesis syn_preserve=1 */;
 always @(posedge clk)begin
  bounds_ratio0<=state[V_BOUNDS_X] ? ratio[2]:ratio[0];
  bounds_ratio1<=state[V_BOUNDS_X] ? ratio[3]:ratio[1];
 end'''
    text=replace_once(original,old,new)
    path.write_text(text)
    record=dict(profile='neo-bounds-coefficients-prefetched',same_cycle=True,
                before=hashlib.sha256(original.encode()).hexdigest(),
                after=hashlib.sha256(text.encode()).hexdigest())
    (source/'tang/boards/neo/gpu_bounds_prefetch.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def audit_bounds_prefetch(netlist):
    text=Path(netlist).read_text()
    modules=re.findall(r'^module gpu_geometry\b.*?^endmodule',text,re.M|re.S)
    if len(modules)!=1:return dict(passed=False,errors=['Missing geometry module'])
    cells=re.findall(r'\b(DFF\w+)\s+(bounds_ratio[01]_\d+_s\d+)\s*\((.*?)\);',modules[0],re.S)
    errors=[];names=set()
    for kind,name,body in cells:
        ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',body))
        names.add(name)
        if (kind!='DFFCE' or ports.get('CLK')!='gpu_clk' or
                ports.get('CE')!='VCC' or ports.get('CLEAR')!='GND'):
            errors.append('Changed coefficient prefetch FF '+name)
    if len(cells)!=64 or names!={f'bounds_ratio{v}_{i}_s0' for v in (0,1) for i in range(32)}:
        errors.append('Expected 64 distinct fabric coefficient FFs')
    return dict(passed=not errors,errors=errors,coefficient_registers=len(cells),
                netlist_sha256=hashlib.sha256(Path(netlist).read_bytes()).hexdigest())


def prefetch_shader_inputs(source):
    """Cut late texture-coordinate enables and round alpha after its product.

    Texture coordinates are consumed only in PIX_OFFSET, one cycle after
    PIX_ADDR. Unconditional private sampling keeps that value without the
    visibility/clipping tree on a remote DSP clock enable. Alpha rounding is
    exactly (product + 128)[16:8], performed in the existing PIX_MOD stage.
    No engine cycles or externally visible transactions are added.
    """
    source=Path(source);path=source/'tang/rtl/video/gpu_v1.v'
    original=path.read_text();text=original
    for old,new in (
        ('reg [8:0] tex_u,tex_v;', 'reg [8:0] tex_u,tex_v /* synthesis syn_preserve=1 */;'),
        ('tex_u<=0;tex_v<=0;', ''),
        ('tex_u<=addressed_u[8:0];tex_v<=addressed_v[8:0];state<=58\'b1<<PIX_OFFSET;',
         "state<=58'b1<<PIX_OFFSET;"),
        ('    reg [15:0] pixel,background,depth;', '''    // Private prefetch, consumed at PIX_OFFSET only.
    always @(posedge clk)begin
        tex_u<=addressed_u[8:0];tex_v<=addressed_v[8:0];
    end
    reg [15:0] pixel,background,depth;'''),
        ('    reg [17:0] alpha_product;', '''    reg [17:0] alpha_product;
    wire [8:0] rounded_alpha=alpha_product[16:8]+{8'b0,alpha_product[7]};'''),
        ("alpha_product<=alpha*texture_alpha+18'd128;", 'alpha_product<=alpha*texture_alpha;'),
        ('effective_alpha<=alpha_product[16:8];', 'effective_alpha<=rounded_alpha;'),
        ('alpha_product[16:8]==0 ? PIX_NEXT', 'rounded_alpha==0 ? PIX_NEXT'),
    ):text=replace_once(text,old,new)
    path.write_text(text)
    record=dict(profile='neo-shader-private-coordinates-alpha-rounding',same_cycle=True,
                before=hashlib.sha256(original.encode()).hexdigest(),
                after=hashlib.sha256(text.encode()).hexdigest())
    (source/'tang/boards/neo/gpu_shader_inputs.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def audit_shader_inputs(netlist):
    raw=Path(netlist).read_bytes()
    found=re.findall(r'^module gpu_v1\b.*?^endmodule',raw.decode(),re.M|re.S)
    if len(found)!=1:return dict(passed=False,errors=['Missing pixel shader module'])
    body=found[0];errors=[]
    cells={name:(kind,dict(re.findall(r'\.(\w+)\(([^()]*)\)',ports)))
           for kind,name,ports in re.findall(r'\b(DFF\w+)\s+(tex_[uv]_\d+_s\d+)\s*\((.*?)\);',body,re.S)}
    for axis in ('u','v'):
        for bit in range(9):
            wanted=dict(Q=f'tex_{axis}[{bit}]',D=f'addressed_{axis}[{bit}]',CLK='gpu_clk',CE='VCC',CLEAR='GND')
            if cells.get(f'tex_{axis}_{bit}_s0')!=('DFFCE',wanted):
                errors.append('Changed private texture-coordinate FF '+axis+str(bit))
    if len(cells)!=18:errors.append('Expected eighteen coordinate FFs')
    products=[(kind,name,ports) for kind,name,ports in
              re.findall(r'^\s*(MULT\w+)\s+(\w+)\s*\((.*?)\);',body,re.M|re.S)
              if 'alpha_product[16:7]' in ports]
    if len(products)!=1:errors.append('Missing unique registered alpha multiplier')
    else:
        kind,name,ports=products[0];ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',ports))
        params=dict(re.findall(r'defparam '+re.escape(name)+r'\.(\w+)=(.*?);',body))
        required={'MULT_RESET_MODE':'"SYNC"','OREG_CLK':'"CLK0"','OREG_CE':'"CE0"',
                  'OREG_RESET':'"RESET0"','AREG_CLK':'"BYPASS"','BREG_CLK':'"BYPASS"','PREG_CLK':'"BYPASS"'}
        if (kind!='MULT12X12' or ports.get('CLK')!='{GND,gpu_clk}' or
                ports.get('CE')!='{VCC,state[21]}' or
                any(params.get(k)!=v for k,v in required.items())):
            errors.append('Alpha product is not one output-register cycle at PIX_UNPACK')
    return dict(passed=not errors,errors=errors,coordinate_registers=len(cells),
                registered_alpha_multiplier=products[0][1] if len(products)==1 else None,
                netlist_sha256=hashlib.sha256(raw).hexdigest())


def audit_reset_tree(netlist, resource_report, control_local=False):
    """Check twelve distinct mapped FFs and actual absence from global trees."""
    netlist, resource_report = Path(netlist), Path(resource_report)
    text = netlist.read_text()
    modules = re.findall(r'^module gpu_accel\b.*?^endmodule', text, re.M|re.S)
    errors, drivers = [], []
    if len(modules) != 1:
        errors.append('Expected one gpu_accel module')
    else:
        for i in range(12):
            cells = re.findall(r'^\s*DFFCE engine_resetn_'+str(i)+r'_s0\s*\((.*?)\);',
                               modules[0], re.M|re.S)
            if len(cells) != 1:
                errors.append(f'Missing/distorted reset driver {i}')
                continue
            ports = dict(re.findall(r'\.(\w+)\(([^()]*)\)', cells[0]))
            drivers.append(dict(index=i, ports=ports))
            if any(ports.get(k) != v for k, v in dict(
                    Q=f'gpu_debug_state_{44+i}', D='gpu_debug_state_42',
                    CLK='gpu_clk', CE='VCC').items()):
                errors.append(f'Unexpected driver {i} ports')
        if len({d['ports'].get('CLEAR') for d in drivers}) != 1:
            errors.append('Reset copies do not share one asynchronous clear')
        if control_local:
            cells=re.findall(r'^\s*DFFCE mrst_1_s0\s*\((.*?)\);',modules[0],re.M|re.S)
            ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',cells[0])) if len(cells)==1 else {}
            expected=dict(Q='gpu_debug_state_43',D='gpu_debug_state_42',CLK='gpu_clk',CE='VCC',
                          CLEAR=drivers[0]['ports'].get('CLEAR') if drivers else None)
            if ports!=expected:errors.append('Control reset driver differs from engine copies')
    rpt = resource_report.read_text()
    try:routes=global_clock_routes(rpt)
    except ValueError as exc:errors.append(str(exc))
    else:
        global_nets={net for net,_,_ in routes}
        for i in range(43 if control_local else 44, 56):
            if f'gpu_debug_state[{i}]' in global_nets:
                errors.append(f'Reset {i-44} still uses a global routing resource')
    return dict(passed=not errors, drivers=drivers, errors=errors,
                netlist_sha256=hashlib.sha256(netlist.read_bytes()).hexdigest(),
                resource_sha256=hashlib.sha256(resource_report.read_bytes()).hexdigest())


def audit_local_payloads(netlist, resource_report):
    """Verify that N39 really removed wide reset/CE loads after synthesis."""
    text=Path(netlist).read_text()
    errors=[];counts={};mask_controls=set()
    specs={'gpu_geometry':{'edge_a':160,'edge_b':160,'clip_side0':33,'clip_side1':33},
           'gpu_v1':{'color_buf':256,'z_buf':256,'pixel_mask':16,'chunk_dirty':1}}
    for module,registers in specs.items():
        modules=re.findall(r'^module '+module+r'\b.*?^endmodule',text,re.M|re.S)
        if len(modules)!=1:
            errors.append('Missing payload module '+module);continue
        for name,width in registers.items():
            cells=re.findall(r'^\s*(DFF\w+) '+name+r'[^\s(]*\s*\((.*?)\);',modules[0],re.M|re.S)
            counts[module+'/'+name]=len(cells)
            if len(cells)!=width:errors.append('Unexpected mapped width '+module+'/'+name)
            for kind,body in cells:
                ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',body))
                if ports.get('CLK')!='gpu_clk':errors.append('Unexpected payload clock '+name)
                if module=='gpu_geometry':
                    if kind!='DFFCE' or ports.get('CLEAR')!='GND' or ports.get('CE')!='VCC':
                        errors.append('Prefetched operand still gated/reset '+name)
                elif name in ('color_buf','z_buf'):
                    if kind!='DFFRE' or ports.get('RESET')!='GND':
                        errors.append('Pixel payload still reset '+name)
                else:
                    signal=ports.get('SET' if name=='pixel_mask' else 'RESET')
                    if not signal or signal in ('GND','VCC'):errors.append('Missing mask/validity reset '+name)
                    mask_controls.add(signal)
    if len(mask_controls)!=1:errors.append('Mask and dirty flag reset disagree')
    nets=['u_accel/u_v1/u_pixels/'+n for n in mask_controls if n]
    routing=audit_control_routing(resource_report,nets)
    errors+=routing['errors']
    return dict(passed=not errors,errors=sorted(set(errors)),register_counts=counts,
                mask_reset_routing=routing,
                netlist_sha256=hashlib.sha256(Path(netlist).read_bytes()).hexdigest())


def audit_stream_payload(netlist, resource_report):
    """Require continuous sampling of the native slot's mapped registers."""
    text=Path(netlist).read_text();errors=[];counts={}
    modules=re.findall(r'^module gpu_accel\b.*?^endmodule',text,re.M|re.S)
    if len(modules)!=1:return dict(passed=False,errors=['Missing gpu_accel'])
    for name,width in [('v1_tx_addr',28),('v1_tx_data',256),('v1_tx_mask',32),('v1_tx_write',1)]:
        cells=re.findall(r'^\s*(DFF\w+) '+name+r'[^\s(]*\s*\((.*?)\);',modules[0],re.M|re.S)
        counts[name]=len(cells)
        if len(cells)!=width:errors.append('Unexpected native payload width '+name)
        for kind,body in cells:
            ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',body))
            if ports.get('CLK')!='gpu_clk' or ports.get('CE')!='VCC':
                errors.append('Native payload still gated '+name)
            # Seven address bits use the synchronous RESET pin as part of a
            # data mux. They still sample every cycle; no shared reset/enable.
            if name!='v1_tx_addr' and (kind!='DFFCE' or ports.get('CLEAR')!='GND'):
                errors.append('Native payload has a reset load '+name)
    routing=audit_control_routing(resource_report,['v1_pending','u_accel/v1_pending'])
    errors+=routing['errors']
    return dict(passed=not errors,errors=sorted(set(errors)),register_counts=counts,
                pending_routing=routing,
                netlist_sha256=hashlib.sha256(Path(netlist).read_bytes()).hexdigest())


def audit_transform_check(netlist):
    text=Path(netlist).read_text();errors=[]
    modules=re.findall(r'^module gpu_geometry\b.*?^endmodule',text,re.M|re.S)
    if len(modules)!=1:return dict(passed=False,errors=['Missing gpu_geometry'])
    cells=re.findall(r'^\s*(DFF\w+)\s+(transform_overflow\S*)\s*\((.*?)\);',modules[0],re.M|re.S)
    if len(cells)!=1:return dict(passed=False,errors=['Missing/ambiguous registered transform overflow'])
    kind,name,body=cells[0];ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',body))
    if kind!='DFFRE' or ports.get('CLK')!='gpu_clk' or ports.get('RESET')!='GND':
        errors.append('Unexpected transform overflow register mapping')
    return dict(passed=not errors,errors=errors,primitive=kind,ports=ports,
                netlist_sha256=hashlib.sha256(Path(netlist).read_bytes()).hexdigest())

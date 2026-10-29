#!/usr/bin/env python3
"""Prepare an observation-only N55 copy; no compiler or hardware access."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
REL = 'tang/rtl/video/'
BOARD = 'tang/boards/neo/'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def transforms(texts):
    edits = {
        REL+'gpu_v1.v': [
            ('    output wire target_config_valid,material_config_valid,',
             '    output wire [31:0] observe_packet_word0,\n    output wire target_config_valid,material_config_valid,'),
            ('    wire [31:0] w0=packet[31:0]',
             '    assign observe_packet_word0=packet[31:0];\n    wire [31:0] w0=packet[31:0]')],
        REL+'gpu_geometry.v': [
            (' output reg done,output wire busy,',
             ' output reg done,output wire busy,\n output wire [63:0] observe_packet_words,'),
            (' reg shader_start;reg [255:0] shader_command;',
             ' wire [31:0] observe_pixel_word0;\n assign observe_packet_words={observe_pixel_word0,captured_command[31:0]};\n reg shader_start;reg [255:0] shader_command;'),
            ('  .target_config_valid(shader_target_valid)',
             '  .observe_packet_word0(observe_pixel_word0),.target_config_valid(shader_target_valid)')],
        REL+'gpu_accel.v': [
            ('    output wire debug_accept\n',
             '    output wire debug_accept,\n    output wire [63:0] observe_packet_words\n'),
            ('        .busy(),.done(v1_done),',
             '        .observe_packet_words(observe_packet_words),.busy(),.done(v1_done),')],
        BOARD+'console_neo.v': [
            ('    wire gpu_debug_accept;',
             '    wire gpu_debug_accept;\n    wire [63:0] gpu_observe_packet_words;'),
            ('        .host_accept(gpu_debug_accept),.live(gpu_debug_state));',
             '        .host_accept(gpu_debug_accept),.live(gpu_debug_state),.observe_packet_words(gpu_observe_packet_words));'),
            ('.debug_state(gpu_debug_state),.debug_accept(gpu_debug_accept)',
             '.debug_state(gpu_debug_state),.debug_accept(gpu_debug_accept),.observe_packet_words(gpu_observe_packet_words)')],
        BOARD+'neo_gpu_debug.v': [
            ('    input wire [255:0] live\n',
             '    input wire [255:0] live,\n    input wire [63:0] observe_packet_words\n'),
            ('    reg [31:0] sequence_id=0;',
             '''    // Ungated observation path, independent of the snapshot handshake.
    // These per-bit synchronizers are NOT an atomic multi-bit capture. Read
    // only with the GPU idle, require repeated equal samples, and interpret
    // them as diagnostic evidence only. They never control the GPU or ACK.
    reg [63:0] observe_words_s1=0,observe_words_s2=0;
    reg [31:0] observe_meta_s1=0,observe_meta_s2=0;
    wire [31:0] observe_meta={8'd0,live[255:248],4'd0,valid,busy,
        ready_s,mem_up,ack_s,ack,req_s,request};
    always @(posedge hclk)begin
        if(!resetn)begin
            observe_words_s1<=0;observe_words_s2<=0;
            observe_meta_s1<=0;observe_meta_s2<=0;
        end else begin
            observe_words_s1<=observe_packet_words;observe_words_s2<=observe_words_s1;
            observe_meta_s1<=observe_meta;observe_meta_s2<=observe_meta_s1;
        end
    end
    reg [31:0] sequence_id=0;'''),
            ('reg [63:0] read_select', 'reg [67:0] read_select'),
            ('sel<64;', 'sel<68;'),
            ('(sel%16)*4', '(sel%17)*4'),
            ('register_value [0:15]', 'register_value [0:16]'),
            ('    assign register_value[6]=0;\n    assign register_value[7]=0;',
             '''    assign register_value[6]=observe_words_s2[31:0]; // geometry captured header
    assign register_value[7]=observe_words_s2[63:32]; // pixel captured header
    assign register_value[16]=observe_meta_s2; // raw handshake/opcode, not a snapshot'''),
            ('k<16;', 'k<17;'),
            ('read_select[byte_index*16+k]', 'read_select[byte_index*17+k]')]
    }
    result = dict(texts)
    # Validate every anchor before producing a changed source tree.
    for name, changes in edits.items():
        for before, after in changes:
            if result[name].count(before) != 1:
                raise ValueError('Unexpected observation anchor in '+name+': '+before)
            result[name] = result[name].replace(before, after)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-build', type=Path, default=ROOT/'tang/impl/console_neo_n55r2')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    parent = a.from_build.resolve(strict=True)
    manifest = json.loads((parent/'sources.json').read_text())
    if any(sha(parent/'source'/rel) != wanted for rel, wanted in manifest.items()):
        raise ValueError('Changed frozen reference')
    texts = {name:(parent/'source'/name).read_text() for name in [
        REL+'gpu_v1.v', REL+'gpu_geometry.v', REL+'gpu_accel.v',
        BOARD+'console_neo.v', BOARD+'neo_gpu_debug.v']}
    changed = transforms(texts)
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copytree(parent/'source', out/'source')
    diff = ''
    for name in texts:
        (out/'source'/name).write_text(changed[name])
        diff += ''.join(difflib.unified_diff(texts[name].splitlines(True),changed[name].splitlines(True),
            fromfile='N55r2/'+name,tofile='observer/'+name))
    (out/'observation.diff').write_text(diff)
    files = {str(f.relative_to(out/'source')):sha(f) for f in (out/'source').rglob('*') if f.is_file()}
    if sorted(k for k in files if files[k]!=manifest.get(k)) != sorted(texts):
        raise ValueError('Unexpected changed files')
    record = dict(parent=str(parent), source_manifest_sha256=sha(parent/'sources.json'),
        source_tree_only=True, compiler_started=False, hardware_accessed=False,
        scope='Observation outputs only. GPU sequential/combinational logic unchanged. DDR, clocks and SDC unchanged.',
        changes={name:dict(before=manifest[name],after=files[name]) for name in texts},
        registers={'0xe9005018':'GPU geometry captured_command[31:0]',
                   '0xe900501c':'GPU pixel packet[31:0]',
                   '0xe9005040':{'request':0,'req_s':[2,1],'ack':3,'ack_s':[5,4],
                    'mem_up':[7,6],'ready_s':[9,8],'busy':10,'valid':11,
                    'ext_command_opcode':[23,16]}},
        warning='Raw observation only. Two hclk synchronizers per bit do not make an atomic capture. GPU must be idle and repeated samples identical.')
    (out/'sources.json').write_text(json.dumps(files,indent=2)+'\n')
    (out/'observation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()

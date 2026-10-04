#!/usr/bin/env python3
"""Asset container interoperability and API overflow/invalid-input checks under UBSan."""
import ctypes,importlib.util,json,struct,subprocess,tempfile
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('assets',ROOT/'tools/gpu_assets.py');assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
C=r'''
#include <assert.h>
#include <limits.h>
#include "gpu_v1.h"
static unsigned calls;
static void emit(const gpu_command *c){assert((c->words[0]>>24)>=22);++calls;}
int main(void){
    gpu_v1_context c;gpu_v1_init(&c,emit);
    gpu_target t={0x800000,0x900000,400,240,832,832};assert(gpu_v1_target(&c,&t));
    unsigned before=calls;gpu_target bad=t;bad.depth=bad.color;assert(!gpu_v1_target(&c,&bad));
    bad=t;bad.width=1025;assert(!gpu_v1_target(&c,&bad));assert(calls==before);
    assert(!gpu_v1_scissor(&c,0,0,UINT_MAX,1));assert(!gpu_v1_clear(&c,1,0,0,INT_MAX,0,1,1));
    assert(!gpu_v1_copy(&c,&t,0,0,0,0,65536,1));assert(!gpu_v1_text(&c,0x1700000,INT_MAX,0,65535,256,16,"X"));
    assert(gpu_v1_viewport(&c,4,12,392,218));int x,y;assert(gpu_v1_project(&c,-65536,65536,&x,&y) && x==4 && y==12);
    assert(gpu_v1_project(&c,65536,-65536,&x,&y) && x==396 && y==230);assert(!gpu_v1_project(&c,INT_MIN,0,&x,&y));
    gpu_material m={17,256,65535,256,256,256,0,0,0};assert(gpu_v1_material(&c,&m));
    gpu_vertex v[3]={{-32768,-32768,-32768,32767,65535,0xffffff,256,256,256},
        {32767,-32768,32767,-32768,0,0xffffff,0,0,0},{-32768,32767,-32768,32767,65535,0,256,256,256}};
    (void)gpu_v1_triangle(&c,v);
    v[1].y=32766;v[2].x=32766;v[2].y=32765;before=calls;
    assert(!gpu_v1_triangle(&c,v));assert(calls==before); // area=-1, enormous gradients
    v[1].q=INT_MAX;before=calls;assert(!gpu_v1_triangle(&c,v));assert(calls==before);
    return 0;
}
'''
class Level(ctypes.Structure):
    _fields_=[('base',ctypes.c_uint32),('width',ctypes.c_uint16),('height',ctypes.c_uint16),('stride',ctypes.c_uint16),('format',ctypes.c_uint8),('u_mode',ctypes.c_uint8),('v_mode',ctypes.c_uint8),('lod',ctypes.c_uint8)]
def main():
    with tempfile.TemporaryDirectory(prefix='console_v1_api_') as temp:
        d=Path(temp);(d/'api.c').write_text(C)
        subprocess.run(['cc','-O1','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT/'fw_console'),str(d/'api.c'),str(ROOT/'fw_console/gpu_v1.c'),'-o',str(d/'api')],check=True)
        subprocess.run([str(d/'api')],check=True)
        subprocess.run(['cc','-shared','-fPIC','-O2','-I'+str(ROOT/'fw_console'),str(ROOT/'fw_console/gpu_v1.c'),'-o',str(d/'api.so')],check=True)
        lib=ctypes.CDLL(str(d/'api.so'));fn=lib.gpu_v1_asset_level
        fn.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint32,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(Level)];fn.restype=ctypes.c_int
        checks=0
        for w,h in ((1,1),(13,7),(256,256),(512,512)):
            for fmt in ('rgb565','argb4444'):
                im=Image.new('RGBA',(w,h),(201,77,39,129));data,meta=assets.pack(im,fmt);buf=ctypes.create_string_buffer(data)
                for lod,l in enumerate(meta['levels']):
                    result=Level();assert fn(buf,len(data),0x1700000,lod,2,2,ctypes.byref(result))
                    assert (result.base,result.width,result.height,result.stride,result.lod)==(0x1700000+l['offset'],l['width'],l['height'],l['stride'],lod);checks+=1
                assert not fn(buf,len(data)-1,0x1700000,0,2,2,ctypes.byref(Level()))
                for word,value in ((0,0),(1,2),(2,2),(3,11),(4,513),(6,0),(7,1),(8,len(data)),(10,1),(11,1)):
                    bad=bytearray(data);struct.pack_into('<I',bad,word*4,value);bb=ctypes.create_string_buffer(bytes(bad))
                    assert not fn(bb,len(bad),0x1700000,0,2,2,ctypes.byref(Level())),(word,value);checks+=1
        # Transparent red must not tint the opaque blue mip, including odd edges.
        im=Image.new('RGBA',(2,1));im.putdata([(255,0,0,0),(0,0,255,255)])
        assert assets.downsample(im).getpixel((0,0))==(0,0,255,128)
        print(json.dumps(dict(status='pass',asset_checks=checks,api_ubsan=True,premultiplied_mip=True)))
if __name__=='__main__':main()

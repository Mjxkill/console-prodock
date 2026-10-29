#!/usr/bin/env python3
"""Actual ILM unpacker: real kernel round-trip, truncations and overflow guards."""
import importlib.util
import os
from pathlib import Path
import random
import subprocess
import tempfile
HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pd_package',HERE/'package.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
code=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "unpack.h"
static unsigned char *readfile(const char *name, unsigned *n) {
 FILE *f=fopen(name,"rb");assert(f);fseek(f,0,SEEK_END);*n=ftell(f);rewind(f);
 unsigned char *b=malloc(*n+1);assert(fread(b,1,*n,f)==*n);fclose(f);return b;
}
int main(int argc,char **argv) {
 assert(argc==3);unsigned ns,nd;unsigned char *s=readfile(argv[1],&ns),*d=readfile(argv[2],&nd);
 unsigned char *out=malloc(nd+32);memset(out,0xa5,nd+32);
 assert(prodock_unpack(s,ns,out+16,nd));assert(!memcmp(out+16,d,nd));
 for(unsigned i=0;i<16;++i)assert(out[i]==0xa5 && out[nd+16+i]==0xa5);
 for(unsigned n=0;n<ns;n+=ns/1000+1)assert(!prodock_unpack(s,n,out+16,nd));
 unsigned char zero[]={0,0,0,0},huge[]={255,255,255,127},literal[]={255,255,255,255};
 assert(!prodock_unpack(zero,4,out,nd));assert(!prodock_unpack(huge,4,out,nd));
 assert(!prodock_unpack(literal,4,out,nd));assert(!prodock_unpack(s,ns,out,nd-1));
 assert(!prodock_unpack(s,ns,out,nd+1));
 free(out);free(d);free(s);puts("PASS packed boot: exact decode, truncated literals/headers, zero runs, overflow, canaries");
}
'''
with tempfile.TemporaryDirectory(prefix='prodock-unpack-') as tmp:
    p=Path(tmp);(p/'test.c').write_text(code)
    subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-I',str(HERE/'boot'),str(p/'test.c'),'-o',str(p/'test')],check=True)
    r=random.Random(7319)
    samples=[bytes(8192),r.randbytes(9137),r.randbytes(4096)+bytes(65536)+r.randbytes(912),
             (module.BUILD/'opensbi/platform/generic/firmware/fw_payload.bin').read_bytes()]
    for raw in samples:
        packed=module.pack_zero_runs(raw)
        (p/'raw').write_bytes(raw);(p/'packed').write_bytes(packed)
        # Bounds/UB checks remain active; LeakSanitizer cannot run under this sandbox's ptrace.
        subprocess.run([str(p/'test'),str(p/'packed'),str(p/'raw')],check=True,
                       env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'))
        print(f'raw={len(raw)} packed={len(packed)}')

#!/usr/bin/env python3
"""New HUD readback mode: both banks, bounded reads, rejected corruption, no board."""
import argparse, ctypes, hashlib, json, os, struct, subprocess, zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
WRAPPER=r'''
#include "prodock-uapi.h"
#include <assert.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
int __real_open(const char *,int,...);
int __real_close(int);
int __real_ioctl(int,unsigned long,...);
void *__real_mmap(void *,size_t,int,int,int,off_t);
int __real_munmap(void *,size_t);
static void *mapped;
int __wrap_open(const char *p,int flags,...) {
 if(!strcmp(p,"/dev/prodock-gpu"))return 900;
 assert(strncmp(p,"/dev/",5));return __real_open(p,flags,0600);
}
int __wrap_close(int fd){return fd==900?0:__real_close(fd);}
int __wrap_ioctl(int fd,unsigned long op,...) {
 va_list a;va_start(a,op);void *p=va_arg(a,void *);va_end(a);
 if(fd!=900)return __real_ioctl(fd,op,p);
 assert(op==PRODOCK_INFO);
 *(struct prodock_info *)p=(struct prodock_info){.width=800,.height=480};return 0;
}
void *__wrap_mmap(void *p,size_t n,int prot,int flags,int fd,off_t off) {
 if(fd!=900)return __real_mmap(p,n,prot,flags,fd,off);
 assert(!p&&!off&&n==(22U<<20)&&prot==PROT_READ&&flags==MAP_SHARED&&!mapped);
 mapped=calloc(1,n);assert(mapped);
 for(unsigned bank=20;bank<=21;bank++)for(unsigned i=0;i<800*300;i++)((unsigned char *)mapped)[(bank<<20)+i]=i%6;
 if(getenv("HUD_MISMATCH"))((unsigned char *)mapped)[21U<<20]=42;
 return mapped;
}
int __wrap_munmap(void *p,size_t n) {
 if(p!=mapped)return __real_munmap(p,n);
 assert(n==(22U<<20));free(mapped);mapped=NULL;return 0;
}
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 repo=HERE.parents[4]
 (out/'wrapper.c').write_text(WRAPPER)
 command=['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-I'+str(repo/'linux/drivers'),str(HERE/'runtime_inspect.c'),str(out/'wrapper.c'),*[f'-Wl,--wrap={f}' for f in ('open','close','ioctl','mmap','munmap')],'-o',str(out/'helper')]
 subprocess.run(command,check=True)
 lib=ctypes.CDLL('liblz4.so.1');lib.LZ4_compress_default.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
 raw=bytes(i%6 for i in range(800*300));compressed=ctypes.create_string_buffer(len(raw)*2)
 count=lib.LZ4_compress_default(raw,compressed,len(raw),len(compressed));assert count>0
 crc=zlib.crc32(raw);packed=struct.pack('<4I',0x4c345a4c,len(raw),count,crc)+compressed.raw[:count]
 (out/'hud.lz4').write_bytes(packed)
 cases=[]
 for name,bank,size,checksum,mismatch,expected in [
  ('bank20','bank20',len(raw),crc,False,0),('bank21','bank21',len(raw),crc,False,0),
  ('bad_bank','bank22',len(raw),crc,False,1),('bad_crc','bank20',len(raw),crc^1,False,1),
  ('bad_size','bank20',len(raw)+800,crc,False,1),('mismatch','bank21',len(raw),crc,True,1)]:
  env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1')
  if mismatch:env['HUD_MISMATCH']='1'
  run=subprocess.run([str(out/'helper'),'hud',str(out/'hud.lz4'),bank,str(size),f'{checksum:08x}'],capture_output=True,env=env)
  (out/(name+'.log')).write_bytes(run.stdout+run.stderr)
  assert run.returncode==expected,(name,run.returncode,run.stderr)
  if not expected:assert f'mismatch=0 actual_crc={crc:08x} expected_crc={crc:08x}'.encode() in run.stdout
  cases.append(name)
 (out/'result.json').write_text(json.dumps(dict(passed=True,hardware=False,cases=cases,compile=command,source_sha256=hashlib.sha256((HERE/'runtime_inspect.c').read_bytes()).hexdigest()),indent=2)+'\n')
 print('HUD_READBACK_TEST_PASS',cases)
if __name__=='__main__':main()

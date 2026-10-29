#define main stage_program_main
#include "stage_reader.c"
#undef main
#include <assert.h>
#include <stdio.h>
#include <sys/stat.h>
static unsigned char *readall(const char *path,size_t size)
{
    unsigned char *b=malloc(size);assert(b);FILE *f=fopen(path,"rb");assert(f);
    assert(fread(b,1,size,f)==size && fgetc(f)==EOF);fclose(f);return b;
}
int main(int argc,char **argv)
{
    assert(argc==3);unsigned char *p=readall(argv[1],PACKED_BYTES),*expected=readall(argv[2],ELF_BYTES);
    char out[100],linkpath[100];snprintf(out,sizeof out,"/tmp/stage-test-%ld",(long)getpid());snprintf(linkpath,sizeof linkpath,"/tmp/stage-link-%ld",(long)getpid());
    assert(access(out,F_OK)&&access(linkpath,F_OK));
    p[100]^=1;assert(extract_stage(p,PACKED_BYTES,out)==2 && access(out,F_OK));p[100]^=1;
    assert(extract_stage(p,PACKED_BYTES-1,out)==2 && access(out,F_OK));
    assert(extract_stage(p,PACKED_BYTES,"/tmp/escape/x")==2);
    assert(extract_stage(p,PACKED_BYTES,out)==0);
    unsigned char *actual=readall(out,ELF_BYTES);assert(!memcmp(actual,expected,ELF_BYTES));free(actual);
    assert(extract_stage(p,PACKED_BYTES,out)==6);
    assert(!symlink(out,linkpath));assert(extract_stage(p,PACKED_BYTES,linkpath)==6);
    actual=readall(out,ELF_BYTES);assert(!memcmp(actual,expected,ELF_BYTES));free(actual);
    assert(!unlink(linkpath)&&!unlink(out));free(p);free(expected);
    puts("PASS exact 16640496 bytes, bad packed CRC, short mapping, traversal, existing output, final symlink; no GPU hardware");return 0;
}

#define _POSIX_C_SOURCE 200809L
/* Small native G3D1 oracle, separate from the evolving game renderer. */
#include "gpu_geometry.h"
#include "prodock-uapi.h"
#include "prodock-validate.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#define BASE PRODOCK_GPU_BASE
#define BYTES (8u<<20)
#define MESH (6u<<20)
#define Q 65536
static struct prodock_batch batch;
static int valid=1;
static void emit(const gpu_command *c) {
    if(batch.count==PRODOCK_BATCH_MAX||prodock_command(c->words)) {valid=0;return;}
    memcpy(batch.commands[batch.count++],c->words,32);
}
static int call(int fd,unsigned long op,void *p) {if(ioctl(fd,op,p)) {perror("geometry probe ioctl");return 0;}return 1;}
static int draw(gpu_v1_context *g,gpu_geom_mesh mesh,int x,int z,unsigned color) {
    gpu_geom_transform t={{Q,0,0,x*Q,0,Q,0,0,0,0,Q,z*Q}};
    gpu_geom_light light={0,0,-32767,256,0};
    gpu_material m={GPU_Z_TEST|GPU_Z_WRITE,256,color,256,256,256,0,0,0};
    return gpu_v1_material(g,&m)&&gpu_geom_instance(g,&mesh,&t,&light,1);
}
static int patch(const unsigned char *memory,unsigned page,int x,int y,unsigned color) {
    for(int dy=-3;dy<=3;dy++)for(int dx=-3;dx<=3;dx++) {
        const uint16_t *p=(const uint16_t *)(memory+page+(y+dy)*1600+(x+dx)*2);
        if(*p!=color) {fprintf(stderr,"G3D pixel (%d,%d)=%04x expected=%04x\n",x+dx,y+dy,*p,color);return 0;}
    }return 1;
}
static int capture(const char *prefix,unsigned phase,const unsigned char *memory) {
    char path[1024];FILE *f;
    snprintf(path,sizeof(path),"%s_%u.commands",prefix,phase);f=fopen(path,"wb");if(!f)return 0;
    int ok=fwrite(batch.commands,32,batch.count,f)==batch.count;if(fclose(f))ok=0;
    snprintf(path,sizeof(path),"%s_%u.memory",prefix,phase);f=fopen(path,"wb");if(!f)return 0;
    ok&=fwrite(memory,1,BYTES,f)==BYTES;if(fclose(f))ok=0;
    snprintf(path,sizeof(path),"%s_%u.json",prefix,phase);f=fopen(path,"w");if(!f)return 0;
    fprintf(f,"{\"width\":400,\"height\":240,\"pitch\":1600,\"page_bytes\":1048576,\"page\":%u,\"bytes\":%u,\"commands\":%u}\n",3+phase,BYTES,batch.count);
    if(fclose(f))ok=0;return ok;
}
int main(int argc,char **argv) {
    const char *prefix=argc==3&&!strcmp(argv[1],"--capture")?argv[2]:NULL;
    if(argc!=1&&!prefix)return 2;
    int fd=-1,display=-1,ok=0;unsigned char *memory=NULL;
    struct prodock_geometry_info before={0},after={0};struct prodock_display_info di={0};
    if(!prefix) {
        fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);display=open("/dev/prodock-display",O_RDWR|O_CLOEXEC);
        struct prodock_info info;
        if(fd<0||display<0||!call(fd,PRODOCK_INFO,&info)||info.abi!=1||info.width!=800||info.height!=480||info.faulted||info.errors)goto done;
        if(!call(fd,PRODOCK_GEOMETRY_INFO,&before)||before.signature!=PRODOCK_GEOMETRY_SIGNATURE||before.errors)goto done;
        memory=mmap(NULL,BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
        if(memory==MAP_FAILED) {memory=NULL;goto done;}
        struct prodock_layout layout={.mode=PRODOCK_GAME};if(!call(display,PRODOCK_LAYOUT,&layout))goto done;
    } else memory=calloc(1,BYTES);
    if(!memory)goto done;
    const gpu_geom_vertex vertices[4]={{-Q,-Q,0,{0}},{Q,-Q,0,{0}},{Q,Q,0,{0}},{-Q,Q,0,{0}}};
    const unsigned gains=256|(256<<9)|(256<<18);
    const gpu_geom_face faces[4]={{{0x01010200,0,0,0,0,32769,gains,0}},{{0x01020300,0,0,0,0,32769,gains,0}},
                                 {{0x01020100,0,0,0,0,32767,gains,0}},{{0x01030200,0,0,0,0,32767,gains,0}}};
    memcpy(memory+MESH,vertices,sizeof(vertices));memcpy(memory+MESH+128,faces,sizeof(faces));
    if(memcmp(memory+MESH,vertices,sizeof(vertices))||memcmp(memory+MESH+128,faces,sizeof(faces)))goto done;
    gpu_geom_mesh mesh={BASE+MESH,BASE+MESH+128,4,2},back=mesh;back.faces+=64;
    gpu_v1_context gpu;gpu_v1_init(&gpu,emit);unsigned depths[2]={0};
    for(unsigned phase=0;phase<2;phase++) {
        batch.count=0;gpu_target target={BASE+((3+phase)<<20),BASE+(5<<20),400,240,1600,1600};
        gpu_geom_camera camera={Q,16*Q,200*Q,200*Q,200,120};
        if(!gpu_v1_target(&gpu,&target)||!gpu_v1_scissor(&gpu,0,0,400,240)||!gpu_v1_clear(&gpu,3,0,65535,0,0,400,240)||!gpu_geom_set_camera(&gpu,&camera))goto done;
        /* Near first, far second: without depth testing blue would overwrite red. */
        if(!draw(&gpu,mesh,phase?3:0,4,0xf800)||!draw(&gpu,mesh,0,8,0x001f)||!draw(&gpu,back,-3,4,0x07e0)||!valid)goto done;
        if(prefix) {if(!capture(prefix,phase,memory))goto done;continue;}
        if(!call(fd,PRODOCK_SUBMIT,&batch)||!call(fd,PRODOCK_GEOMETRY_INFO,&after)||after.errors!=before.errors)goto done;
        if(!patch(memory,(3+phase)<<20,200,120,phase?0x001f:0xf800)||!patch(memory,(3+phase)<<20,50,120,0)||!patch(memory,(3+phase)<<20,350,120,phase?0xf800:0))goto done;
        depths[phase]=*(uint16_t *)(memory+(5<<20)+120*1600+200*2);
        struct prodock_scene scene={.base=target.color,.stride=1600,.format=7};
        if(!call(fd,PRODOCK_PRESENT,&scene))goto done;
        printf("LUMA3D_GEOMETRY_PHASE phase=%u pixels=147 depth=%u commands=%u\n",phase,depths[phase],batch.count);fflush(stdout);
    }
    if(!prefix) {
        if(!(depths[0]<depths[1]&&depths[1]<65535)||after.vertices-before.vertices!=24||after.triangles-before.triangles!=8||after.culled-before.culled!=4)goto done;
        if(!call(display,PRODOCK_DISPLAY_INFO,&di)||di.errors||di.underflows||di.invalid_layers||di.invalid_sprites||di.faulted)goto done;
        printf("LUMA3D_GEOMETRY_OK phases=2 pixels=294 vertices=%u triangles=%u culled=%u errors=%u uf=%u invalid=%u sprites=%u fault=%u\n",after.vertices-before.vertices,after.triangles-before.triangles,after.culled-before.culled,after.errors,di.underflows,di.invalid_layers,di.invalid_sprites,di.faulted);
    }ok=1;
done:
    if(memory) {if(prefix)free(memory);else munmap(memory,BYTES);}
    if(fd>=0)close(fd);if(display>=0)close(display);return !ok;
}

/* SPDX-License-Identifier: MIT
 * Temporary Linux userspace transport, no GPU, MMIO, JTAG or persistent disk.
 * Freestanding RV32 ELF keeps the serial bootstrap small. Blocks are CRC32
 * verified before writing; retransmission uses sequence numbers. */
typedef unsigned int u32;
typedef unsigned char u8;
static long call(long nr,long p0,long p1,long p2,long p3){register long a0 __asm__("a0")=p0;register long a1 __asm__("a1")=p1;register long a2 __asm__("a2")=p2;register long a3 __asm__("a3")=p3;register long a7 __asm__("a7")=nr;__asm__ volatile("ecall":"+r"(a0):"r"(a1),"r"(a2),"r"(a3),"r"(a7):"memory");return a0;}
static int io(int writing,int fd,void *ptr,u32 n){u8 *p=ptr;while(n){long k=call(writing?64:63,fd,(long)p,n,0);if(k==-4)continue;if(k<=0)return -1;p+=k;n-=(u32)k;}return 0;}
static u32 crc(u32 c,const u8 *p,u32 n){while(n--){c^=*p++;for(int k=0;k<8;k++)c=(c>>1)^(0xedb88320U&-(c&1));}return c;}
static void answer(u8 c,u32 seq){u8 b[5]={c,(u8)seq,(u8)(seq>>8),(u8)(seq>>16),(u8)(seq>>24)};io(1,1,b,5);}
static u8 block[1024],saved[36],raw[36];
__attribute__((used,noreturn)) void boot(long *stack){
 char *path=stack[0]>1?(char *)stack[2]:0;int result=1,fd=-1,changed=0;
 if(!path||path[0]!='/'||path[1]!='t'||path[2]!='m'||path[3]!='p'||path[4]!='/')goto done;
 if(call(29,0,0x5401,(long)saved,0))goto done;for(unsigned i=0;i<36;i++)raw[i]=saved[i];
 ((u32 *)raw)[0]&=~(2U|16U|32U|256U|1024U);((u32 *)raw)[1]&=~1U;((u32 *)raw)[2]|=48;((u32 *)raw)[3]&=~(1U|2U|8U|32768U);raw[17+5]=0;raw[17+6]=1;
 if(call(29,0,0x5402,(long)raw,0))goto done;changed=1;
 fd=(int)call(56,-100,(long)path,577,0700);if(fd<0)goto done;
 answer('R',0);u32 expect=0,total=0,checksum=~0U;
 for(;;){u32 magic=0;u8 byte;while(magic!=0x31414d4c){if(io(0,0,&byte,1))goto done;magic=(magic>>8)|((u32)byte<<24);}
  u32 h[3];if(io(0,0,h,sizeof(h)))goto done;u32 seq=h[0],len=h[1],hash=h[2];if(len>sizeof(block)){answer('N',expect);continue;}
  if(!len){if(seq==expect&&hash==~checksum){answer('D',total);result=0;}else answer('F',total);break;}
  if(io(0,0,block,len))goto done;if(~crc(~0U,block,len)!=hash){answer('N',expect);continue;}
  if(seq<expect){answer('A',seq);continue;}if(seq!=expect){answer('N',expect);continue;}
  if(io(1,fd,block,len))goto done;checksum=crc(checksum,block,len);total+=len;answer('A',expect++);
 }
done:
 if(fd>=0)call(57,fd,0,0,0);if(changed)call(29,0,0x5402,(long)saved,0);call(93,result,0,0,0);for(;;){}
}
__attribute__((naked,noreturn)) void _start(void){__asm__ volatile(".option push\n.option norelax\nla gp,__global_pointer$\n.option pop\nmv a0,sp\ncall boot\n1: j 1b");}

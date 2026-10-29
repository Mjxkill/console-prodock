"""Bounded interpreter for the exact RV32 diagnostic binary, not an AE350 model.

Only instructions present in this program are accepted. All bus accesses are
recorded and restricted. Vendor CSRs are modeled registers: this checks payload
control flow/footprint, not their physical operation or any FPGA timing.
"""
from pathlib import Path
import struct

BASE=0xa0004000
JOURNAL=0xa0006000
SCRATCH=0x12000000
GPU=0xe9001000
VIDEO=0xe9000000
MASK=0xffffffff

def signed(value,bits):
    sign=1<<(bits-1)
    return (value&(sign-1))-(value&sign)

class RV32:
    def __init__(self,binary,fault=None,cache=0,milmb=0xa0000001):
        self.code=bytes(binary);self.pc=BASE;self.reg=[0]*32;self.steps=0
        self.csr={0x305:0x80000000,0x300:0x1800,0x304:0,0x180:0,
                  0x7ca:cache,0x7c0:milmb,0x342:0,0x343:0,0x341:0}
        self.memory={};self.accesses=[];self.commands=[];self.packet=[]
        self.done=0;self.rejected=0;self.fault=fault;self.target=None;self.trapped=False
        self.gpu_writes=[]

    def word(self,address):
        return sum(self.memory.get(address+i,0)<<(i*8) for i in range(4))

    def put(self,address,value):
        for i in range(4):self.memory[address+i]=(value>>(i*8))&255

    def access(self,address,write=False,value=0):
        if address&3:raise AssertionError('unaligned access')
        self.accesses.append((write,address,value))
        if BASE<=address<BASE+len(self.code):
            if write:raise AssertionError('code write')
            return struct.unpack_from('<I',self.code,address-BASE)[0]
        if JOURNAL<=address<JOURNAL+512:
            if write:self.put(address,value)
            return self.word(address)
        if SCRATCH<=address<SCRATCH+128:
            if self.fault=='load_trap' and not write and not self.trapped:
                self.trapped=True;self.csr[0x342]=5;self.csr[0x343]=address
                self.csr[0x341]=self.pc;self.pc=self.csr[0x305]
                raise Trap
            if write:self.put(address,value)
            value=self.word(address)
            if self.fault=='seed_corrupt' and not write and self.done==0 and address==SCRATCH+12:
                value^=1
            return value
        if address in (VIDEO+8,VIDEO+12,VIDEO+20):
            assert not write
            return 0
        if address in (GPU,GPU+4,GPU+8,GPU+12,GPU+28,GPU+52):
            assert not write
            return {GPU:0x424c5432,GPU+8:self.done,GPU+52:self.rejected}.get(address,0)
        if address==GPU+16 and write:
            self.packet.append(value)
            if len(self.packet)==8:
                self.command(self.packet);self.commands.append(self.packet[:]);self.packet=[]
            return 0
        raise AssertionError(f'unexpected {"write" if write else "read"} {address:#x}')

    def command(self,words):
        if words[0]==0x16000000:
            # Decode the public ABI: width is HIGH16, height LOW16. Bounds
            # and overlap are computed, not inferred from expected literals.
            color,z=words[1:3];width=words[3]>>16;height=words[3]&65535
            color_stride=words[4]>>16;z_stride=words[4]&65535
            color_end=color+color_stride*height;z_end=z+z_stride*height
            valid=(color<0x40000000 and z<0x40000000 and color%32==0 and z%32==0
                and 1<=width<=1024 and 1<=height<=512 and color_stride%32==0
                and z_stride%32==0 and color_stride>=width*2 and z_stride>=width*2
                and color_end<=0x40000000 and z_end<=0x40000000
                and not(color<z_end and z<color_end) and words[5:]==[0,0,0])
            self.target=(color,z,width,height,color_stride,z_stride) if valid else None
            if not valid:self.rejected+=1;self.done+=1;return
            if self.fault=='target_touch':self.put(SCRATCH,self.word(SCRATCH)^1)
            if self.fault!='target_timeout':self.done+=1
        elif words[0]==0x1c000000:
            if not self.target or words[1]>3 or words[2]>65535 or words[3]>65535 or words[6:]!=[0,0]:
                self.rejected+=1;self.done+=1;return
            if self.fault=='clear_timeout':return
            color,z,width,height,color_stride,z_stride=self.target
            x=signed(words[4]>>16,16);y=signed(words[4]&65535,16)
            end_x=x+(words[5]>>16);end_y=y+(words[5]&65535)
            if self.fault!='clear_missing':
                for flag,base,stride,value in [(1,color,color_stride,words[2]),(2,z,z_stride,words[3])]:
                    if not words[1]&flag:continue
                    for row in range(max(0,y),min(height,end_y)):
                        for col in range(max(0,x),min(width,end_x)):
                            address=base+row*stride+2*col
                            if not SCRATCH<=address<SCRATCH+127:raise AssertionError('GPU outside scratch')
                            self.memory[address]=value&255;self.memory[address+1]=value>>8
                            self.gpu_writes.append(address)
            if self.fault=='clear_canary':self.put(SCRATCH+64,0)
            self.done+=1
        else:raise AssertionError('unexpected GPU command')

    def run(self,limit=1500000):
        while self.pc!=0x80000000:
            if self.steps>=limit:raise AssertionError('CPU model instruction bound')
            if not BASE<=self.pc<BASE+len(self.code):raise AssertionError('PC outside payload')
            self.steps+=1
            ins=struct.unpack_from('<I',self.code,self.pc-BASE)[0]
            op=ins&127;rd=(ins>>7)&31;f3=(ins>>12)&7
            rs1=(ins>>15)&31;rs2=(ins>>20)&31;f7=ins>>25
            x,y=self.reg[rs1],self.reg[rs2];nextpc=(self.pc+4)&MASK;out=None
            try:
                if op==0x37:out=ins&0xfffff000
                elif op==0x17:out=self.pc+(ins&0xfffff000)
                elif op==0x13:
                    imm=signed(ins>>20,12)
                    if f3==0:out=x+imm
                    elif f3==7:out=x&imm
                    elif f3==1 and f7==0:out=x<<rs2
                    elif f3==5 and f7==0:out=x>>rs2
                    else:raise AssertionError(f'unsupported immediate {ins:08x}')
                elif op==0x33:
                    if f3==4 and f7==0:out=x^y
                    elif f3==6 and f7==0:out=x|y
                    elif f3==0 and f7==0:out=x+y
                    else:raise AssertionError('unsupported integer op')
                elif op==3 and f3==2:out=self.access((x+signed(ins>>20,12))&MASK)
                elif op==0x23 and f3==2:
                    imm=((ins>>25)<<5)|((ins>>7)&31)
                    self.access((x+signed(imm,12))&MASK,True,y)
                elif op==0x63:
                    imm=((ins>>31)<<12)|(((ins>>7)&1)<<11)|(((ins>>25)&63)<<5)|(((ins>>8)&15)<<1)
                    conditions={0:x==y,1:x!=y,4:signed(x,32)<signed(y,32),
                                5:signed(x,32)>=signed(y,32),6:x<y,7:x>=y}
                    if f3 not in conditions:raise AssertionError('branch opcode')
                    if conditions[f3]:nextpc=(self.pc+signed(imm,13))&MASK
                elif op==0x6f:
                    imm=((ins>>31)<<20)|(((ins>>12)&255)<<12)|(((ins>>20)&1)<<11)|(((ins>>21)&1023)<<1)
                    out=self.pc+4;nextpc=(self.pc+signed(imm,21))&MASK
                elif op==0x67 and f3==0:
                    out=self.pc+4;nextpc=(x+signed(ins>>20,12))&0xfffffffe
                elif op==0x0f and f3 in (0,1):pass
                elif op==0x73 and f3 in (1,2):
                    csr=ins>>20
                    if csr not in self.csr:raise AssertionError('unmodeled CSR')
                    out=self.csr[csr]
                    if f3==1:self.csr[csr]=x
                    elif rs1:self.csr[csr]|=x
                else:raise AssertionError(f'unsupported instruction {ins:08x} at {self.pc:08x}')
            except Trap:continue
            if rd and out is not None:self.reg[rd]=out&MASK
            self.reg[0]=0;self.pc=nextpc
        return [self.word(JOURNAL+4*i) for i in range(128)]

class Trap(Exception):pass

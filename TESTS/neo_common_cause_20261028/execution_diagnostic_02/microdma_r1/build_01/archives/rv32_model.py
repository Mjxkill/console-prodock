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
        self.done=0;self.fault=fault;self.target=False;self.trapped=False
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
            return {GPU:0x424c5432,GPU+8:self.done}.get(address,0)
        if address==GPU+16 and write:
            self.packet.append(value)
            if len(self.packet)==8:
                self.command(self.packet);self.commands.append(self.packet[:]);self.packet=[]
            return 0
        raise AssertionError(f'unexpected {"write" if write else "read"} {address:#x}')

    def command(self,words):
        if words[0]==0x16000000:
            assert words==[0x16000000,SCRATCH+32,SCRATCH+64,0x10010,0x200020,0,0,0]
            self.target=True
            if self.fault=='target_touch':self.put(SCRATCH,self.word(SCRATCH)^1)
            if self.fault!='target_timeout':self.done+=1
        elif words[0]==0x1c000000:
            assert self.target
            assert words==[0x1c000000,1,0x6b4d,0,0,0x10010,0,0]
            if self.fault=='clear_timeout':return
            if self.fault!='clear_missing':
                for address in range(SCRATCH+32,SCRATCH+64,4):
                    self.put(address,0x6b4d6b4d);self.gpu_writes.append(address)
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

"""RX2 host protocol. Generic I/O only: no device open or shell launch by default.

The caller owns the exclusive console lock, identity, storage and bootstrap.
After launch, this module emits only Base64/NUL until a fresh RETURN is observed.
"""
import base64
import dataclasses
import math
import re
import struct
import time
import zlib

BLOCK=512
SAFE=frozenset(b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\0')
LINE=re.compile(rb'RX2 ([0-9a-f]{32}) ([RANX]) ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8})')

def crc(data):return zlib.crc32(data)&0xffffffff
def frame(nonce,op,seq,offset,data=b''):
    head=b'LX2P'+bytes.fromhex(nonce)+struct.pack('<5I',op,seq,offset,len(data),crc(data))
    assert len(head)==40 and len(data)<=BLOCK
    wire=b'\0'+base64.b64encode(head+struct.pack('<I',crc(head))+data)+b'\0'
    assert set(wire)<=SAFE
    return wire

@dataclasses.dataclass(frozen=True)
class Reply:
    kind:str; seq:int; offset:int; prefix:int; reason:int

class TransferError(RuntimeError):pass
class Uncertain(TransferError):pass

class Session:
    def __init__(self,io,nonce,data,idle_ms=5000,total_ms=1800000,chunk=16,pause=.002):
        if not re.fullmatch('[0-9a-f]{32}',nonce):raise ValueError('nonce')
        if len(data)>32*1024*1024 or not 100<=idle_ms<=30000 or not idle_ms<=total_ms<=3600000:raise ValueError('bounds')
        if type(chunk)!=int or not 1<=chunk<=4096 or not math.isfinite(pause) or pause<0:raise ValueError('pacing')
        full_frame=math.ceil(746/chunk)*pause
        if full_frame+max(.02,full_frame*.25)>idle_ms/1000:raise ValueError('pacing exceeds idle budget')
        if math.ceil(len(data)/BLOCK)*full_frame>total_ms/1000:raise ValueError('pacing exceeds total budget')
        self.io,self.nonce,self.data=io,nonce,bytes(data)
        self.idle_ms,self.total_ms,self.chunk,self.pause=idle_ms,total_ms,chunk,pause
        self.pending=bytearray();self.replies=[];self.returncode=None;self.ready=False;self.offset=0;self.seq=0;self.sent_frames=0;self.retries=0;self.terminal=None
        self.started=time.monotonic();self.return_seen=False;self.cancelled=False
        self.return_line=re.compile(rb'RX2_RETURN_'+nonce.encode()+rb':([0-9]+)')
        # Linear construction, rather than rehashing an ever-growing prefix
        # for every block of a multi-megabyte ELF.
        self.prefixes={0:0};prefix=0
        for offset in range(0,len(self.data),BLOCK):
            part=self.data[offset:offset+BLOCK];prefix=zlib.crc32(part,prefix)&0xffffffff
            self.prefixes[offset+len(part)]=prefix

    def command(self,executable,path,resume=False):
        if not re.fullmatch('/tmp/luma-rx2-[a-z0-9_-]+',executable):raise ValueError('RX path')
        if not re.fullmatch('/tmp/rx2-[a-z0-9_.-]+',path) or '..' in path or len(path)>220:raise ValueError('target path')
        # Sole textual command, BEFORE this Session receives READY. Root must
        # confirm a shell and verify executable bytes before issuing it.
        return (f"rc=0; {executable} {path} {self.nonce} {len(self.data)} {crc(self.data):08x} "
                f"{'resume' if resume else 'new'} {self.idle_ms} {self.total_ms} || rc=$?; "
                f"printf '\\nRX2_RETURN_{self.nonce}:%s\\n' \"$rc\"\n").encode()

    def _line(self,line):
        line=line.rstrip(b'\r')
        m=self.return_line.fullmatch(line)
        if m:
            self.returncode=int(m[1]);self.return_seen=True;return ('return',self.returncode)
        m=LINE.fullmatch(line)
        if m:
            if m[1].decode()!=self.nonce:raise Uncertain('foreign nonce reply')
            if crc(line.rsplit(b' ',1)[0])!=int(m[7],16):raise Uncertain('reply CRC')
            r=Reply(m[2].decode(),*[int(m[i],16) for i in range(3,7)])
            self.replies.append(r)
            if r.kind=='X':self.terminal=r
            return ('reply',r)
        if line.startswith(b'RX2 '):raise Uncertain('malformed reply')
        if self.ready and line and line not in (b'RX2_PROMPT> ',):
            raise Uncertain('unexpected receiver output '+repr(line[:100]))
        # A bounded printable command echo/banner may precede READY.
        if not self.ready and any(c<32 and c not in (9,13) for c in line):raise Uncertain('nontext preamble')
        return None

    def event(self,timeout):
        end=time.monotonic()+timeout;received=0
        while time.monotonic()<end:
            while b'\n' in self.pending:
                line,_,tail=self.pending.partition(b'\n');self.pending[:]=tail
                r=self._line(bytes(line))
                if r:return r
            b=self.io.read(min(.1,max(0,end-time.monotonic())))
            if b:self.pending.extend(b);received+=len(b)
            if len(self.pending)>8192 or received>32768:raise Uncertain('bounded output exceeded')
        raise Uncertain('receive timeout; no retransmission allowed')

    def _checkpoint(self,r):
        if r.offset>len(self.data) or r.offset%BLOCK and r.offset!=len(self.data):raise Uncertain('checkpoint offset')
        if r.seq!=(r.offset+BLOCK-1)//BLOCK or r.prefix!=self.prefixes[r.offset]:raise Uncertain('checkpoint prefix')

    def begin(self):
        kind,r=self.event(self.idle_ms/1000+2)
        if kind!='reply' or r.kind!='R' or r.reason:raise TransferError('receiver not ready')
        self._checkpoint(r);self.offset,self.seq=r.offset,r.seq;self.ready=True
        return r

    def send(self,wire):
        if not self.ready or self.return_seen or self.terminal:raise TransferError('receiver not active')
        if not wire or not set(wire)<=SAFE:raise ValueError('unsafe wire alphabet')
        self.sent_frames+=1
        # io.write must itself have a finite timeout. A partial write error
        # abandons this session; it never causes a replay of the frame.
        for i in range(0,len(wire),self.chunk):
            if time.monotonic()>=self.started+self.total_ms/1000:raise Uncertain('host session deadline')
            part=wire[i:i+self.chunk];n=self.io.write(part)
            if n!=len(part):raise Uncertain('partial transmit')
            if self.pause:time.sleep(self.pause)

    def block(self,mutate=None):
        if self.offset>=len(self.data):raise TransferError('no block remains')
        initial=self.offset;data=self.data[initial:initial+BLOCK];end=initial+len(data)
        packet=frame(self.nonce,1,self.seq,initial,data)
        for attempt in range(4):
            wire=mutate(packet,attempt) if mutate else packet;self.send(wire)
            deadline=time.monotonic()+self.idle_ms/1000+1
            while True:
                if time.monotonic()>=deadline:raise Uncertain('ACK deadline')
                kind,r=self.event(max(.001,deadline-time.monotonic()))
                if kind!='reply':raise TransferError('receiver returned during DATA')
                self._checkpoint(r)
                if r.kind=='X':raise TransferError('receiver terminal reason '+str(r.reason))
                if r.kind=='A' and r.offset==end and r.reason==0:
                    self.offset,self.seq=r.offset,r.seq;return r
                if r.kind=='A' and r.offset<=initial and r.reason==0:continue
                if r.kind=='N' and r.offset==initial and r.reason==1:
                    self.retries+=1;break
                raise Uncertain('unexpected acknowledgement')
        raise TransferError('NACK retry limit')

    def finish(self,stop=False):
        if not stop and self.offset!=len(self.data):raise TransferError('incomplete source')
        self.send(frame(self.nonce,3 if stop else 2,self.seq,self.offset))
        deadline=time.monotonic()+self.idle_ms/1000+2
        # A duplicate prior ACK may precede the terminal response.
        while not self.terminal:
            if time.monotonic()>=deadline:raise Uncertain('FIN deadline')
            kind,r=self.event(max(.001,deadline-time.monotonic()))
            if kind!='reply':raise Uncertain('return without terminal checkpoint')
            self._checkpoint(r)
            if r.kind=='A' and r.offset<=self.offset:continue
            if r.kind!='X':raise Uncertain('unexpected FIN response')
        self._checkpoint(self.terminal)
        expected=1 if stop else 0
        if self.terminal.reason!=expected:raise TransferError('terminal failure')
        self.await_return(max(.001,deadline-time.monotonic()))
        if self.returncode!=expected:raise TransferError('wrapper/terminal mismatch')
        return self.terminal

    def await_return(self,timeout=None):
        # This method NEVER writes. Use it even following timeout/corruption.
        if timeout is None:timeout=self.idle_ms/1000+3
        end=time.monotonic()+timeout
        while not self.return_seen:
            if time.monotonic()>=end:raise Uncertain('shell return not confirmed')
            try:self.event(max(.001,end-time.monotonic()))
            except Uncertain:
                # Malformed reply is not permission to send. Preserve the
                # remaining bytes and continue looking for the fresh wrapper.
                if time.monotonic()>=end:raise
        return self.returncode

    def cancel_line(self):
        if not self.return_seen:raise Uncertain('no fresh process return')
        if self.cancelled:raise TransferError('already cancelled')
        # A separate caller must now verify the prompt before a new command.
        if self.io.write(b'\x15\n')!=2:raise Uncertain('line cancellation partial')
        self.cancelled=True

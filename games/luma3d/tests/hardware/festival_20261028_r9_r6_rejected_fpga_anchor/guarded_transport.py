"""Candidate guard for the frozen LMA1 receiver; not integrated or board tested.

Never resend after silence, malformed replies or a terminal F/D. Only an
explicit matching N permits retry. Does not make the unprotected wire protocol
reliable against arbitrary corruption, nor recall bytes already in flight.
"""
import hashlib,json,re,struct,time,zlib

class ReceiverUncertain(RuntimeError):pass

def guarded_class(base):
    class GuardedTransport(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.receiver_state='idle';self.rx_checkpoint=lambda:None;self.trace=[];self.rx_carry=b''
        def set_state(self,state):
            self.receiver_state=state
            # Legacy boolean remains compatible but cannot mean "safe to send
            # abort" in uncertain states. Use guarded abort(), never the old one.
            self.receiver_active=state=='receiving'
        def run(self,*args,**kwargs):
            if self.receiver_state not in ('idle','complete','returned_error'):
                raise ReceiverUncertain('Shell commands forbidden until receiver return is confirmed')
            return super().run(*args,**kwargs)
        def ready(self,name):
            # The interactive shell can echo the command before the receiver
            # disables ECHO. Keep that bounded preamble and any terminal marker.
            data=bytearray();deadline=time.monotonic()+10;magic=b'R\0\0\0\0'
            exit_line=re.compile(rb'^LMA_RX_EXIT_'+re.escape(name.encode())+rb':([0-9]+)\r?\n',re.M)
            try:
                while time.monotonic()<deadline and len(data)<=8192:
                    at=data.find(magic)
                    if exit_line.search(data):raise ReceiverUncertain('Receiver exited during startup')
                    if at>=0:
                        if at+len(magic)!=len(data):raise ReceiverUncertain('Unexpected data after receiver readiness')
                        self.trace.append(dict(phase='ready',raw=data.hex()));self.rx_carry=b'';return
                    data.extend(self.uart.read(4096))
                raise ReceiverUncertain('Receiver readiness missing or preamble too long')
            except BaseException:
                self.rx_carry+=bytes(data);self.trace.append(dict(phase='ready_failed',raw=data[-8192:].hex()));raise
        def response(self,phase,seq,seconds=.5):
            data=bytearray();deadline=time.monotonic()+seconds
            try:
                while len(data)<5 and time.monotonic()<deadline:
                    data.extend(self.uart.read(5-len(data)))
            finally:
                self.rx_carry+=bytes(data)
                self.trace.append(dict(phase=phase,seq=seq,raw=data.hex()))
            if len(data)!=5:raise ReceiverUncertain('Missing/truncated ACK '+data.hex())
            return data[0],struct.unpack('<I',data[1:])[0]
        def write_packet(self,packet):
            # No automatic replay of a partial write. The delivered length of
            # an exception is unknown, so continuation requires a new trial.
            for i in range(0,len(packet),16):
                block=packet[i:i+16];n=self.uart.write(block)
                if n!=len(block):raise ReceiverUncertain('Partial UART write')
                self.uart.flush();time.sleep(.002)
        def returned_marker(self,name,seconds=1):
            data=bytearray(self.rx_carry);self.rx_carry=b'';deadline=time.monotonic()+seconds
            pattern=re.compile(rb'^LMA_RX_EXIT_'+re.escape(name.encode())+rb':([0-9]+)\r?\n',re.M)
            while time.monotonic()<deadline:
                found=pattern.findall(data)
                if found:
                    if len(found)!=1 or int(found[0])>255:break
                    self.trace.append(dict(exit_code=int(found[0]),return_bytes=data[-1024:].hex()))
                    return int(found[0])
                try:data.extend(self.uart.read(4096))
                except BaseException as error:
                    self.trace.append(dict(return_read_error=repr(error)));break
            self.rx_carry=bytes(data[-4096:]);self.trace.append(dict(return_unconfirmed=data[-1024:].hex()));return None
        def transfer(self,path,name,expected=None):
            if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):raise ValueError('Unsafe name')
            if self.receiver_state not in ('idle','complete','returned_error'):raise ReceiverUncertain('Previous receiver unresolved')
            blob=path.read_bytes();seq=0;retries=0;start=time.monotonic();self.trace=[];self.rx_carry=b'';valid_done=False
            actual=dict(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),crc32=f'{zlib.crc32(blob):08x}')
            if expected is not None and actual!=expected:raise ReceiverUncertain('Payload changed after preflight; nothing sent')
            self.rx_checkpoint();self.set_state('unknown')
            try:
                self.uart.reset_input_buffer()
                self.sendline('/tmp/luma-rx /tmp/'+name+'; rc=$?; printf "\\nLMA_RX_EXIT_'+name+':%s\\n" "$rc"')
                self.ready(name);self.set_state('receiving');self.rx_checkpoint()
                for offset in range(0,len(blob),512):
                    block=blob[offset:offset+512];packet=struct.pack('<4sIII',b'LMA1',seq,len(block),zlib.crc32(block))+block
                    for attempt in range(12):
                        self.rx_checkpoint();self.write_packet(packet)
                        code,n=self.response('data',seq)
                        if code==ord('A') and n==seq:self.rx_carry=b'';break
                        if code==ord('N') and n==seq:
                            self.rx_carry=b'';retries+=1;self.rx_checkpoint();continue
                        raise ReceiverUncertain(f'Unexpected data reply code={code} value={n} seq={seq}')
                    else:raise ReceiverUncertain('Explicit N retry limit reached')
                    seq+=1;self.rx_checkpoint()
                self.write_packet(struct.pack('<4sIII',b'LMA1',seq,0,zlib.crc32(blob)))
                code,n=self.response('end',seq)
                if code!=ord('D') or n!=len(blob):raise ReceiverUncertain(f'Unexpected final reply code={code} value={n}')
                # Classify the complete valid terminal reply before a signal
                # checkpoint. A D during data or with the wrong length never
                # reaches this state.
                valid_done=True;self.set_state('received_D');self.rx_checkpoint()
                rc=self.returned_marker(name)
                if rc!=0:raise ReceiverUncertain('Receiver shell return is not confirmed successful')
                self.set_state('complete')
                return dict(name=name,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),crc32=f'{zlib.crc32(blob):08x}',retries=retries,seconds=time.monotonic()-start)
            except BaseException:
                if self.receiver_state not in ('complete','returned_error'):
                    self.set_state('unknown')
                    # Read-only confirmation: no binary abort, Ctrl-C, shell
                    # command or retry is sent after uncertainty.
                    rc=self.returned_marker(name)
                    if rc is not None:self.set_state('complete' if valid_done and rc==0 else 'returned_error')
                raise
            finally:
                (self.out/(name+'.transport.json')).write_text(json.dumps(dict(receiver_state=self.receiver_state,trace=self.trace),indent=2)+'\n')
        def abort(self):
            if self.receiver_state in ('idle','complete','returned_error'):return
            raise ReceiverUncertain('Receiver state unresolved; no abort bytes or shell commands sent')
    return GuardedTransport

"""CRC transport reused from the completed LUMA R9b trial; RAM files only.

Caller owns /tmp/prodock-diagnostic.lock and exclusive serial port. A 1464-byte
receiver is read back byte-for-byte before execution. This module never opens
JTAG, resets a board, or decides which process to stop.
"""
import hashlib
import re
import struct
import time
import zlib

RECEIVER_SHA = '5964389b8244dc73b58bf916a7856da3cc3aba2c2efa58779d1f755bb8410ae4'


class Transport:
    def __init__(self, uart, command, out):
        self.uart, self.command, self.out = uart, command, out
        self.receiver_active = False

    def run(self, name, text, seconds=45):
        rc, data = self.command(self.uart, text, seconds)
        (self.out / (name+'.log')).write_bytes(data)
        if rc:
            raise RuntimeError((name,rc,data[-1500:]))
        return data

    def sendline(self, text):
        for byte in (text+'\n').encode():
            self.uart.write(bytes([byte])); time.sleep(.002)

    def marker(self, marker, seconds=10):
        data=bytearray(); until=time.monotonic()+seconds
        while time.monotonic()<until:
            data.extend(self.uart.read(4096))
            if marker in data:
                return bytes(data)
        raise TimeoutError(repr(data[-1500:]))

    def ack(self, seconds=.5):
        data=bytearray(); until=time.monotonic()+seconds
        while time.monotonic()<until:
            data.extend(self.uart.read(5-len(data)))
            if len(data)==5:
                return data[0],struct.unpack('<I',data[1:])[0]
        raise TimeoutError('Transport ack '+repr(data))

    def bootstrap(self, receiver):
        data=receiver.read_bytes()
        assert len(data)==1464 and hashlib.sha256(data).hexdigest()==RECEIVER_SHA
        self.uart.reset_input_buffer()
        for offset in range(0,len(data),96):
            escaped=''.join('\\%03o'%byte for byte in data[offset:offset+96])
            self.sendline("printf '"+escaped+"' "+('>' if offset==0 else '>>')+' /tmp/luma-rx; echo __RX_CHUNK__')
            self.marker(b'\r\n__RX_CHUNK__\r\n')
        readback=self.run('bootstrap_readback','od -b -v /tmp/luma-rx')
        octets=[]
        for line in readback.replace(b'\r',b'').splitlines():
            if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}',line.strip()):
                octets.extend(int(x,8) for x in line.split()[1:])
        assert bytes(octets)==data, 'Receiver mismatch: never execute it'
        self.run('bootstrap_mode','chmod 700 /tmp/luma-rx')

    def transfer(self, path, name):
        assert re.fullmatch(r'[a-zA-Z0-9_.-]+',name)
        blob=path.read_bytes(); retries=0; seq=0; start=time.monotonic()
        self.uart.reset_input_buffer(); self.sendline('/tmp/luma-rx /tmp/'+name)
        self.receiver_active=True; self.marker(b'R\0\0\0\0')
        for offset in range(0,len(blob),512):
            block=blob[offset:offset+512]
            packet=struct.pack('<4sIII',b'LMA1',seq,len(block),zlib.crc32(block))+block
            for attempt in range(12):
                for i in range(0,len(packet),16):
                    self.uart.write(packet[i:i+16]); self.uart.flush(); time.sleep(.002)
                try:
                    code,n=self.ack()
                except TimeoutError:
                    code,n=0,0
                if code==ord('A') and n==seq:
                    break
                retries+=1
            else:
                raise RuntimeError(('Serial transfer rejected',name,seq,code,n))
            seq+=1
            if seq%256==0:
                print(f'{name}: {offset+len(block)}/{len(blob)} bytes, retries={retries}',flush=True)
        self.uart.write(struct.pack('<4sIII',b'LMA1',seq,0,zlib.crc32(blob))); self.uart.flush()
        code,n=self.ack()
        assert code==ord('D') and n==len(blob),(name,code,n)
        self.receiver_active=False; time.sleep(.3); self.uart.read(4096)
        return dict(name=name,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),
                    crc32='%08x'%zlib.crc32(blob),retries=retries,seconds=time.monotonic()-start)

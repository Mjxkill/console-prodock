#!/usr/bin/env python3
"""Local browser keyboard controller; the game runs on the FPGA's LCD."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import serial
from serial.tools import list_ports


class Game:
    def __init__(self,port):
        self.dev=serial.Serial(port,115200,timeout=0,write_timeout=.3,exclusive=True)
        self.lock=threading.Lock();self.keys=0;self.received=0.;self.start_until=0.
        self.state={'ready':False,'error':'','speed':0,'distance':0,'hits':0,'fps':0}
        self.stop=threading.Event();self.worker=threading.Thread(target=self.run,daemon=True)
        self.worker.start()

    def controls(self,mask):
        with self.lock:
            if mask&16 and not self.keys&16:self.start_until=time.monotonic()+.1
            self.keys=mask;self.received=time.monotonic()

    def status(self):
        with self.lock:return dict(self.state)

    def run(self):
        pending=bytearray();poll=0.;began=time.monotonic()
        try:
            self.dev.write(b'XR')
            while not self.stop.wait(.04):
                now=time.monotonic();pending.extend(self.dev.read(self.dev.in_waiting))
                while b'\n\r' in pending:
                    line,_,pending=pending.partition(b'\n\r');line=line.decode('ascii',errors='replace').strip()
                    if 'FAIL' in line or 'TRAP' in line:raise RuntimeError(line)
                    with self.lock:
                        if line.startswith('RACE READY'):self.state['ready']=True
                        elif line.startswith('RACE STATUS'):
                            values=dict(field.split('=',1) for field in line.split()[2:])
                            self.state.update({k:int(v) for k,v in values.items()})
                        elif line.startswith('RACE BENCH'):
                            fields=dict(f.split('=',1) for f in line.split()[2:])
                            self.state['fps']=int(fields['fps_x100'])/100
                with self.lock:
                    ready=self.state['ready']
                    mask=self.keys if now-self.received<.25 else 0
                    if now<self.start_until:mask|=16
                if ready:
                    self.dev.write(bytes([0x80|mask]))
                    if now-poll>.5:self.dev.write(b'H');poll=now
                elif now-began>15:raise RuntimeError('La console ne répond pas à RACE READY.')
        except (serial.SerialException,OSError,RuntimeError,ValueError) as exc:
            with self.lock:self.state['error']=str(exc)+(' / '+repr(line) if isinstance(exc,ValueError) else '');self.state['ready']=False
        finally:
            try:self.dev.write(b'\x80X')
            except (serial.SerialException,OSError):pass
            self.dev.close()

    def close(self):
        self.stop.set();self.worker.join(timeout=2)


def handler(game,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def local(self):
            host=self.headers.get('Host','')
            return host in (f'localhost:{port}',f'127.0.0.1:{port}') and self.headers.get('Origin',f'http://{host}')==f'http://{host}'
        def send(self,body,kind):
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if not self.local():self.send_error(403);return
            if self.path=='/':self.send(Path(__file__).with_name('racer_controller.html').read_bytes(),'text/html; charset=utf-8')
            elif self.path=='/status':self.send(json.dumps(game.status()).encode(),'application/json')
            else:self.send_error(404)
        def do_POST(self):
            if not self.local():self.send_error(403);return
            if self.path!='/controls':self.send_error(404);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=3:raise ValueError()
                mask=int(self.rfile.read(length))
                if not 0<=mask<=31:raise ValueError()
            except ValueError:self.send_error(400);return
            game.controls(mask);self.send(b'{}','application/json')
    return Handler


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port');p.add_argument('--http-port',type=int,default=8765)
    a=p.parse_args()
    if not a.port:
        ports=[v.device for v in list_ports.comports() if (v.vid,v.pid)==(0x359f,0x2011)]
        if len(ports)!=1:raise SystemExit(f'Une console USB 359f:2011 attendue ; trouvé : {ports}')
        a.port=ports[0]
    game=Game(a.port)
    try:
        with ThreadingHTTPServer(('127.0.0.1',a.http_port),handler(game,a.http_port)) as server:
            print(f'Manette : http://localhost:{a.http_port} — LCD sur {a.port}',flush=True)
            try:server.serve_forever(poll_interval=.2)
            except KeyboardInterrupt:pass
    finally:game.close()


if __name__=='__main__':main()

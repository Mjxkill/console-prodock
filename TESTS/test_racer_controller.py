#!/usr/bin/env python3
"""Exercise the real browser UI against a local fake console, no FPGA changes."""
import importlib.util
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import os
import signal
import tempfile
import threading
import time
import sys
import json
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('racer_web',ROOT/'tools/racer_web.py')
web=importlib.util.module_from_spec(spec);spec.loader.exec_module(web)


class FakeGame:
    def __init__(self):self.keys=0;self.seen=[]
    def controls(self,mask):self.keys=mask;self.seen.append(mask)
    def status(self):return {'ready':True,'error':'','speed':250,'distance':500,'hits':0,'fps':55,'keys':self.keys}


def main():
    # A corrupted telemetry field must not silently kill the USB thread while
    # leaving the UI marked ready. It closes the port and releases controls.
    class BrokenSerial:
        def __init__(self):self.data=b'RACE READY\n\rRACE STATUS speed=\n\r';self.closed=False;self.writes=[]
        @property
        def in_waiting(self):return len(self.data)
        def read(self,n):result=self.data[:n];self.data=self.data[n:];return result
        def write(self,data):self.writes.append(data)
        def close(self):self.closed=True
    device=BrokenSerial();original=web.serial.Serial
    try:
        web.serial.Serial=lambda *a,**k:device
        usb=web.Game('test');usb.worker.join(timeout=2)
        assert not usb.worker.is_alive() and not usb.status()['ready'] and usb.status()['error']
        assert device.closed and device.writes[-1]==b'\x80X'
    finally:web.serial.Serial=original
    game=FakeGame()
    server=ThreadingHTTPServer(('127.0.0.1',0),web.handler(game,0))
    port=server.server_port;server.RequestHandlerClass=web.handler(game,port)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='racer_browser_',ignore_cleanup_errors=True) as work:
            with open(Path(work)/'chrome.log','w') as log:
                chrome=subprocess.Popen(['/usr/bin/google-chrome','--headless=new','--no-sandbox','--disable-gpu',
                    '--disable-extensions','--no-proxy-server','--disable-background-networking','--remote-debugging-port=0',f'--user-data-dir={work}','--no-first-run','about:blank'],stdout=log,stderr=log,start_new_session=True)
                try:
                    active=Path(work)/'DevToolsActivePort'
                    for _ in range(100):
                        if active.exists():break
                        if chrome.poll() is not None:raise RuntimeError((Path(work)/'chrome.log').read_text())
                        time.sleep(.1)
                    debug=active.read_text().splitlines()[0]
                    import urllib.request
                    response=urllib.request.urlopen(f'http://127.0.0.1:{port}/')
                    assert b'Mega Coast' in response.read()
                    subprocess.run(['node',str(ROOT/'TESTS/racer_browser_test.mjs'),str(port),debug],check=True)
                    assert any(mask&16 for mask in game.seen),'Start key was not transmitted'
                finally:
                    try:os.killpg(chrome.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                    chrome.wait(timeout=10)
    finally:server.shutdown();server.server_close()
    print('PASS browser: page loaded, start, simultaneous keys, release, focus loss, local origin checks')


if __name__=='__main__':
    if '--live-status' in sys.argv:
        page=urllib.request.urlopen('http://localhost:8765/').read()
        assert b'Mega Coast' in page
        state=json.load(urllib.request.urlopen('http://localhost:8765/status'))
        assert state['ready'] and not state['error'] and state.get('running')==1 and state.get('underflows')==0,state
        print('PASS live controller:',state)
    else:main()

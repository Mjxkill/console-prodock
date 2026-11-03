#!/usr/bin/env python3
"""Read-only project dashboard. Bind explicitly to the requested Tailscale IP.

Only fixed UI assets, structured status and evidence referenced by that status
are exposed. No directory browser, command execution or hardware access exists.
The collector is cached so browser refreshes never scan processes concurrently.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}
MAX_EVIDENCE = 196608


def evidence_paths(value):
    """Derive the allowlist from explicit evidence fields, never URL paths."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'evidence':
                if isinstance(item, str):
                    found.add(item)
                elif isinstance(item, list):
                    found.update(x for x in item if isinstance(x, str))
            found.update(evidence_paths(item))
    elif isinstance(value, list):
        for item in value:
            found.update(evidence_paths(item))
    return found


def read_evidence(root, path, allowed):
    if path not in allowed:
        raise ValueError('Cette preuve ne figure pas dans le registre.')
    target = Path(path)
    if target.is_absolute() or '..' in target.parts:
        raise ValueError('Chemin non autorisé.')
    target = root / target
    if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
        raise ValueError('Chemin non autorisé.')
    if target.suffix.lower() not in ('.json', '.md', '.txt', '.log'):
        raise ValueError('Format non publié ; consulter le dépôt local.')
    if not target.is_file():
        raise FileNotFoundError('Preuve absente sur ce PC.')
    size = target.stat().st_size
    # Large diagnostic logs show a bounded suffix, explicitly identified.
    with target.open('rb') as stream:
        if size > MAX_EVIDENCE:
            stream.seek(size - MAX_EVIDENCE)
        data = stream.read(MAX_EVIDENCE)
    return dict(path=path, bytes=size, truncated=size > MAX_EVIDENCE,
                sha256=hashlib.sha256(data).hexdigest() if size <= MAX_EVIDENCE else None,
                text=data.decode('utf-8', errors='replace'))


class Status:
    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()
        self.cached = None
        self.at = 0

    def get(self):
        with self.lock:
            if self.cached is None or time.monotonic() - self.at >= 0.8:
                from collector import collect
                self.cached = collect(self.root)
                self.cached['served_at'] = datetime.now(timezone.utc).isoformat()
                self.cached['read_only'] = True
                self.at = time.monotonic()
            return self.cached


def snapshot_signature(status):
    """Exclude clock-only fields; counters and task transitions still trigger."""
    copy = {key: value for key, value in status.items() if key not in ('generated_at', 'served_at')}
    copy['workers'] = [{key: value for key, value in worker.items() if key != 'elapsed_s'}
                       for worker in status.get('workers', [])]
    return json.dumps(copy, sort_keys=True, ensure_ascii=False, allow_nan=False)


class Handler(BaseHTTPRequestHandler):
    server_version = 'ConsoleDashboard/1'

    def send(self, code, body, content_type):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy',
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def json(self, value, code=200):
        self.send(code, json.dumps(value, ensure_ascii=False, allow_nan=False).encode(),
                  'application/json; charset=utf-8')

    def do_HEAD(self):
        if urlsplit(self.path).path == '/api/events':
            self.send(200, b'', 'text/event-stream; charset=utf-8')
            return
        self.do_GET()

    def events(self):
        """SSE: one-second observations, immediate first snapshot, heartbeats.

        Each browser has its own stream; collection is shared and cached. A
        missing collector never turns the previous snapshot into fresh evidence.
        Broken streams are closed and EventSource reconnects automatically.
        """
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-transform')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(b'retry: 1500\n\n')
        previous = None
        while True:
            try:
                status = self.server.status.get()
                signature = snapshot_signature(status)
                if signature != previous:
                    event, value = 'snapshot', status
                    previous = signature
                else:
                    event, value = 'heartbeat', {'time': datetime.now(timezone.utc).isoformat()}
            except Exception:
                event, value = 'collection_error', {'error': 'La collecte est indisponible.'}
                previous = None  # Recovery must send a complete snapshot.
            payload = json.dumps(value, ensure_ascii=False, allow_nan=False)
            self.wfile.write(('event: '+event+'\ndata: '+payload+'\n\n').encode())
            self.wfile.flush()
            time.sleep(1)

    def do_GET(self):
        url = urlsplit(self.path)
        try:
            if url.path in ASSETS:
                name, kind = ASSETS[url.path]
                self.send(200, (HERE / name).read_bytes(), kind)
            elif url.path == '/api/status':
                self.json(self.server.status.get())
            elif url.path == '/api/events':
                self.events()
            elif url.path == '/api/evidence':
                query = parse_qs(url.query)
                if set(query) != {'path'} or len(query['path']) != 1:
                    raise ValueError('Une seule preuve doit être demandée.')
                status = self.server.status.get()
                self.json(read_evidence(self.server.status.root, query['path'][0], evidence_paths(status)))
            elif url.path == '/health':
                self.json({'ok': True, 'read_only': True})
            else:
                self.json({'error': 'Page introuvable.'}, 404)
        except (ValueError, FileNotFoundError) as error:
            self.json({'error': str(error)}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            # Do not expose stack traces, environment or arbitrary file paths.
            self.log_error('collection failed')
            self.json({'error': 'Collecte indisponible ; les données précédentes peuvent être périmées.'}, 503)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8088)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.daemon_threads = True
    server.status = Status(ROOT)
    print(f'Dashboard: http://{args.bind}:{args.port}/', flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

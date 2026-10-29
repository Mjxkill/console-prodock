"""Trusted host-only, single-model gateway; never available inside tool box.

Only POST /v1/chat/completions is forwarded to the fixed Ollama HTTPS origin.
The model key lives here, not in OpenCode or the MCP tool environment. Counts
are real HTTP attempts, independent of CLI steps. Bodies/headers are not logged.
"""
from contextlib import contextmanager
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.error
import urllib.request


class ProviderProxy:
    def __init__(self, key, model, max_requests=128, opener=None):
        if not key or '\n' in key or '\r' in key:
            raise ValueError('invalid provider key')
        if type(max_requests) is not int or not 1 <= max_requests <= 512:
            raise ValueError('invalid request bound')
        self._key = key
        self.model = model
        self.token = secrets.token_hex(24)
        self.max_requests = max_requests
        self.records = []
        self._lock = threading.Lock()
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self._opener = opener or urllib.request.build_opener(NoRedirect()).open
        self.server = None
        self.thread = None

    def snapshot(self):
        """Return observed metadata only; no prompts, auth, response bodies."""
        with self._lock:
            return [dict(record) for record in self.records]

    def start(self):
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.0'

            def log_message(self, *args):
                pass

            def setup(self):
                super().setup()
                self.connection.settimeout(30)

            def reject(self, status, message):
                data = json.dumps({'error': {'message': message}}).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                if self.path != '/v1/chat/completions':
                    return self.reject(404, 'only chat completions allowed')
                if self.headers.get('Authorization') != 'Bearer ' + owner.token:
                    return self.reject(403, 'local authorization required')
                try:
                    length = int(self.headers.get('Content-Length', '-1'))
                    if not 1 <= length <= 4 << 20:
                        raise ValueError()
                    data = self.rfile.read(length)
                    if len(data) != length:
                        raise ValueError()
                    body = json.loads(data)
                    if not isinstance(body, dict) or body.get('model') != owner.model:
                        raise ValueError()
                    # A provider credential must never enter task/model data.
                    if owner._key.encode() in data:
                        raise ValueError()
                except (ValueError, TimeoutError):
                    return self.reject(400, 'invalid bounded model request')
                with owner._lock:
                    if len(owner.records) >= owner.max_requests:
                        return self.reject(429, 'task request limit reached')
                    record = dict(index=len(owner.records), model=owner.model,
                                  started_monotonic=time.monotonic(), finished_monotonic=None,
                                  request_sha256=hashlib.sha256(data).hexdigest(),
                                  request_bytes=len(data), response_status=None,
                                  response_bytes=0, response_models=[], error_type=None)
                    owner.records.append(record)
                request = urllib.request.Request(
                    'https://ollama.com/v1/chat/completions', data=data,
                    headers={'Authorization': 'Bearer ' + owner._key,
                             'Content-Type': 'application/json',
                             'Accept': 'text/event-stream'}, method='POST')
                sent_headers = False
                try:
                    with owner._opener(request, timeout=120) as response:
                        record['response_status'] = response.status
                        self.send_response(response.status)
                        self.send_header('Content-Type', response.headers.get('Content-Type', 'text/event-stream'))
                        self.send_header('Connection', 'close')
                        self.end_headers()
                        sent_headers = True
                        pending = b''
                        while True:
                            chunk = response.read1(16384)
                            if not chunk:
                                break
                            record['response_bytes'] += len(chunk)
                            if record['response_bytes'] > 32 << 20:
                                raise RuntimeError('response bound exceeded')
                            pending += chunk
                            while b'\n' in pending:
                                line, pending = pending.split(b'\n', 1)
                                if line.startswith(b'data:'):
                                    try:
                                        item = json.loads(line[5:].strip())
                                    except ValueError:
                                        continue
                                    model = item.get('model') if isinstance(item, dict) else None
                                    if isinstance(model, str) and len(model) <= 200 and model not in record['response_models']:
                                        record['response_models'].append(model)
                            if len(pending) > 1 << 20:
                                raise RuntimeError('SSE line bound exceeded')
                            self.wfile.write(chunk)
                            self.wfile.flush()
                except BaseException as error:
                    record['error_type'] = type(error).__name__
                    if isinstance(error, urllib.error.HTTPError):
                        record['response_status'] = error.code
                    if not sent_headers:
                        try:
                            self.reject(502, 'provider transport failed')
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                finally:
                    record['finished_monotonic'] = time.monotonic()

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f'http://127.0.0.1:{self.server.server_port}/v1'

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self.server = None
        self._key = ''


@contextmanager
def provider_proxy(key, model, max_requests=128):
    proxy = ProviderProxy(key, model, max_requests)
    url = proxy.start()
    try:
        yield proxy, url
    finally:
        proxy.close()

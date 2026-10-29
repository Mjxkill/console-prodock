#!/usr/bin/env python3
"""Offline boundary tests; localhost HTTP uses a fake upstream, never a model.

Changing ceilings must not change timeout, isolation, validation or credentials.
Observed 32-step failures are evidence for a usable ceiling, not activity quotas.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'pack'))
import agent_runner
import agent_backend
from agent_provider import ProviderProxy


class Bounds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'spec.json').write_text('{}')
        self.base = ['--project', str(self.root), '--spec', str(self.root/'spec.json'),
                     '--out', str(self.root/'out'), '--model', 'beam',
                     '--registry', str(self.root/'registry.sqlite')]

    def parse(self, *extra):
        return agent_runner.arguments(self.base+list(extra))

    def refused(self, *extra):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
            self.parse(*extra)
        self.assertEqual(e.exception.code, 2)

    def test_defaults_and_timeout_unchanged(self):
        a=self.parse()
        self.assertEqual((a.max_steps,a.max_requests,a.timeout),(64,128,900))
        self.assertEqual(a.max_output_tokens,65536)

    def test_steps_lower_upper_and_previously_refused(self):
        for n in (1,16,32,33,64,256):
            self.assertEqual(self.parse('--max-steps',str(n)).max_steps,n)
        for n in (0,-1,257,100000): self.refused('--max-steps',str(n))

    def test_requests_lower_upper_and_previous_limit(self):
        for n in (1,48,96,97,128,512):
            self.assertEqual(self.parse('--max-requests',str(n)).max_requests,n)
        for n in (0,-1,513,100000): self.refused('--max-requests',str(n))

    def test_timeout_bounds_unchanged(self):
        for n in (1,900,3600): self.assertEqual(self.parse('--timeout',str(n)).timeout,n)
        for n in (0,3601): self.refused('--timeout',str(n))

    def test_noninteger_cli_refused(self):
        for option in ('--max-steps','--max-requests'):
            for value in ('true','1.5','nan'): self.refused(option,value)

    def test_provider_bounds_and_types(self):
        self.assertEqual(ProviderProxy('dummy-key','beam').max_requests,128)
        for n in (1,96,97,128,512):
            self.assertEqual(ProviderProxy('dummy-key','beam',n).max_requests,n)
        for n in (0,-1,513,True,False,1.5,'512',None):
            with self.assertRaises(ValueError): ProviderProxy('dummy-key','beam',n)

    def test_backend_forwards_selected_limits_and_keeps_isolation_policy(self):
        class Isolation:
            @staticmethod
            def prepare(spec,out): return {'manifest_path':'dummy','paths':[],'tree':str(out)}
            @staticmethod
            def preflight(path): return {'isolation_verified':True}
            @staticmethod
            def mcp_config(path): return {'taskbox':{'type':'local','command':['dummy']}}
        observed=[]
        class Proxy:
            def __init__(self,key,model,limit):
                observed.append(limit);self.token='dummy-local-token'
            def start(self): return 'http://127.0.0.1:1234/v1'
        for n,req in ((64,128),(256,512)):
            out=self.root/('run'+str(n));out.mkdir()
            args=self.parse('--max-steps',str(n),'--max-requests',str(req))
            with patch.object(agent_backend,'dependencies',return_value=(Isolation,None)), \
                 patch.object(agent_backend,'ProviderProxy',Proxy), \
                 patch.object(agent_backend.shutil,'which',return_value='/dummy/opencode'), \
                 patch.object(agent_backend.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='test-version')):
                backend=agent_backend.Backend(args,{},out,'dummy-key')
                backend.preflight({})
            config=json.loads((out/'controller/opencode.json').read_text())
            self.assertEqual(config['agent']['implementer']['steps'],n)
            self.assertEqual(config['permission'],{'*':'deny','taskbox_*':'allow'})
            self.assertEqual(config['agent']['implementer']['permission'],config['permission'])
            self.assertNotIn('dummy-key',json.dumps(config))
        self.assertEqual(observed,[128,512])


class Response(io.BytesIO):
    status=200
    headers={'Content-Type':'text/event-stream'}


class HTTPBoundary(unittest.TestCase):
    def test_512_real_local_requests_then_429_without_upstream_call(self):
        upstream=[]
        def fake(request,timeout):
            upstream.append(request.full_url)
            return Response(b'data: {"model":"beam"}\n\ndata: [DONE]\n\n')
        proxy=ProviderProxy('dummy-key','beam',512,opener=fake)
        url=proxy.start()
        try:
            def send():
                req=urllib.request.Request(url+'/chat/completions',data=b'{"model":"beam"}',
                    headers={'Authorization':'Bearer '+proxy.token})
                with urllib.request.urlopen(req,timeout=3) as response: return response.read()
            for unused in range(512): send()
            with self.assertRaises(urllib.error.HTTPError) as e: send()
            self.assertEqual(e.exception.code,429)
            self.assertEqual(len(upstream),512)
            self.assertEqual(len(proxy.snapshot()),512)
            self.assertNotIn('dummy-key',json.dumps(proxy.snapshot()))
        finally: proxy.close()


if __name__=='__main__': unittest.main(verbosity=2)

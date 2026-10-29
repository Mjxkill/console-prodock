"""Minimal JSON-lines MCP: only scoped files, isolated argv and fixed tests."""
import json
import os
from pathlib import Path
import sys
from agent_box import execute,protect,tests

protect()
POLICY=json.loads(Path('/control/policy.json').read_text())


def path(name,write=False):
    allowed=POLICY['owned'] if write else POLICY['readable']
    if type(name)is not str or name not in allowed:raise ValueError('Path outside explicit task scope')
    value=Path('/work')/name
    if value.is_symlink() or not value.is_file():raise ValueError('Invalid task file')
    return value


TOOLS=[
    dict(name='read_file',description='Read one explicitly scoped text file.',inputSchema={
        'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}),
    dict(name='write_file',description='Write an owned source file in place; paths outside ownership are refused.',inputSchema={
        'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content'],'additionalProperties':False}),
    dict(name='exec',description='Execute argv in offline task sandbox; build temporaries belong in /tmp.',inputSchema={
        'type':'object','properties':{'argv':{'type':'array','items':{'type':'string'}}},'required':['argv'],'additionalProperties':False}),
    dict(name='run_tests',description='Execute the fixed protected acceptance tests and return their actual exit statuses.',
         inputSchema={'type':'object','properties':{},'additionalProperties':False})]


def call(name,args):
    if name=='read_file':return dict(content=path(args['path']).read_text())
    if name=='write_file':
        content=args['content']
        if type(content)is not str or len(content.encode())>1048576:raise ValueError('Oversized content')
        target=path(args['path'],True)
        with target.open('w') as stream:stream.write(content)
        return dict(written_bytes=len(content.encode()))
    if name=='exec':return execute(args['argv'],POLICY['timeout_seconds'])
    if name=='run_tests':return tests(POLICY)
    raise ValueError('Unknown task tool')


for raw in sys.stdin.buffer:
    if len(raw)>2097152:break
    message=None
    try:
        message=json.loads(raw);identity=message.get('id');method=message.get('method')
        if identity is None:continue
        if method=='initialize':
            result=dict(protocolVersion='2024-11-05',capabilities={'tools':{}},
                        serverInfo={'name':'isolated-taskbox','version':'1'})
        elif method=='tools/list':result={'tools':TOOLS}
        elif method=='ping':result={}
        elif method=='tools/call':
            params=message['params'];body=call(params['name'],params.get('arguments',{}))
            result=dict(content=[{'type':'text','text':json.dumps(body,ensure_ascii=False)}],
                        structuredContent=body,isError=False)
        else:raise ValueError('Unsupported MCP method')
        reply=dict(jsonrpc='2.0',id=identity,result=result)
    except Exception as error:
        reply=dict(jsonrpc='2.0',id=message.get('id') if isinstance(message,dict) else None,
                   error={'code':-32603,'message':str(error)})
    print(json.dumps(reply,ensure_ascii=False),flush=True)

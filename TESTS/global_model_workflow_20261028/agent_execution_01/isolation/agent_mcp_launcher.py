#!/usr/bin/env python3
"""Trusted secret-free stdio relay; audit is never mounted in the task sandbox.

Only matched server responses to real run_tests requests count as test events.
Tool stdout is JSON-escaped data and cannot append host journal records.
"""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid
from agent_isolation import command,load


def start_ticks(pid):
    try:return int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19])
    except (OSError,ValueError,IndexError):return None


def response_events(data,name,identity):
    """MCP tool errors may be result.isError, not only JSON-RPC error objects."""
    result=data.get('result')
    error='error' in data or not isinstance(result,dict) or result.get('isError')is True
    events=[dict(event='tool_finish',request_id=identity,name=name,error=error)]
    if name=='run_tests' and not error:
        body=result.get('structuredContent',{})
        for index,item in enumerate(body.get('test_results',[])):
            events.append(dict(event='test_finish',request_id=identity,index=index,
                returncode=item['returncode'],timeout=item['timeout'],
                output_limited=item['output_limited'],elapsed_seconds=item['elapsed_seconds']))
    return events


def main():
    manifest_path=Path(sys.argv[1]);manifest=load(manifest_path)
    journal=Path(manifest['journal_path'])
    if journal.is_symlink() or journal.parent!=manifest_path.parent:
        raise ValueError('Unsafe audit path')
    audit=os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
    launch=uuid.uuid4().hex
    def record(event,**details):
        data=json.dumps(dict(event=event,launch_id=launch,monotonic=time.monotonic(),**details))+'\n'
        os.write(audit,data.encode());os.fsync(audit)
    own_pid=os.getpid();own_ticks=start_ticks(own_pid)
    record('launcher_start',pid=own_pid,start_ticks=own_ticks)
    proc=subprocess.Popen(command(manifest_path,['/usr/bin/python3','-B','/isolation/agent_mcp.py']),
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=sys.stderr,start_new_session=True,
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    sandbox_ticks=start_ticks(proc.pid)
    record('sandbox_start',pid=proc.pid,start_ticks=sandbox_ticks)
    selector=selectors.DefaultSelector();selector.register(sys.stdin.buffer,selectors.EVENT_READ,'input')
    selector.register(proc.stdout,selectors.EVENT_READ,'output')
    buffers={'input':bytearray(),'output':bytearray()};calls={}
    def note(direction,raw):
        try:data=json.loads(raw)
        except ValueError:return
        identity=data.get('id')
        if direction=='input' and data.get('method')=='tools/call':
            name=data.get('params',{}).get('name');calls[identity]=name
            record('tool_start',request_id=identity,name=name)
        elif direction=='output' and identity in calls:
            name=calls.pop(identity)
            for event in response_events(data,name,identity):record(**event)
    def interrupted(*_):raise InterruptedError('MCP relay interrupted')
    previous={sig:signal.signal(sig,interrupted) for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    try:
        while selector.get_map():
            for key,_ in selector.select(.2):
                chunk=os.read(key.fd,8192);direction=key.data
                if not chunk:
                    selector.unregister(key.fileobj)
                    if direction=='input':proc.stdin.close()
                    elif proc.poll() is not None:
                        return proc.returncode
                    continue
                if direction=='input':proc.stdin.write(chunk);proc.stdin.flush()
                else:sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
                buffers[direction].extend(chunk)
                if len(buffers[direction])>2097152:raise ValueError('Oversized MCP line')
                while b'\n' in buffers[direction]:
                    line,_,tail=buffers[direction].partition(b'\n');buffers[direction][:]=tail
                    note(direction,bytes(line))
        return proc.wait(timeout=5)
    finally:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait();record('sandbox_exit',pid=proc.pid,start_ticks=sandbox_ticks,returncode=proc.returncode)
        record('launcher_exit',pid=own_pid,start_ticks=own_ticks)
        selector.close();os.close(audit)
        for sig,handler in previous.items():signal.signal(sig,handler)


if __name__=='__main__':sys.exit(main())

#!/usr/bin/env python3
"""Actual Bubblewrap/MCP adversarial tests; synthetic files, no model or secret key.

Run in an explicitly authorized host context: the outer Codex sandbox can block
Bubblewrap's NETLINK_ROUTE setup. Failure is recorded, never bypassed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
from unittest.mock import patch
import agent_isolation as box
from agent_mcp_launcher import response_events


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    out=args.out.absolute();out.mkdir(parents=True,exist_ok=False)
    project=out/'project';project.mkdir()
    (project/'calc.py').write_text('def add(a, b):\n    return a - b\n')
    (project/'tests.py').write_text('import calc\nassert calc.add(2, 3) == 5\n')
    secret=out/'outside_synthetic_secret.txt';secret.write_text('SYNTHETIC_SECRET_NOT_REAL')
    spec=dict(schema=1,project=str(project),inputs=['calc.py','tests.py'],owned=['calc.py'],
              tests=[['python3','-B','tests.py']],timeout_seconds=2)
    records=[];report={'passed':False,'hardware_access':False,'tests':records}
    process=None;listener=None
    def record(name,**details):records.append(dict(name=name,passed=True,**details))
    try:
        valid={'returncode':0,'timeout':False,'output_limited':False,'elapsed_seconds':.01}
        success={'result':{'isError':False,'structuredContent':{'test_results':[valid]}}}
        assert len(response_events(success,'run_tests',1))==2
        for bad in (
            {'result':{'isError':True,'structuredContent':{'test_results':[valid]}}},
            {'error':{'code':-1},'result':success['result']},
            {'result':[]},
        ):
            events=response_events(bad,'run_tests',1)
            assert len(events)==1 and events[0]['event']=='tool_finish' and events[0]['error']
        record('mcp_iserror_or_rpc_error_never_counts_spurious_successful_tests')
        manifest=box.prepare(spec,out/'task');path=Path(manifest['manifest_path'])
        pre=box.preflight(path);report['preflight']=pre
        assert pre['isolation_verified'],pre
        record('real_namespaces_no_credentials_no_devices_no_network_protected_parent')
        baseline=box.run_tests(path);assert baseline['infrastructure_ok'] and not baseline['passed']
        assert baseline['test_runs']==1 and baseline['test_failures']==1
        record('independent_protected_baseline_fails',returncode=baseline['tests_returncode'])
        cfg=box.mcp_config(path)['taskbox'];stderr=(out/'mcp.stderr').open('wb')
        process=subprocess.Popen(cfg['command'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,
            env={'PATH':'/usr/bin:/bin','OLLAMA_API_KEY':'SYNTHETIC_ENV_KEY','TOKEN':'SYNTHETIC_PROVIDER_TOKEN'})
        serial=0
        def rpc(method,params):
            nonlocal serial
            serial+=1;request=dict(jsonrpc='2.0',id=serial,method=method,params=params)
            process.stdin.write((json.dumps(request)+'\n').encode());process.stdin.flush()
            assert select.select([process.stdout],[],[],10)[0], 'MCP response timeout'
            raw=process.stdout.readline();assert raw, 'MCP exited: '+str(process.poll())
            response=json.loads(raw);assert response['id']==serial
            return response
        def tool(name,arguments):
            response=rpc('tools/call',dict(name=name,arguments=arguments))
            assert 'error' not in response,response
            return response['result']['structuredContent']
        rpc('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1'}})
        assert len(rpc('tools/list',{})['result']['tools'])==4
        first=tool('run_tests',{});assert first['test_runs']==1 and first['test_failures']==1
        record('actual_mcp_test_failure')
        for path_name in ('../outside_synthetic_secret.txt',str(secret),'/proc/1/environ','tests.py'):
            name='write_file' if path_name=='tests.py' else 'read_file'
            arguments={'path':path_name}
            if name=='write_file':arguments['content']='pass'
            assert 'error' in rpc('tools/call',dict(name=name,arguments=arguments))
        record('mcp_scope_and_protected_test_write_refused')
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
        port=listener.getsockname()[1]
        code='''import os,socket,pathlib,errno
assert not os.environ.get('OLLAMA_API_KEY') and not os.environ.get('TOKEN')
assert not pathlib.Path(OUTSIDE).exists()
assert not pathlib.Path('/dev/bus/usb').exists()
for target in [('127.0.0.1',PORT),('192.0.2.1',9)]:
 try: s=socket.create_connection(target,timeout=.2);s.close();raise AssertionError('network escaped')
 except OSError: pass
for action in [lambda:open('/work/tests.py','w'),lambda:open('/work/unowned','w'),
 lambda:os.symlink('/etc/passwd','/work/escape'),lambda:os.open('/proc/1/fd/1',os.O_WRONLY),
 lambda:open('/proc/1/mem','rb')]:
 try: action();raise AssertionError('operation escaped')
 except OSError: pass
print('ISOLATION_OK')
'''.replace('OUTSIDE',repr(str(secret))).replace('PORT',str(port))
        result=tool('exec',{'argv':['python3','-c',code]});assert result['returncode']==0,result
        assert 'ISOLATION_OK' in result['stdout']
        record('arbitrary_child_cannot_read_secret_network_devices_parent_or_modify_context')
        assert not select.select([listener],[],[],0)[0]
        result=tool('exec',{'argv':['python3','-c','import time;time.sleep(5)']})
        assert result['timeout'] and result['returncode']!=0
        record('bounded_child_timeout')
        result=tool('exec',{'argv':['python3','-c','import sys;sys.stdout.write("x"*300000)']})
        assert result['output_limited'] and len(result['stdout'])<=131072
        record('bounded_child_output')
        tool('write_file',dict(path='calc.py',content='def add(a, b):\n    return a + b\n'))
        passed=tool('run_tests',{});assert passed['passed'] and passed['test_runs']==1
        record('mcp_owned_edit_and_tests_really_pass')
        process.stdin.close();assert process.wait(timeout=10)==0
        stderr.close();process=None
        audit=[json.loads(line) for line in Path(manifest['journal_path']).read_text().splitlines()]
        finishes=[line for line in audit if line['event']=='test_finish']
        assert len(finishes)==2 and [x['returncode'] for x in finishes]==[1,0]
        record('host_only_audit_observed_one_failure_one_success')
        final=box.run_tests(path);changes=box.collect_changes(path)
        assert final['passed'] and changes['changed_files']==['calc.py']
        assert changes['originals_unchanged'] and changes['context_unchanged']
        record('independent_final_pass_and_only_owned_diff')
        # A capture policy failure must not pass just because the test exited0.
        fake=subprocess.CompletedProcess([],0,json.dumps({'test_results':[
            {'returncode':0,'timeout':False,'output_limited':True}]}).encode(),b'')
        with patch.object(box,'invoke',return_value=fake):
            limited=box.run_tests(path)
        assert not limited['passed'] and not limited['policy_ok'] and limited['tests_returncode']!=0
        record('exit_zero_with_output_limit_is_not_pass')
        read_only=dict(spec,owned=[],require_changes=False)
        r=box.prepare(read_only,out/'read_only');assert box.preflight(r['manifest_path'])['isolation_verified']
        record('tests_only_no_owned_files_supported')
        (project/'alias.py').symlink_to(secret)
        for inputs in (['../outside_synthetic_secret.txt'],['alias.py'],['.env']):
            try:box.prepare(dict(spec,inputs=inputs),out/'rejected');raise AssertionError('unsafe input accepted')
            except ValueError:pass
        (project/'alias.py').unlink()
        record('prepare_traversal_symlink_secret_name_refused')
        report['passed']=True
    except Exception as error:
        report['error']=repr(error)
        raise
    finally:
        if process is not None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        if listener:listener.close()
        report['inputs']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in Path(__file__).parent.glob('agent_*.py')}
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

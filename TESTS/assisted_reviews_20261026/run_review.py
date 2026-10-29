#!/usr/bin/env python3
"""User-authorized independent reviews via OpenCode/Ollama Cloud or Claude Code.

Only explicit text packets are transmitted. Reviewer tools are disabled; results
are proposals for parent verification, never permission to mutate or program.
Credentials stay in the child environment and are redacted from captured output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SYSTEM = ('You are an independent engineering reviewer helping a real FPGA console project. '
          'Analyze ONLY the supplied packet. No tools, file modifications or hardware actions. '
          'Separate facts, hypotheses and missing evidence. Cite supplied filenames/line numbers. '
          'Do not claim to have executed tests. Prefer concrete minimal patches and discriminating '
          'tests over generic advice. Answer in French. User-facing quality and reproducible proof matter.')


def credential():
    value = os.environ.get('OLLAMA_API_KEY')
    if not value:
        path = Path('/home/michael/.claude/secrets.env')
        for line in path.read_text().splitlines():
            match = re.fullmatch(r'\s*(?:export\s+)?OLLAMA_API_KEY\s*=\s*(.+)', line)
            if match:
                words = shlex.split(match[1], comments=True)
                if len(words) != 1 or '$' in words[0]:
                    raise ValueError('Unsupported credential assignment; no shell evaluation')
                value = words[0]
                break
    if not value:
        raise RuntimeError('OLLAMA_API_KEY missing; no fallback provider')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=('deepseek-v4.1-flash', 'beam', 'minimax-m3.1-flash', 'fable'), required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--focus', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9_]+', args.name):
        raise ValueError('Invalid task name')
    packet = args.packet.resolve()
    if not packet.is_relative_to(ROOT) or packet.suffix != '.txt':
        raise ValueError('Only prepared repository text packets are allowed')
    source = packet.read_text()
    if len(source.encode()) > 200_000:
        raise ValueError('Packet too large; curate the evidence')
    out = HERE / args.name
    out.mkdir()
    prompt = SYSTEM + '\n\nTASK FOCUS:\n' + args.focus + '\n\nEVIDENCE PACKET:\n' + source
    (out / 'prompt.txt').write_text(prompt)
    report = dict(model=args.model, tool='claude-code' if args.model == 'fable' else 'opencode',
                  packet=str(packet.relative_to(ROOT)),
                  packet_sha256=hashlib.sha256(packet.read_bytes()).hexdigest(),
                  focus=args.focus, started_unix=time.time(), status='STARTING',
                  validation='Independent proposal only; parent code/test verification required')

    def save():
        (out / 'status.json').write_text(json.dumps(report, indent=2) + '\n')

    env = os.environ.copy()
    key = None
    work = Path('/tmp/console-assisted-reviews-20261026') / args.name
    work.mkdir(parents=True)
    if args.model == 'fable':
        cmd = ['/home/michael/.local/bin/claude', '--safe-mode', '--model', 'fable',
               '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
               '--no-session-persistence', '--output-format', 'json', '--print']
    else:
        key = credential()
        env['OLLAMA_API_KEY'] = key
        for suffix in ('CONFIG', 'DATA', 'CACHE', 'STATE'):
            d = work / ('xdg_' + suffix.lower())
            d.mkdir()
            env['XDG_' + suffix + '_HOME'] = str(d)
        config = dict(
            enabled_providers=['console-ollama-cloud'],
            autoupdate=False, snapshot=False, share='disabled',
            permission={'*': 'deny'},
            agent={'reviewer': dict(mode='primary', description='Text packet review only',
                                   prompt=SYSTEM, permission={'*': 'deny'})},
            provider={'console-ollama-cloud': dict(
                npm='@ai-sdk/openai-compatible', name='Ollama Cloud explicit user models',
                options=dict(baseURL='https://ollama.com/v1', apiKey='{env:OLLAMA_API_KEY}'),
                models={
                    'deepseek-v4.1-flash': dict(name='deepseek-v4.1-flash', reasoning=True,
                        interleaved={'field': 'reasoning_content'},
                        limit={'context': 1048576, 'output': 131072},
                        options={'reasoningEffort': 'low'}),
                    'beam': dict(name='beam'),
                    'minimax-m3.1-flash': dict(name='minimax-m3.1-flash')})})
        (out / 'opencode.json').write_text(json.dumps(config, indent=2) + '\n')
        env['OPENCODE_CONFIG'] = str(out / 'opencode.json')
        env['OPENCODE_DISABLE_PROJECT_CONFIG'] = 'true'
        env['OPENCODE_DISABLE_CLAUDE_CODE'] = 'true'
        # OpenCode 1.x otherwise clamps an explicit model output limit at 32000.
        # See anomalyco/opencode#29363. Keep this override local to our child.
        if args.model == 'deepseek-v4.1-flash':
            env['OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX'] = '131072'
            report['opencode_output_cap_override'] = 131072
        cmd = ['/home/michael/.npm-global/bin/opencode', 'run', '--pure',
               '--model', 'console-ollama-cloud/' + args.model, '--agent', 'reviewer',
               '--format', 'json', '--title', args.name, '--dir', str(work)]
    save()
    child = subprocess.Popen(cmd, cwd=work, env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    report.update(status='RUNNING', pid=child.pid)
    save()
    print(json.dumps(dict(name=args.name, model=args.model, pid=child.pid, status='RUNNING')), flush=True)

    def interrupt(sig, frame):
        raise KeyboardInterrupt('Signal ' + str(sig))

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupt)
    try:
        stdout, stderr = child.communicate(prompt, timeout=1800)
        if key:
            stdout, stderr = stdout.replace(key, '[REDACTED]'), stderr.replace(key, '[REDACTED]')
        (out / 'events.jsonl').write_text(stdout)
        (out / 'stderr.txt').write_text(stderr)
        responses, errors, finishes = [], [], []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if args.model == 'fable' and event.get('type') == 'result':
                responses.append(event.get('result', ''))
                if event.get('is_error'):
                    errors.append(event.get('result', 'Claude result error'))
                report['usage'] = event.get('usage')
                report['model_usage'] = event.get('modelUsage')
            elif event.get('type') == 'text':
                responses.append(event.get('part', {}).get('text', ''))
            elif event.get('type') == 'error':
                errors.append(event.get('error', 'OpenCode error'))
            elif event.get('type') == 'step_finish':
                finishes.append(event.get('part', {}))
        answer = '\n\n'.join(r for r in responses if r)
        (out / 'answer.txt').write_text(answer)
        truncated = any(p.get('reason') == 'length' for p in finishes)
        report.update(returncode=child.returncode, errors=errors, answer_chars=len(answer), finishes=finishes,
                      status=('INCOMPLETE_LENGTH' if truncated else
                              'COMPLETED_REVIEW_PENDING_VALIDATION' if child.returncode == 0 and answer and not errors else 'FAILED'))
    except BaseException as exc:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.communicate()
        report.update(status='FAILED', error=type(exc).__name__)
        raise
    finally:
        report['finished_unix'] = time.time()
        save()
        print(json.dumps(dict(name=args.name, model=args.model, status=report['status'],
                              answer_chars=report.get('answer_chars', 0))), flush=True)


if __name__ == '__main__':
    main()

"""Account actual OpenCode JSONL steps/tools without equating them to tasks.

HTTP attempts come from the separate provider gateway. Tool completion is a
real emitted event, but does not establish correctness of a resulting edit.
"""
import json


def parse(raw, expected_session=None):
    errors, starts, finishes, tools, texts = [], {}, {}, {}, {}
    sessions = set()
    part_values = {}
    last_reason = None
    for index, line in enumerate(raw.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError()
        except ValueError:
            errors.append(f'line{index}:invalid_json')
            continue
        kind = event.get('type')
        sid = event.get('sessionID')
        if not isinstance(sid, str) or not sid.startswith('ses_'):
            errors.append(f'line{index}:missing_session')
            continue
        sessions.add(sid)
        if expected_session is not None and sid != expected_session:
            errors.append(f'line{index}:wrong_session')
        if kind == 'error':
            errors.append(f'line{index}:provider_error')
            continue
        part = event.get('part')
        if not isinstance(part, dict):
            errors.append(f'line{index}:missing_part')
            continue
        if part.get('sessionID') != sid:
            errors.append(f'line{index}:part_session_mismatch')
        pid, message = part.get('id'), part.get('messageID')
        if not isinstance(pid, str) or not isinstance(message, str):
            errors.append(f'line{index}:missing_identity')
            continue
        identity = (kind, pid)
        previous = part_values.get(identity)
        # Terminal CLI tool events normally appear once. Updates before the
        # terminal state are allowed and counted as one invocation below.
        if previous == part:
            continue
        if previous is not None and kind != 'tool_use':
            errors.append(f'line{index}:conflicting_duplicate_part')
            continue
        part_values[identity] = part
        if kind == 'step_start':
            starts[pid] = message
        elif kind == 'step_finish':
            reason = part.get('reason')
            finishes[pid] = dict(message_id=message, reason=reason,
                                 tokens=part.get('tokens'), cost=part.get('cost'))
            last_reason = reason
            if reason == 'length':
                errors.append(f'line{index}:length_limit')
        elif kind == 'text':
            if not isinstance(part.get('text'), str):
                errors.append(f'line{index}:invalid_text')
            else:
                texts[pid] = part['text']
        elif kind == 'tool_use':
            call_id, name, state = part.get('callID'), part.get('tool'), part.get('state')
            if not isinstance(call_id, str) or not isinstance(name, str) or not isinstance(state, dict):
                errors.append(f'line{index}:malformed_tool')
                continue
            status = state.get('status')
            if status not in ('pending', 'running', 'completed', 'error'):
                errors.append(f'line{index}:unknown_tool_status')
            old = tools.get(call_id)
            if old and (old['name'] != name or old['message_id'] != message or
                        old['status'] in ('completed', 'error')):
                errors.append(f'line{index}:conflicting_tool_identity_or_terminal')
                continue
            metadata = state.get('metadata')
            metadata = metadata if isinstance(metadata, dict) else {}
            tools[call_id] = dict(call_id=call_id, name=name, message_id=message,
                                  status=status, exit_code=metadata.get('exit'),
                                  input=state.get('input'), output=state.get('output'),
                                  time=state.get('time'))
        # Reasoning or provider-specific extra events are retained in raw log;
        # they do not silently increment model requests or tool invocations.
    if len(sessions) != 1:
        errors.append('expected_one_session')
    start_messages = list(starts.values())
    finish_messages = [item['message_id'] for item in finishes.values()]
    if sorted(start_messages) != sorted(finish_messages) or not starts:
        errors.append('unmatched_model_steps')
    for tool in tools.values():
        if tool['message_id'] not in start_messages:
            errors.append('tool_without_observed_model_step')
        if tool['status'] not in ('completed', 'error'):
            errors.append('unfinished_tool')
    if last_reason != 'stop':
        errors.append('missing_final_stop')
    # A tool returning a failure is evidence for the model to repair; it is
    # not itself a protocol failure. Final independent tests decide success.
    return dict(session_id=next(iter(sessions)) if len(sessions) == 1 else None,
                complete=not errors, errors=errors,
                model_steps_started=len(starts), model_steps_finished=len(finishes),
                tool_invocations_observed=len(tools), tools=list(tools.values()),
                finishes=list(finishes.values()), answer='\n'.join(texts.values()),
                api_requests_observed=None,
                note='API attempts are measured separately by the provider gateway')

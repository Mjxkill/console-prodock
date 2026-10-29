#!/usr/bin/env python3
"""Read account usage, without generation or retaining credentials/identity.

Uses the same credential resolution as the OpenCode runner. Only counters and
time/model labels are retained; this is not a model inference client.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import credential


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward the authorization header to a different endpoint."""

    def redirect_request(self, *args, **kwargs):
        return None


ALLOWED = {
    'range', 'scope', 'granularity', 'group_by', 'from', 'until', 'totals',
    'buckets', 'groups', 'remainder', 'model', 'name', 'request_count',
    'input_tokens', 'output_tokens', 'cached_input_tokens', 'usage_usd',
    'partial', 'limits', 'session', 'weekly', 'models', 'usage', 'activity',
    'period', 'type', 'cost', 'inference', 'web_search', 'web_fetch',
    'requests', 'tokens', 'input', 'output', 'cached', 'reset_at', 'resets_at',
    'start', 'end', 'total', 'usage_unit', 'unit', 'count', 'value',
}


def filtered(value):
    if isinstance(value, dict):
        return {k: filtered(v) for k, v in value.items() if k in ALLOWED}
    if isinstance(value, list):
        return [filtered(v) for v in value]
    return value


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--credential-file', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit('Output already exists')
    key = credential(args)
    url = 'https://ollama.com/api/usage?range=24h&scope=self&group_by=model'
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + key})
    result = {'url': url, 'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=25) as response:
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise ValueError('Response size limit')
            data = json.loads(body)
            result.update(status=response.status, response_sha256=hashlib.sha256(body).hexdigest(),
                          top_level_fields=sorted(data), counters=filtered(data))
    except Exception as error:
        result.update(error_type=type(error).__name__, http_status=getattr(error, 'code', None))
    serialized = json.dumps(result, indent=2)
    if key in serialized:
        raise SystemExit('Unexpected credential in response; nothing retained')
    args.out.write_text(serialized + '\n')
    print(serialized)
    return 0 if result.get('status') == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())

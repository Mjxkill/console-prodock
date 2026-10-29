"""Export a self-contained interactive report; no server or CDN needed."""
import copy
import json
from pathlib import Path


def export(result, destination):
    compact = copy.deepcopy(result)
    for build in compact['builds']:
        build['reported_path_count'] = len(build['paths'])
        # Keep all failures plus up to 40 positive paths; full data is in JSON.
        build['paths'] = [p for p in build['paths'] if p.get('slack_ns') is not None and p['slack_ns'] < 0] + [
            p for p in build['paths'] if p.get('slack_ns') is None or p['slack_ns'] >= 0][:40]
    data = json.dumps(compact, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    template = (Path(__file__).parent/'dashboard.html').read_text()
    Path(destination).write_text(template.replace('/*__DATA__*/null', data))

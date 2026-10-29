#!/usr/bin/env python3
"""Static validation against installed source snapshots; never submits jobs."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT/"manifest.json").read_text())
    sources = ROOT.parent/"art/provenance"
    observed_inputs = {}
    for filename in ("installed_nodes_yue2.py", "installed_nodes_audio.py"):
        tree = ast.parse((sources/filename).read_text())
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for definition in ast.walk(node):
                    if isinstance(definition, ast.keyword) and definition.arg == "inputs" and isinstance(definition.value, ast.List):
                        observed_inputs[node.name] = {call.args[0].value for call in definition.value.elts
                            if isinstance(call, ast.Call) and call.args and isinstance(call.args[0], ast.Constant)}
    blueprint = json.loads((sources/"yue2_blueprint.json").read_text())
    active_path = ROOT/"provenance/active_nodes.json"
    active = json.loads(active_path.read_text()) if active_path.exists() else None
    known = {}
    for subgraph in blueprint["definitions"]["subgraphs"]:
        for node in subgraph["nodes"]:
            known[node["type"]] = {i["name"] for i in node.get("inputs", [])}
    known.update(observed_inputs)
    checks = []
    ids = [c["id"] for c in manifest["cues"]]
    assert len(ids) == len(set(ids)), "duplicate cue id"
    assert len(manifest["cues"]) == 25
    for world in range(6):
        cues = [c for c in manifest["cues"] if c["world"] == world]
        assert len([c for c in cues if c["state"] == "explore"]) == 2
        assert any(c["state"] == "mystery" for c in cues)
    checks.append("six worlds have two exploration variants and mystery")
    for path in sorted((ROOT/"workflows").glob("*.json")):
        graph = json.loads(path.read_text())
        assert graph["1"]["inputs"]["ckpt_name"] == manifest["model"]
        assert graph["2"]["class_type"] == "YuE2GenerateMusic"
        assert graph["2"]["inputs"]["lyrics"] == ""
        assert graph["4"]["inputs"]["seconds"] == ["2", 1], "latent must follow actual generated duration"
        assert graph["5"]["inputs"]["negative"] == ["3", 0]
        assert graph["3"]["class_type"] == "ConditioningZeroOut"
        for node in graph.values():
            assert node["class_type"] in known, node["class_type"]
            assert set(node["inputs"]) <= known[node["class_type"]], node["class_type"]
            for value in node["inputs"].values():
                if isinstance(value, list):
                    assert len(value) == 2 and value[0] in graph and isinstance(value[1], int)
            if active:
                schema = active["nodes"][node["class_type"]]
                required = schema["input"].get("required", {})
                allowed = dict(required, **schema["input"].get("optional", {}))
                assert set(required) <= set(node["inputs"]), node["class_type"] + ": missing required input"
                assert set(node["inputs"]) <= set(allowed), node["class_type"] + ": unknown input"
                for name, value in node["inputs"].items():
                    spec = allowed[name]
                    kind = spec[0]
                    options = spec[1] if len(spec) > 1 else {}
                    if isinstance(value, list):
                        source = graph[value[0]]["class_type"]
                        assert active["nodes"][source]["output"][value[1]] == kind, name + ": incompatible link"
                    elif isinstance(kind, list):
                        assert value in kind, name + ": invalid choice"
                    elif kind == "COMBO":
                        assert value in options["options"], name + ": invalid combo"
                    elif kind in ("FLOAT", "INT"):
                        assert isinstance(value, (int, float)), name
                        assert options.get("min", value) <= value <= options.get("max", value), name + ": range"
                    elif kind == "STRING":
                        assert isinstance(value, str), name
        checks.append(path.name + ": installed-node inputs and duration link PASS")
    for path, expected in manifest["provenance_sources"].items():
        assert hashlib.sha256((ROOT.parent/path).read_bytes()).hexdigest() == expected, path
    for cue in manifest["cues"]:
        attempts = [a["cue_snapshot"] for a in cue.get("render_attempts", [])]
        if cue["status"] in ("generated", "ready"):
            attempts.append(cue)
        for attempt in attempts:
            qa = json.loads((ROOT.parent/attempt["qa_file"]).read_text())
            provenance = attempt["render_provenance"]
            for file, digest in ((qa["native_file"], provenance["source_sha256"]),
                                 (qa["history_file"], provenance["history_sha256"]),
                                 (attempt["workflow"], provenance["workflow_sha256"])):
                assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest() == digest, file
            if attempt.get("file"):
                assert hashlib.sha256((ROOT.parent/attempt["file"]).read_bytes()).hexdigest() == attempt["sha256"]
            checks.append(attempt["id"] + ": retained audio/history/workflow SHA PASS; waveform " + qa["waveform_qa"])
        if cue["status"] == "ready":
            assert cue["file"] and cue["audition"] == "approved"
            path = ROOT.parent/cue["file"]
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == cue["sha256"]
            qa = json.loads((ROOT.parent/cue["qa_file"]).read_text())
            assert qa["waveform_qa"] == "PASS" and qa["sha256"] == cue["sha256"]
            assert cue["render_provenance"]["model_sha256"] == manifest["model_sha256"]
            assert manifest["model_sha256"], "ready cue requires model fingerprint"
    for pilot in manifest["pilots"]:
        if pilot.get("status") == "generated":
            qa = json.loads((ROOT/pilot["qa_file"]).read_text())
            for file, digest in ((pilot["native_file"], pilot["source_sha256"]),
                                 (pilot["preview_file"], qa["pcm_preview_sha256"]),
                                 (pilot["loop_preview_file"], qa["loop_preview_qa"]["sha256"]),
                                 (qa["history_file"], qa["history_sha256"]),
                                 (pilot["file"], qa["workflow_sha256"])):
                assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest() == digest, file
            checks.append(pilot["id"] + ": native/PCM/loop/workflow/history SHA PASS; audition " + pilot["audition"])
    result = {"status": "PASS", "scope": "local graph/source/manifest validation, not GPU execution or listening",
              "checks": checks, "ready_cues": sum(c["status"] == "ready" for c in manifest["cues"]),
              "generated_pilots": sum(p.get("status") == "generated" for p in manifest["pilots"]),
              "generated_cues": sum(c["status"] == "generated" for c in manifest["cues"]),
              "graph_count": len(list((ROOT/"workflows").glob("*.json"))),
              "active_server_schema": active["server"] if active else None,
              "manifest_sha256": hashlib.sha256((ROOT/"manifest.json").read_bytes()).hexdigest()}
    out = ROOT/"qa/static_validation.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Import finished regional renders from the art agent's local staging directory."""
import json
from pathlib import Path
import shutil

import audio_tools as audio
import review_pilot

ROOT = audio.ROOT
REGIONS = ("aube_explore", "canopee_explore", "marees_explore", "cuivre_explore", "nuages_explore", "racines_explore")


def main():
    outcomes = []
    for cue_id in REGIONS:
        manifest = json.loads((ROOT/"manifest.json").read_text())
        cue = next(c for c in manifest["cues"] if c["id"] == cue_id)
        if cue["status"] in ("generated", "ready"):
            continue
        generation_id = cue.get("generation_id", cue_id)
        staging = ROOT.parent/"art/music_staging"/generation_id
        submission_path = staging/"submission.json"
        if not submission_path.exists():
            continue
        submission = json.loads(submission_path.read_text())
        if submission.get("status") != "generated":
            continue
        if submission["workflow_sha256"] != audio.sha(ROOT/cue["workflow"]):
            raise ValueError(cue_id + ": submitted workflow differs from retained workflow")
        outputs = [f for f in submission["files"] if f.get("kind") == "audio"]
        if len(outputs) != 1:
            raise ValueError(cue_id + ": expected exactly one native audio output")
        source = staging/outputs[0]["file"]
        if audio.sha(source) != outputs[0]["sha256"]:
            raise ValueError(cue_id + ": native output fingerprint mismatch")
        report = audio.prepare(source, cue_id, .125, 0, None, staging/"history.json")
        retained_submission = ROOT/"provenance"/(generation_id + "_submission.json")
        if retained_submission.exists():
            raise ValueError("Submission already retained: " + cue_id)
        shutil.copyfile(submission_path, retained_submission)
        outcomes.append({"cue": cue_id, "seconds": report["duration_seconds"],
                         "peak_dbfs": report["peak_dbfs"], "waveform_qa": report["waveform_qa"],
                         "issues": report["issues"], "audition": "pending"})
    manifest = json.loads((ROOT/"manifest.json").read_text())
    completed = [c["id"] for c in manifest["cues"] if c["id"] in REGIONS and c["status"] == "generated"]
    manifest["generation"]["regions_generated"] = completed
    manifest["generation"]["status"] = "six_regions_generated_audition_pending" if len(completed) == 6 else "regional_generation_in_progress"
    manifest["generation"].pop("active_prompt_id", None)
    (ROOT/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    review_pilot.page(manifest)
    print(json.dumps({"imported": outcomes, "generated_regions": len(completed), "ready_cues": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

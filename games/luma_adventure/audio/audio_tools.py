#!/usr/bin/env python3
"""Inspect/prepare YuE2 renders with stdlib and installed ffmpeg. No generation."""
from __future__ import annotations
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parent
RATE = 48000


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def confined(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Output must remain in {ROOT}")
    return path


def validate_history(path: Path, graph: dict, source_basename: str) -> dict:
    """Bind the downloaded native filename to a successful, exact GPU prompt."""
    data = json.loads(path.read_text())
    if "prompt" in data:
        record = data
    else:
        records = [r for r in data.values() if isinstance(r, dict) and "prompt" in r]
        if len(records) != 1:
            raise ValueError("Expected history containing exactly one prompt")
        record = records[0]
    actual_graph = record["prompt"][2]
    for node_id, node in graph.items():
        actual = actual_graph.get(node_id, {})
        if actual.get("class_type") != node["class_type"] or actual.get("inputs") != node["inputs"]:
            raise ValueError(f"History differs from pilot/cue workflow at node {node_id}")
    if not record.get("status", {}).get("completed") or record["status"].get("status_str") != "success":
        raise ValueError("ComfyUI history does not report successful completion")
    outputs = record.get("outputs", {}).get("7", {}).get("audio", [])
    if source_basename not in {output.get("filename") for output in outputs}:
        raise ValueError("Keep the original ComfyUI output basename: source is not listed by SaveAudio history")
    return record


def decode(path: Path) -> tuple[array, dict]:
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
                           check=True, capture_output=True, text=True)
    streams = json.loads(probe.stdout)["streams"]
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise ValueError("No audio stream")
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
                              "-ac", "2", "-ar", str(RATE), "-f", "f32le", "pipe:1"],
                             check=True, capture_output=True)
    samples = array("f")
    samples.frombytes(decoded.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples, {"source_sample_rate": int(audio["sample_rate"]),
                     "source_channels": audio["channels"], "source_codec": audio["codec_name"],
                     "source_sample_format": audio.get("sample_fmt"), "sha256": sha(path)}


def measure(samples: array, rate: int = RATE) -> dict:
    if not samples or len(samples) % 2:
        raise ValueError("Empty or unaligned stereo PCM")
    if any(not math.isfinite(v) for v in samples):
        raise ValueError("Non-finite audio samples")
    frames = len(samples) // 2
    peaks = [max(abs(v) for v in samples[c::2]) for c in range(2)]
    rms = [math.sqrt(sum(v*v for v in samples[c::2]) / frames) for c in range(2)]
    window = max(1, rate // 100)
    silent_windows = 0
    window_count = 0
    for start in range(0, len(samples), window * 2):
        part = samples[start:start + window * 2]
        silent_windows += math.sqrt(sum(v*v for v in part) / len(part)) < 0.001
        window_count += 1
    adjacent_energy = sum((samples[i] - samples[i-2])**2 for i in range(2, len(samples)))
    delta_rms = math.sqrt(adjacent_energy / max(1, len(samples)-2))
    seam = max(abs(samples[c] - samples[-2+c]) for c in range(2))
    return {"duration_seconds": round(frames/rate, 6), "sample_rate": rate,
            "channels": 2, "frames": frames, "peak_linear": max(peaks),
            "peak_dbfs": round(20*math.log10(max(max(peaks), 1e-12)), 3),
            "channel_rms_dbfs": [round(20*math.log10(max(r, 1e-12)), 3) for r in rms],
            "clipped_samples": sum(abs(v) >= 32767/32768 for v in samples),
            "silent_window_fraction": round(silent_windows / window_count, 6),
            "dc_offset": [sum(samples[c::2])/frames for c in range(2)],
            "loop_seam_step": seam, "adjacent_step_rms": delta_rms,
            "loop_seam_to_step_rms": seam / max(delta_rms, 1e-9)}


def technical_issues(report: dict, loop: bool = False) -> list[str]:
    issues = []
    if report["duration_seconds"] < 2:
        issues.append("too_short")
    if max(report["channel_rms_dbfs"]) < -50:
        issues.append("silent_or_near_silent")
    if min(report["channel_rms_dbfs"]) < -60:
        issues.append("silent_channel")
    if report["clipped_samples"]:
        issues.append("clipped_samples")
    if report["silent_window_fraction"] > 0.35:
        issues.append("excess_silence")
    if max(abs(v) for v in report["dc_offset"]) > 0.02:
        issues.append("dc_offset")
    if loop and report["loop_seam_to_step_rms"] > 8 and report["loop_seam_step"] > 0.02:
        issues.append("loop_seam_outlier")
    return issues


def loop_crossfade(samples: array, fade_frames: int) -> array:
    """Overlap last/first segment; join at an original adjacent sample pair."""
    frames = len(samples) // 2
    if fade_frames < 2 or fade_frames * 3 >= frames:
        raise ValueError("Crossfade must fit at least three times in source")
    head = array("f")
    for i in range(fade_frames):
        t = i / (fade_frames - 1)
        a, b = math.cos(t*math.pi/2), math.sin(t*math.pi/2)
        for channel in range(2):
            head.append(samples[(frames-fade_frames+i)*2+channel]*a + samples[i*2+channel]*b)
    head.extend(samples[fade_frames*2:(frames-fade_frames)*2])
    return head


def prepare(source: Path, cue_id: str, fade: float, start: float, end: float | None, history: Path) -> dict:
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    cue = next((c for c in manifest["cues"] if c["id"] == cue_id), None)
    if cue is None:
        raise ValueError("Unknown cue id; pilots are for QA, not published tracks")
    graph = json.loads((ROOT/cue["workflow"]).read_text())
    record = validate_history(history, graph, source.name)
    target = confined(ROOT / "renders" / (cue_id + ".wav"))
    if target.exists():
        raise ValueError("Render already exists; keep prior output and use a new cue revision")
    generation_id = cue.get("generation_id", cue_id)
    native = ROOT/"renders/raw"/generation_id/source.name
    retained_history = ROOT/"provenance"/(generation_id + "_history.json")
    for input_path, retained_path in ((source, native), (history, retained_history)):
        retained_path.parent.mkdir(parents=True, exist_ok=True)
        if input_path.resolve() != retained_path.resolve():
            if retained_path.exists():
                raise ValueError(f"Will not overwrite provenance {retained_path}")
            shutil.copyfile(input_path, retained_path)
    samples, provenance = decode(source)
    original = measure(samples)
    original["issues"] = technical_issues(original)
    qa_path = ROOT / "qa" / (generation_id + ".json")
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    render_provenance = {"source_sha256": provenance["sha256"], "prompt_id": record["prompt"][1],
                         "history_sha256": sha(retained_history), "model_sha256": manifest.get("model_sha256"),
                         "workflow_sha256": sha(ROOT/cue["workflow"])}
    common = dict(source=str(source), source_metadata=provenance, cue_id=cue_id,
                  prompt_id=record["prompt"][1], native_file=str(native.relative_to(ROOT)),
                  history_file=str(retained_history.relative_to(ROOT)), history_sha256=sha(retained_history),
                  model_sha256=manifest.get("model_sha256"),
                  audition="pending: musical quality, no vocals, seam harmony and tempo require listening")
    if original["issues"]:
        result = dict(original, **common, sha256=provenance["sha256"], waveform_qa="FAIL", pcm_exported=False)
        qa_path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
        cue.update(file=None, status="generated", sha256=None, waveform_qa="FAIL",
                   generated_seconds=original["duration_seconds"], qa_file="audio/"+str(qa_path.relative_to(ROOT)),
                   render_provenance=render_provenance)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
        return result
    end_frame = round(end*RATE) if end is not None else len(samples)//2
    start_frame = round(start*RATE)
    if not 0 <= start_frame < end_frame <= len(samples)//2:
        raise ValueError("Invalid trim interval")
    samples = samples[start_frame*2:end_frame*2]
    if cue["loop"]:
        samples = loop_crossfade(samples, round(fade*RATE))
    else:
        # Short envelopes prevent clicks on the exported one-shot boundaries.
        envelope_frames = min(round(0.01*RATE), len(samples)//4)
        for i in range(envelope_frames):
            gain = i/max(1, envelope_frames-1)
            for channel in range(2):
                samples[i*2+channel] *= gain
                samples[len(samples)-2-i*2+channel] *= gain
    # Attenuation only; do not disguise a low-level failed generation by boosting it.
    peak = max(abs(v) for v in samples)
    gain = min(1, 10**(-2/20)/max(peak, 1e-12))
    pcm = array("h", (round(max(-1, min(1, v*gain))*32767) for v in samples))
    if sys.byteorder != "little":
        pcm.byteswap()
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as output:
        output.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
        output.writeframes(pcm.tobytes())
    decoded, output_provenance = decode(target)
    result = measure(decoded)
    result["issues"] = technical_issues(result, loop=cue["loop"])
    result.update(**common, source_qa=original,
                  sha256=output_provenance["sha256"], pcm_exported=True,
                  waveform_qa="FAIL" if result["issues"] else "PASS",
                  warnings=["render shorter than 75% of requested duration"] if original["duration_seconds"] < cue["requested_seconds"]*.75 else [],
                  transform={"trim_start_frame": start_frame, "trim_end_frame": end_frame,
                             "crossfade_frames": round(fade*RATE) if cue["loop"] else 0,
                             "attenuation_gain": gain, "tool_sha256": sha(Path(__file__))})
    qa_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    cue.update(file="audio/" + str(target.relative_to(ROOT)), status="generated",
               waveform_qa=result["waveform_qa"],
               sha256=result["sha256"], generated_seconds=result["duration_seconds"],
               loop_end_frame=result["frames"], qa_file="audio/" + str(qa_path.relative_to(ROOT)),
               render_provenance=render_provenance)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("source", type=Path)
    inspect.add_argument("--loop", action="store_true")
    inspect.add_argument("--out", type=Path)
    prep = commands.add_parser("prepare")
    prep.add_argument("source", type=Path)
    prep.add_argument("--cue", required=True)
    prep.add_argument("--history", required=True, type=Path)
    prep.add_argument("--crossfade", type=float, default=0.125)
    prep.add_argument("--start", type=float, default=0)
    prep.add_argument("--end", type=float)
    args = parser.parse_args()
    if args.command == "inspect":
        samples, metadata = decode(args.source)
        result = measure(samples)
        result.update(metadata)
        result["issues"] = technical_issues(result, args.loop)
        result["waveform_qa"] = "FAIL" if result["issues"] else "PASS"
        if args.out:
            target = confined(args.out)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, indent=2) + "\n")
    else:
        result = prepare(args.source, args.cue, args.crossfade, args.start, args.end, args.history)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

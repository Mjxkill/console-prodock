#!/usr/bin/env python3
"""Prepare reproducible YuE2 API graphs locally. Never contacts ComfyUI/GPU."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKPOINT = "yue2_3b_int8_convrot.safetensors"
COMMON = (
    "Original instrumental fantasy adventure game soundtrack, intimate acoustic ensemble, "
    "warm living world, tender curiosity and ancient mystery, expressive human phrasing, "
    "organic room acoustics, clear melody with space between phrases, restrained dynamics, "
    "no vocals, no singing, no speech, no choir, no cinematic trailer hits. "
)
REGIONS = [
    ("aube", "Le Val des Lanternes", 84, "D", "wooden flute, plucked nylon strings, felt piano, brushed frame drum, lantern-lit grasslands, hopeful open fifths, unhurried walking rhythm"),
    ("canopee", "La Canopée de Verre", 76, "Ddor", "breathy alto flute, delicate glass chimes, marimba, pizzicato strings, dew on translucent leaves, curious descending replies, quiet woodland mystery"),
    ("marees", "L'Archipel des Marées", 72, "G", "soft clarinet, nylon guitar, mellow vibraphone, muted hand percussion, tidal islands, gently rocking phrases, horizon and salt air"),
    ("cuivre", "Les Ateliers du Soleil", 108, "Dmix", "muted brass, hammered dulcimer, warm upright bass, small wooden percussion, cheerful copper workshops, playful interlocking mechanical rhythms"),
    ("nuages", "La Mer des Nuages", 92, "D", "soaring flute, transparent string harmonics, harp arpeggios, soft French horn, vast cloud ocean, weightless rising phrases, wonder with no bombast"),
    ("racines", "Le Jardin des Retours", 68, "D", "felt piano, cello, low wooden flute and distant glass chimes, garden of remembered journeys, peaceful bittersweet homecoming, motifs answering each other"),
]
EXTRA = [
    ("village", "Les maisons qui veillent", 96, "G", 48, True, "nylon guitar, wooden flute, pizzicato bass, brushed tambourine, friendly village conversations, gentle circular dance, quiet and welcoming"),
    ("combat", "Les sentiers se défendent", 132, "Ddor", 48, True, "agile chamber strings, low marimba, dry frame drums, determined short flute motif, playful heroic skirmish, readable pulse, controlled tension"),
    ("boss", "Le gardien du souvenir", 120, "Ddor", 64, True, "low strings, resonant bronze percussion, muted horns, measured powerful frame drums, ancient guardian, awe and resolve, transformed adventure motif, clear four-bar phrases"),
    ("travel_ground", "La poussière et les étoiles", 112, "Dmix", 48, True, "nimble plucked strings, fiddle, woody percussion, hand-played galloping pulse, joyful horseback and wheeled travel, forward motion, countryside air"),
    ("travel_air", "Plus haut que les ponts", 100, "D", 64, True, "harp, wide soft strings, lyrical horn and flute, glider and small airplane above sunlit clouds, long rising phrases, buoyant adventurous freedom"),
    ("victory", "Les jardins se souviennent", 84, "D", 36, False, "flute and cello in warm dialogue, harp, gentle strings, resolved homecoming, original adventure melody returns quietly, intimate celebratory ending, natural final decay"),
    ("discovery", "Une lumière sous la pierre", 80, "D", 12, False, "brief delicate celesta and plucked strings phrase, magical discovery, rising four-note motif, tender surprise, short resolved cadence and clean natural decay"),
]


def score(tempo: int, key: str, title: str) -> str:
    """Original eight-bar leitmotif; pitches are a request, not a proven render."""
    header = f"X:1\nT:{title}\nM:4/4\nL:1/8\nQ:1/4={tempo}\nK:{key}\n"
    if key == "G":
        return (header + '"G"G2 d2 e2 g2 | "C"e3 d c2 A2 | "G"B2 d2 g3 d | "D"A4 z4 |\n'
                '"Em"e2 g2 a2 g2 | "C"e3 d c2 A2 | "D"B2 A2 G2 A2 | "G"G6 z2 |]\n')
    tonic = "Dm" if key == "Ddor" else "D"
    dominant = "Am" if key in ("Ddor", "Dmix") else "A"
    sixth = "Bdim" if key == "Ddor" else "Bm"
    return (header + f'"{tonic}"D2 A2 B2 d2 | "G"B3 A G2 E2 | "{tonic}"F2 A2 d3 A | "{dominant}"E4 z4 |\n'
            f'"{sixth}"B2 d2 e2 d2 | "G"B3 A G2 E2 | "{dominant}"F2 E2 D2 E2 | "{tonic}"D6 z2 |]\n')


def graph(cue: dict, duration: float | None = None, baseline: bool = False) -> dict:
    seed = cue["seed"]
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "2": {"class_type": "YuE2GenerateMusic", "inputs": {
            "clip": ["1", 1], "style": cue["style"], "lyrics": "",
            "abc": "" if baseline else cue["abc"], "seed": seed, "mode": "full",
            "max_duration": duration or cue["requested_seconds"], "temperature": 1.0,
            "top_p": 0.95, "top_k": 100, "repetition_penalty": 1.2,
            "cfg_scale": 1.01 if baseline else 1.0}},
        "3": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["2", 0]}},
        "4": {"class_type": "EmptyYuE2LatentAudio", "inputs": {"seconds": ["2", 1], "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0], "seed": seed, "steps": 32, "cfg": 1.0,
            "sampler_name": "dpm_2", "scheduler": "sgm_uniform", "denoise": 1.0}},
        "6": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveAudio", "inputs": {
            "audio": ["6", 0], "filename_prefix": "luma_yue2/" + cue.get("generation_id", cue["id"])}},
    }


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def prepare() -> None:
    cues = []
    for index, (region, title, bpm, key, style) in enumerate(REGIONS):
        cues.append(dict(id=f"{region}_explore", title=title, world=index,
                         state="explore", bpm=bpm, key=key, requested_seconds=64,
                         loop=True, style=COMMON + style))
        cues.append(dict(id=f"{region}_explore_b", title=title + " — chemins lointains", world=index,
                         state="explore", bpm=bpm, key=key, requested_seconds=96,
                         loop=True, style=COMMON + style + ", sparse alternate arrangement, long breathing spaces, melody passed between instruments, quiet contrasting middle section"))
        cues.append(dict(id=f"{region}_mystery", title=title + " — traces oubliées", world=index,
                         state="mystery", bpm=max(60, bpm - 16), key="Ddor", requested_seconds=64,
                         loop=True, style=COMMON + style + ", ancient hidden sanctuary, very sparse percussion, low sustained strings, fragmented motif, unresolved gentle wonder, never horror"))
    for state, title, bpm, key, seconds, loop, style in EXTRA:
        cues.append(dict(id=state, title=title, world=-1, state=state, bpm=bpm,
                         key=key, requested_seconds=seconds, loop=loop, style=COMMON + style))
    old_manifest = ROOT / "manifest.json"
    previous_manifest = json.loads(old_manifest.read_text()) if old_manifest.exists() else {}
    old = {c["id"]: c for c in previous_manifest.get("cues", [])}
    for index, cue in enumerate(cues):
        cue.update(seed=2026102300 + index, lyrics="", abc=score(cue["bpm"], cue["key"], cue["title"]),
                   file=None, status="planned", sha256=None, sample_rate=48000, channels=2,
                   pcm_bits=16, gain=0.65, fade_in_ms=1800 if cue["loop"] else 80,
                   fade_out_ms=1800 if cue["loop"] else 100, loop_start_frame=0,
                   loop_end_frame=None, workflow=f"workflows/{cue['id']}.json",
                   audition="pending", generated_seconds=None)
        # Rebuilding prompts must not erase a finished render or its provenance.
        previous = old.get(cue["id"], {})
        for field in ("file", "status", "sha256", "audition", "generated_seconds", "loop_end_frame", "qa_file", "render_provenance", "waveform_qa"):
            if field in previous:
                cue[field] = previous[field]
        if previous.get("generation_id"):
            for field in ("generation_id", "seed", "style", "workflow", "render_attempts"):
                if field in previous:
                    cue[field] = previous[field]
        workflow_path = ROOT / cue["workflow"]
        if cue["status"] in ("generated", "ready") and workflow_path.exists():
            if json.loads(workflow_path.read_text()) != graph(cue):
                raise ValueError(f"{cue['id']}: preserve generated graph; create an explicit revision")
        dump(workflow_path, graph(cue))
    pilot_cues = []
    for suffix, baseline in (("a_free", True), ("b_motif", False)):
        pilot = dict(cues[0], id="pilot_" + suffix, requested_seconds=24, seed=2026102317)
        pilot["workflow"] = f"workflows/{pilot['id']}.json"
        previous_pilot = next((p for p in previous_manifest.get("pilots", []) if p["id"] == pilot["id"]), {})
        pilot_path = ROOT/pilot["workflow"]
        if previous_pilot.get("status") in ("submitted", "generated") and pilot_path.exists():
            if json.loads(pilot_path.read_text()) != graph(pilot, 24, baseline):
                raise ValueError(f"{pilot['id']}: preserve submitted/generated graph; create an explicit revision")
        dump(pilot_path, graph(pilot, 24, baseline))
        pilot_info = {"id": pilot["id"], "file": pilot["workflow"], "seconds": 24,
                           "seed": pilot["seed"], "abc_mode": "off" if baseline else "full",
                           "purpose": "Compare instrumental timbre without/with original ABC motif; do not queue bank before pilot QA."}
        for key, value in previous_pilot.items():
            if key not in pilot_info:
                pilot_info[key] = value
        pilot_cues.append(pilot_info)
    provenance = {}
    for name in ("yue2_blueprint.json", "installed_nodes_yue2.py", "installed_text_encoder_yue2.py", "installed_nodes_audio.py"):
        path = ROOT.parent / "art/provenance" / name
        provenance[str(path.relative_to(ROOT.parent))] = hashlib.sha256(path.read_bytes()).hexdigest()
    dump(ROOT / "manifest.json", {
        "schema": 1, "title": "LUMA — Les Jardins du Souvenir", "path_base": "games/luma_adventure",
        "model": CHECKPOINT, "model_family": "YuE2", "model_sha256": previous_manifest.get("model_sha256"),
        "model_sha256_status": previous_manifest.get("model_sha256_status", "pending read-only hash on gx10-2"),
        "generation": previous_manifest.get("generation", {"status": "awaiting_comfy_endpoint", "submitter": "luma_world_art",
                       "queue_policy": "one GPU job at a time; no downloads; no automatic submissions"}),
        "runtime": {"format": "WAV PCM signed 16-bit little endian stereo 48000 Hz",
                    "ready_rule": "status == ready and file is a string; missing cue means silence",
                    "shared_world": -1, "fallback": "same-world explore, otherwise silence",
                    "pc": "SDL2 integration by game owner", "prodock": "no proven audio backend",
                    "neo": "no proven audio backend; HDMI audio not implemented"},
        "transitions": {"priority": ["victory", "boss", "combat", "mystery", "village", "travel_air", "travel_ground", "explore"],
                        "combat_enter_ms": 250, "combat_leave_hold_ms": 4000,
                        "world_crossfade_ms": 1800, "combat_crossfade_ms": 350,
                        "pause_duck_db": -18, "dialogue_duck_db": -9,
                        "explore_rotation": "alternate A/B after two loops; avoid repeating same cue after a world transition",
                        "quiet_windows": "optional 15–30 seconds of ambience between exploration phrases; not implemented by manifest alone",
                        "state_note": "Desired mix contract; game backend may implement fewer states. No guaranteed bar sync until tempo is auditioned."},
        "provenance_sources": provenance, "pilots": pilot_cues, "cues": cues})
    print(f"Prepared {len(cues)} cue graphs + 2 pilots; no GPU work submitted.")


if __name__ == "__main__":
    prepare()

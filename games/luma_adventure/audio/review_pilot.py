#!/usr/bin/env python3
"""Register real pilot renders and create an offline listening page. No GPU/API."""
from array import array
from datetime import datetime, timezone
import argparse
import html
import json
from pathlib import Path
import shutil
import sys
import wave

import audio_tools as audio

ROOT = audio.ROOT


def write_pcm(path, samples):
    gain = min(1, 10**(-2/20)/max(max(abs(v) for v in samples), 1e-12))
    pcm = array("h", (round(max(-1, min(1, v*gain))*32767) for v in samples))
    if sys.byteorder != "little":
        pcm.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setparams((2, 2, audio.RATE, 0, "NONE", "none"))
        wav.writeframes(pcm.tobytes())
    return gain


def page(manifest):
    cards = []
    for pilot in manifest["pilots"]:
        title = "A · Instrumental libre" if pilot["id"] == "pilot_a_free" else "B · Motif original"
        if not pilot.get("preview_file"):
            cards.append(f"<article><h2>{title}</h2><p>Rendu encore absent.</p></article>")
            continue
        qa = json.loads((ROOT/pilot["qa_file"]).read_text())
        cards.append(f'''<article><h2>{title}</h2>
        <p>{qa['duration_seconds']:.2f} s · PCM16 stéréo 48 kHz · QA technique {qa['waveform_qa']}</p>
        <p>Rendu natif converti pour écoute, sans boucle :</p>
        <audio controls preload="none" src="{html.escape(pilot['preview_file'])}"></audio>
        <p>Essai de boucle avec recouvrement de 125 ms ; écouter au moins trois passages :</p>
        <audio controls loop preload="none" src="{html.escape(pilot['loop_preview_file'])}"></audio>
        <p>Graine {pilot['seed']} · <a href="{html.escape(pilot['qa_file'])}">Mesures et provenance</a></p>
        <p class="pending">Écoute musicale en attente : timbre, voix involontaires, cadence et raccord.</p></article>''')
    region_cards = []
    for cue in manifest.get("cues", []):
        if cue.get("status") != "generated":
            continue
        title = html.escape(cue["title"])
        if not cue.get("file"):
            region_cards.append(f'<article><h2>{title}</h2><p>Rendu natif conservé ; contrôle technique échoué, aucune boucle publiée.</p></article>')
            continue
        src = cue["file"].removeprefix("audio/")
        report = cue["qa_file"].removeprefix("audio/")
        region_cards.append(f'''<article><h2>{title}</h2>
        <p>{cue['generated_seconds']:.2f} s · PCM16 stéréo 48 kHz · QA technique {html.escape(cue.get('waveform_qa','pending'))}</p>
        <audio controls loop preload="none" src="{html.escape(src)}"></audio>
        <p><a href="{html.escape(report)}">Mesures et provenance</a> · Graine {cue['seed']}</p>
        <p class="pending">Produit, écoute musicale en attente. Non activé automatiquement dans le jeu.</p></article>''')
    if region_cards:
        cards.append("<h2>Les six régions · premiers rendus</h2>" + "\n".join(region_cards))
    content = '''<!doctype html><html lang="fr"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>LUMA · Audition YuE2</title><style>
    body{margin:0;background:#111d24;color:#f3e9ce;font:18px/1.6 system-ui,sans-serif}
    main{max-width:940px;margin:auto;padding:40px 22px}h1{font-size:2rem;margin-bottom:8px}
    h2{font-size:1.35rem}p{max-width:76ch}article{padding:22px;background:#203138;border:1px solid #4a6461;border-radius:16px;margin:24px 0}
    audio{width:100%}a{color:#aee8d4}.pending{color:#eac37c}.note{color:#c3d2cd}
    </style><main><h1>LUMA · Les Jardins du Souvenir</h1>
    <p>Deux essais musicaux YuE2, issus du même prompt instrumental et de la même graine.
    Aucun essai n'est automatiquement approuvé pour le jeu.</p>
    ''' + "\n".join(cards) + '''
    <p class="note">Les mesures détectent silence, saturation et discontinuités simples.
    Elles ne certifient ni la qualité musicale, ni l'absence de voix. La page fonctionne
    localement, sans connexion externe. La validation musicale est conservée séparément.</p>
    <script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script>
    </main></html>'''
    (ROOT/"audition.html").write_text(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", choices=("pilot_a_free", "pilot_b_motif"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--page-only", action="store_true")
    args = parser.parse_args()
    manifest_path = ROOT/"manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if args.page_only:
        page(manifest)
        return
    if not all((args.id, args.source, args.history)):
        parser.error("--id, --source and --history are required for a real render")
    pilot = next(p for p in manifest["pilots"] if p["id"] == args.id)
    if pilot.get("status") == "generated":
        raise ValueError("Pilot already registered; retain provenance and make an explicit revision")
    graph = json.loads((ROOT/pilot["file"]).read_text())
    record = audio.validate_history(args.history, graph, args.source.name)
    prompt = record["prompt"]
    samples, source_meta = audio.decode(args.source)
    qa = audio.measure(samples)
    qa.update(source_meta)
    qa["issues"] = audio.technical_issues(qa)
    if qa["duration_seconds"] < 8 or qa["duration_seconds"] > pilot["seconds"] + 2:
        qa["issues"].append("pilot_duration_outside_expected_range")
    qa["waveform_qa"] = "FAIL" if qa["issues"] else "PASS"
    native = ROOT/"renders/raw"/(args.id + args.source.suffix)
    history = ROOT/"provenance"/(args.id + "_history.json")
    for source, destination in ((args.source, native), (args.history, history)):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            if destination.exists():
                raise ValueError(f"Will not overwrite {destination}")
            shutil.copyfile(source, destination)
    preview = ROOT/"renders/previews"/(args.id + ".wav")
    loop = ROOT/"renders/previews"/(args.id + "_loop.wav")
    for path in (preview, loop):
        if path.exists():
            raise ValueError(f"Will not overwrite {path}")
    gain = write_pcm(preview, samples)
    loop_gain = write_pcm(loop, audio.loop_crossfade(samples, round(.125*audio.RATE)))
    loop_samples, loop_metadata = audio.decode(loop)
    loop_qa = audio.measure(loop_samples)
    loop_qa["issues"] = audio.technical_issues(loop_qa, True)
    loop_qa["sha256"] = loop_metadata["sha256"]
    qa.update(id=args.id, prompt_id=prompt[1], native_file=str(native.relative_to(ROOT)),
              history_file=str(history.relative_to(ROOT)), history_sha256=audio.sha(history),
              workflow_sha256=audio.sha(ROOT/pilot["file"]),
              model_sha256=manifest.get("model_sha256"), audition="pending",
              registered_utc=datetime.now(timezone.utc).isoformat(),
              pcm_preview_sha256=audio.sha(preview), pcm_preview_attenuation=gain,
              loop_preview_qa=loop_qa, loop_preview_attenuation=loop_gain,
              loop_crossfade_frames=round(.125*audio.RATE))
    qa_path = ROOT/"qa"/(args.id + ".json")
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2)+"\n")
    pilot.update(status="generated", native_file=str(native.relative_to(ROOT)),
                 preview_file=str(preview.relative_to(ROOT)), loop_preview_file=str(loop.relative_to(ROOT)),
                 qa_file=str(qa_path.relative_to(ROOT)), prompt_id=prompt[1],
                 source_sha256=source_meta["sha256"], waveform_qa=qa["waveform_qa"], audition="pending")
    manifest["generation"]["status"] = "pilots_generated_bank_pending"
    manifest["generation"].pop("active_prompt_id", None)
    manifest["generation"]["last_completed_prompt_id"] = prompt[1]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    page(manifest)
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    if qa["issues"] or loop_qa["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Compile and smoke-test the PC backend using SDL's dummy driver only."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parent


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def main():
    cflags = shlex.split(run(["pkg-config", "--cflags", "sdl2"]))
    libs = shlex.split(run(["pkg-config", "--libs", "sdl2"]))
    qa = ROOT/"qa"
    qa.mkdir(exist_ok=True)
    executable = qa/"audio_smoke"
    compile_args = ["cc", "-O2", "-std=c11", "-Wall", "-Wextra", "-Werror"]
    run(compile_args + ["-DLUMA_HOST", "-DLUMA_AUDIO_SMOKE"] + cflags +
        [str(ROOT/"luma_audio.c"), "-o", str(executable)] + libs)
    run(compile_args + ["-c", str(ROOT/"luma_audio.c"), "-o", str(qa/"audio_stub.o")])
    pilot = ROOT/"renders/previews/pilot_a_free.wav"
    checks = {"real_yue2_pilot": run([str(executable), str(pilot)])}
    with tempfile.TemporaryDirectory(dir=qa) as directory:
        fixture = Path(directory)/"temporary_60ms_mono_fixture_not_music.wav"
        pcm = array("h", (round(.2*32767*math.sin(2*math.pi*330*i/22050)) for i in range(1323)))
        if sys.byteorder != "little":
            pcm.byteswap()
        with wave.open(str(fixture), "wb") as wav:
            wav.setparams((1, 2, 22050, 0, "NONE", "none"))
            wav.writeframes(pcm.tobytes())
        checks["mono_resample_short_loop_and_oneshot"] = run([str(executable), str(fixture)])
    report = {"status": "PASS", "backend": "SDL2 dummy, no physical device opened",
              "checks": checks, "board_stub_compile": "PASS; no board driver implemented",
              "source_sha256": hashlib.sha256((ROOT/"luma_audio.c").read_bytes()).hexdigest(),
              "pilot_sha256": hashlib.sha256(pilot.read_bytes()).hexdigest(),
              "musical_audition": "pending"}
    (qa/"backend_validation.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

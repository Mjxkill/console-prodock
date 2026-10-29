#!/usr/bin/env python3
"""CPU-only checks; generated sine fixtures are tests, never soundtrack assets."""
from array import array
from contextlib import redirect_stdout
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import wave

import audio_tools as audio
import review_pilot


def tone(seconds=2.1, amplitude=0.3, rate=48000):
    return array("f", (amplitude*math.sin(2*math.pi*440*(i//2)/rate)
                       for i in range(round(seconds*rate)*2)))


class AudioTests(unittest.TestCase):
    def test_silence_and_clipping_are_failures(self):
        self.assertIn("silent_or_near_silent", audio.technical_issues(audio.measure(array("f", [0]) * 48000 * 4)))
        clipped = tone()
        clipped[250] = 1
        self.assertIn("clipped_samples", audio.technical_issues(audio.measure(clipped)))
        clipped[250] = 32767/32768
        self.assertIn("clipped_samples", audio.technical_issues(audio.measure(clipped)))
        self.assertEqual([], audio.technical_issues(audio.measure(tone())))

    def test_bad_numbers_and_unaligned_input_rejected(self):
        for values in ([float("nan"), 0], [float("inf"), 0], [0], []):
            with self.assertRaises(ValueError):
                audio.measure(array("f", values))

    def test_crossfade_preserves_adjacent_samples_at_loop_join(self):
        # Deliberately non-periodic segment: old end is far from first sample.
        source = array("f", [math.sin(i*.013)+.000001*i for i in range(22050*2)])
        fade = 600
        out = audio.loop_crossfade(source, fade)
        seam_source = (len(source)//2-fade)*2
        self.assertEqual(len(source)-2*fade, len(out))
        for ch in (0, 1):
            self.assertAlmostEqual(out[ch], source[seam_source+ch], places=6)
            self.assertAlmostEqual(out[-2+ch], source[seam_source-2+ch], places=6)
            self.assertAlmostEqual(out[(fade-1)*2+ch], source[(fade-1)*2+ch], places=6)
            self.assertAlmostEqual(out[fade*2+ch], source[fade*2+ch], places=6)
        with self.assertRaises(ValueError):
            audio.loop_crossfade(source, len(source)//4)

    def test_real_ffmpeg_decode_resamples_mono_to_contract(self):
        with tempfile.TemporaryDirectory(dir=audio.ROOT) as directory:
            path = Path(directory)/"test_fixture_not_music.wav"
            pcm = array("h", (round(.25*32767*math.sin(2*math.pi*330*i/22050)) for i in range(22050*3)))
            if sys.byteorder != "little":
                pcm.byteswap()
            with wave.open(str(path), "wb") as wav:
                wav.setparams((1, 2, 22050, 0, "NONE", "none"))
                wav.writeframes(pcm.tobytes())
            samples, metadata = audio.decode(path)
            result = audio.measure(samples)
            self.assertEqual((22050, 1), (metadata["source_sample_rate"], metadata["source_channels"]))
            self.assertAlmostEqual(result["duration_seconds"], 3, places=3)
            self.assertEqual(result["channels"], 2)
            self.assertEqual(result["sample_rate"], 48000)
            self.assertEqual([], audio.technical_issues(result))
            completed = subprocess.run([sys.executable, str(audio.ROOT/"audio_tools.py"), "inspect", str(path)],
                                       capture_output=True, text=True, check=True)
            self.assertEqual("PASS", json.loads(completed.stdout)["waveform_qa"])

    def test_empty_channel_and_output_escape_rejected(self):
        samples = tone()
        for index in range(1, len(samples), 2):
            samples[index] = 0
        self.assertIn("silent_channel", audio.technical_issues(audio.measure(samples)))
        with self.assertRaises(ValueError):
            audio.confined(audio.ROOT/"../../escape.wav")

    def test_pilot_import_checks_history_before_audio(self):
        with tempfile.TemporaryDirectory(dir=audio.ROOT) as directory:
            root = Path(directory)
            graph = {"1": {"class_type": "YuE2GenerateMusic", "inputs": {"seed": 7}}}
            (root/"graph.json").write_text(json.dumps(graph))
            (root/"manifest.json").write_text(json.dumps({"pilots": [{"id": "pilot_a_free", "file": "graph.json"}]}))
            history = {"prompt": [0, "fixture-only", {"1": {"class_type": "YuE2GenerateMusic", "inputs": {"seed": 8}}}],
                       "status": {"status_str": "success", "completed": True}}
            (root/"history.json").write_text(json.dumps(history))
            args = ["review_pilot.py", "--id", "pilot_a_free", "--source", str(root/"missing.flac"), "--history", str(root/"history.json")]
            with mock.patch.object(review_pilot, "ROOT", root), mock.patch.object(sys, "argv", args):
                with self.assertRaisesRegex(ValueError, "differs from pilot"):
                    review_pilot.main()
            history["prompt"][2] = graph
            (root/"history.json").write_text(json.dumps(history))
            with mock.patch.object(review_pilot, "ROOT", root), mock.patch.object(sys, "argv", args):
                with self.assertRaisesRegex(ValueError, "not listed by SaveAudio"):
                    review_pilot.main()

    def test_successful_pilot_import_remains_unauditioned(self):
        with tempfile.TemporaryDirectory(dir=audio.ROOT) as directory:
            root = Path(directory)
            graph = {"1": {"class_type": "YuE2GenerateMusic", "inputs": {"seed": 7}}}
            (root/"graph.json").write_text(json.dumps(graph))
            source = root/"test_fixture_not_music.wav"
            pcm = array("h", (round(.25*32767*math.sin(2*math.pi*330*i/12000)) for i in range(12000*9)))
            if sys.byteorder != "little":
                pcm.byteswap()
            with wave.open(str(source), "wb") as wav:
                wav.setparams((1, 2, 12000, 0, "NONE", "none"))
                wav.writeframes(pcm.tobytes())
            manifest = {"generation": {}, "cues": [], "pilots": [
                {"id": "pilot_a_free", "file": "graph.json", "seconds": 24, "seed": 7}]}
            (root/"manifest.json").write_text(json.dumps(manifest))
            history = {"prompt": [0, "fixture-not-a-real-GPU-job", graph],
                       "status": {"status_str": "success", "completed": True},
                       "outputs": {"7": {"audio": [{"filename": source.name}]}}}
            (root/"history.json").write_text(json.dumps(history))
            args = ["review_pilot.py", "--id", "pilot_a_free", "--source", str(source), "--history", str(root/"history.json")]
            with mock.patch.object(review_pilot, "ROOT", root), mock.patch.object(sys, "argv", args), redirect_stdout(io.StringIO()):
                review_pilot.main()
            result = json.loads((root/"manifest.json").read_text())["pilots"][0]
            self.assertEqual("generated", result["status"])
            self.assertEqual("PASS", result["waveform_qa"])
            self.assertEqual("pending", result["audition"])
            self.assertTrue((root/result["preview_file"]).exists())
            self.assertTrue((root/"audition.html").exists())
            qa = json.loads((root/result["qa_file"]).read_text())
            self.assertEqual([], qa["loop_preview_qa"]["issues"])
            self.assertEqual(audio.sha(source), qa["sha256"])


if __name__ == "__main__":
    unittest.main()

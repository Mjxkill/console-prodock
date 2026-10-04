from pathlib import Path
import hashlib
import json
import shutil
import tarfile

root = Path('/home/michael/console')
stage = root / 'tang/impl/gpu_v1_r31'
proof = root / 'TESTS/gpu_v1_20261004'
read = lambda p: json.loads(p.read_text())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
board = read(proof / 'board_r31/result.json')
end = read(proof / 'endurance_r31/result.json')
timing = read(proof / 'r31_timing.json')
assert board['status'] == end['status'] == 'pass'
assert board['scope'] == 'usb_and_gpu' and len(board['runs']) == 2
assert all(x['status'] == 'pass' and x['usb_speed_mbps'] == 480 and
           x['fresh_enumeration'] and x['target_serial'] == '2023112818'
           for x in board['runs'])
assert end['elapsed_seconds'] >= 1800 and end['requested_seconds'] == 1800
assert end['usb']['speed_mbps'] == 480
assert {x['scene'] for x in end['samples']} == {0, 1, 2}
assert all(x['underflows'] == x['rejected'] == 0 and x['frames'] == 120 and
           x['line'] < 2556 and x['gpu_max'] <= 32000000 for x in end['samples'])
assert timing['pass_setup_hold'] and timing['minimum_all_reported_slacks_ns'] >= 0
for prefix in ('copy_synthesis', 'scanout_synthesis'):
    assert read(proof / f'r31_{prefix}.json')['passed']
fs = stage / 'impl/pnr/console_gpu_v1_r31.fs'
sha = digest(fs)
assert sha == board['sha256'] == (stage / 'bitstream.sha256').read_text().split()[0]
for prefix in ('ddr', 'gpu', 'usb'):
    d = read(proof / f'r31_{prefix}_gray_sdf.json')
    assert d['pass_routed_gray_bound'] and d['bitstream_sha256'] == sha
manifest = read(stage / 'sources.json')
assert len(manifest) == 119
for name, expected in manifest.items():
    assert digest(stage / 'source' / name) == expected, name
archive = proof / 'r31_sources.tar.gz'
assert digest(archive) == (proof / 'r31_sources.tar.gz.sha256').read_text().split()[0]
with tarfile.open(archive) as t:
    for name, expected in manifest.items():
        f = t.extractfile('gpu_v1_r31/source/' + name)
        assert f and hashlib.sha256(f.read()).hexdigest() == expected, name
for folder, tool, expected in (
    ('board_r31', 'reload_test_tool.py', board['test_tool_sha256']),
    ('board_r31', 'gpu_test_tool.py', board['gpu_test_tool_sha256']),
    ('endurance_r31', 'test_tool.py', end['tool_sha256']),
):
    assert digest(proof / folder / tool) == expected
for name, expected in end['helper_sha256'].items():
    assert digest(proof / 'endurance_r31' / name) == expected

summary = dict(stage=stage.name, status='pass', sha256=sha, sources=len(manifest),
    timing_minimum_all_reported_slacks_ns=timing['minimum_all_reported_slacks_ns'],
    full_board_suite='pass', physical_visual_confirmation='user confirmed all three scenes 2026-10-04',
    endurance_seconds=end['elapsed_seconds'], endurance_frames=end['total_frames'],
    endurance_windows=len(end['samples']), endurance_usb_echo_bytes=end['usb_echo_bytes'],
    endurance_max_drawing_ms=max(x['gpu_max'] for x in end['samples']) / 800000,
    endurance_max_line_cycles=max(x['line'] for x in end['samples']),
    endurance_max_presentation_interval_ms=max(x['frame_max'] for x in end['samples']) / 800000,
    usb_speed_mbps=480, underflows=0, rejected=0,
    resources=dict(logic=65812, logic_available=138240, registers=43754,
        registers_available=139140, bsram=242, bsram_available=340,
        dsp=83, dsp_available=298, primary_clocks=8, primary_clocks_available=8),
    source_archive_sha256=digest(archive))
summary['endurance_scenes'] = {}
for scene in range(3):
    rows = [x for x in end['samples'] if x['scene'] == scene]
    summary['endurance_scenes'][str(scene)] = dict(
        frames=sum(x['frames'] for x in rows),
        drawing_max_ms=max(x['gpu_max'] for x in rows) / 800000,
        presentation_max_ms=max(x['frame_max'] for x in rows) / 800000,
        fps_min=min(x['fps_x100'] for x in rows) / 100,
        fps_max=max(x['fps_x100'] for x in rows) / 100)
(proof / 'r31_validation.json').write_text(json.dumps(summary, indent=2) + '\n')
dest = root / 'bitstreams/console_gpu_v1_800.fs'
assert not dest.exists() or digest(dest) == sha, 'Refusing to overwrite a different reference'
shutil.copy2(fs, dest)
dest.with_suffix('.sha256').write_text(sha + '  ' + dest.name + '\n')
shutil.copy2(stage / 'sources.json', dest.with_suffix('.sources.json'))
shutil.copy2(proof / 'r31_validation.json', dest.with_suffix('.validation.json'))
metrics = read(proof / 'r31_board_metrics.json')
metrics['endurance'] = 'pass; see r31_validation.json and endurance_r31/result.json'
(proof / 'r31_board_metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
dest.with_suffix('.md').write_text(f'''# GPU V1 — image SRAM validée

4 octobre 2026, build `gpu_v1_r31`, Tang Mega 138K Pro Dock FPG676.

Les sept points vidéo sont livrés : cibles RGB565/Z16 paramétrables, cache
DDR pour textures jusqu'à 512 × 512, API 2D RGB565, alpha par texel/additif/
Gouraud, brouillard/mipmaps, mode 400 × 240 agrandi ×2 avec HUD natif,
ABI/pilote/outils et qualification. Les commandes historiques sont conservées.

- AE350 800 MHz, AHB 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz ; USB HS 480 Mbit/s.
- `f` vérifie mémoire, douze poses couleur/Z/LCD et changement de résolution ;
  `g` anime les trois scènes ; `c` met en pause.
- Zéro violation setup/hold : marge minimale globale +0,140 ns ;
  pires setups GPU/DDR +0,706 ns et AHB +1,524 ns. SDC inchangé.
- Ensemble FPGA : 65 812 éléments logiques (47,61 %), 43 754 registres
  (31,45 %), 242 BSRAM (71,18 %), 83 DSP (27,85 %), 8/8 PRIMARY.
  Firmware : 63 832 octets ITCM, 29 184 octets BSS.
- Deux rechargements SRAM, nouvelle énumération HS à chaque fois,
  217 640 octets binaires exacts ; suite GPU complète passée.
- Douze références couleur/Z et LCD exactes, test de copie entre pages et
  changement de Z passé, gardes mémoire intactes. Trois scènes confirmées
  visuellement par l'utilisateur.
- Endurance : {summary['endurance_seconds']:.3f} s,
  {summary['endurance_frames']} images et {summary['endurance_usb_echo_bytes']}
  octets d'écho USB exacts pendant l'animation, sans underflow, refus,
  corruption détectée ni réénumération. Références revérifiées après le test.
  Dessin maximal : {summary['endurance_max_drawing_ms']:.3f} ms ;
  composition : {summary['endurance_max_line_cycles']}/2556 cycles par ligne.

Avant les échos d'endurance, aventure/couloir : environ 27,4 images/s ;
route : 54,58 images/s. Les échos occupent momentanément la boucle CPU et
leur durée compte dans l'intervalle de présentation. Le LCD reste à environ
55,04 Hz. Les scènes sont des charges de qualification, pas des jeux finis.
Le dessin comparatif prend 28,464 ms en 400 × 240 contre 102,228 ms en
800 × 480 (facteur 3,59). Ces mesures valent pour les contenus testés.

SHA-256 du `.fs` : `{sha}`.
Le `.sources.json` décrit les 119 sources figées ; leur archive vérifiée est
[`r31_sources.tar.gz`](../TESTS/gpu_v1_20261004/r31_sources.tar.gz), accompagnée
de son SHA-256. Le `.validation.json` donne le bilan automatique.

Le garde-fou `check_gpu_copy_synthesis.py` est obligatoire : une absorption
incorrecte de registres à activations distinctes dans les DSP avait laissé
passer le timing tout en corrompant les copies r20. Conserver `syn_preserve`
sur le paquet V1 ; les preuves et la correction sont documentées.

Charger uniquement en SRAM sur le FTDI **2023112818**, après identification
de son numéro bus:périphérique actuel. La flash n'a pas été modifiée.
Reconstruction : options placement 3, route 1, réplication désactivée et
IP USB Gowin High-Speed/PHY Advance, selon la fiche de tests et le manifeste.

[Fonctionnalités et limites](../ARCHI/FONCTIONNALITES_ACTUELLES.md) ·
[Contrat](../ARCHI/GPU_V1.md) ·
[Validation détaillée](../TESTS/TESTS_GPU_V1.md).
''')
print(json.dumps(summary, indent=2))

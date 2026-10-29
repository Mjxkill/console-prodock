# Validation Gowin Workbench — 13 octobre 2026

- `doctor.json` : versions réelles et présence de la base GW5AST-138C.
- `unit-tests.log` : 21 tests Python réussis.
- `browser-test.json` : test Chrome réussi, sans erreur JavaScript ; filtres,
  chemins, sélection de région, commande proposée et adaptation mobile.
- `neo_probe_001.json` : trois graines, trois bitstreams (LUT + 2 BSRAM).
- `neo_dsp_001.json` : deux échecs de pack avec Apicula fourni par OSS CAD.
- `neo_dsp_legacy_002.json` : trois graines, trois bitstreams avec Apicula 0.32,
  1 MULT12X12 et 2 BSRAM.
- `neo_dsp_final.json` : parcours complet supplémentaire, routeur2, graine7,
  avec empreintes des sorties calculées par la version finale du script.
- `neo.cst`, `neo.json`, `plan_host.json`, `n18r2-execution.json` : expérience
  Gowin réelle, même netlist et SDC que N18, placement régional de 13 cellules.
- `console_neo_n18r2.qualification.log` : PASS timing et audits DSP, marge
  minimale +0,135 ns, aucune violation setup/hold.
- `summary.json` : synthèse des 20 essais, y compris échecs et compilations
  incomplètes ; c'est une photographie, pas une page de suivi actualisée.

Les bitstreams, rapports détaillés, commandes et journaux volumineux sont
conservés localement dans `optimizer/runs/` et `tang/impl/` (hors Git).
L'interface consultable se trouve dans `optimizer/runs/dashboard/index.html`.

Les circuits libres ne sont pas validés sur carte. Le premier essai physique
de la console N18r2 échoue au contrôle CRC DDR ; son timing PASS ne constitue
pas un succès matériel. Voir `../NEO_720P_20261012.md` et les captures
`../neo_720p_20261012/board_n18r2*` et `memory_ilm_n18r2`.

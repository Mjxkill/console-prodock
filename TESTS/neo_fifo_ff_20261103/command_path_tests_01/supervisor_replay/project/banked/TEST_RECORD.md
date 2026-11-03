# Fiche de tests — helper banques Neo

Objectif : conserver le SDPB128×32 observable par les deux files commandes,
réduire la demande de connexions du mux FF sans cycle supplémentaire.

Entrées exactes : source `banked_words32.v`, bibliothèque officielle
`/home/michael/gowin/IDE/simlib/gw5a/prim_sim.v`, banc figé
`../mapping_01/implementation/tb_storage.sv`. Empreintes dans les RESULT des
campagnes et QUALIFICATION.json. Paramètres/limites SDPB dans CONTRACT historique.

Procédure exécutée :

1. `test_banked.py --out .../rtl_02 --mutants` :6casPASS,5mutantsdétectés.
2. `synthesize.py prepare/run --stage .../stage_02 --root-coordinated-helper-only` :
   réutilise le projet et le lanceur figés ; seul helper synthétisé, rc0.
3. `compare.py .../stage_02/helper/neo_command_ff128.vg --out .../COMPARISON.json` :
   inventaire+fanouts+graphe LUT face au helper précédent, zéroRAM, FF identiques.
4. `test_banked.py --candidate .../stage_02/helper/neo_command_ff128.vg --out .../mapped_01` :
   six casPASS sur primitives officielles, aucun SDF.
5. `qualify_helper.py` : toutes4128FF, INIT/CLK/reset/Q/D, sorties et GSR contrôlés ;
   empreintes sources/tests/netlist recoupées ; inverse exacte vector→array.

Résultats conservés : `rtl_02/RESULT.json`, `mapped_01/RESULT.json`,
`stage_02/helper/result.json`, `COMPARISON.json`, `QUALIFICATION.json`.
Échecs conservés : `rtl_01` (timeouts, interruption), stage01 (licence/sandbox).

Aucun matériel, aucun PNR, aucune évaluation CLS ou STA. Collisions interdites
par fournisseur et métastabilité physique hors périmètre ; les tests du helper
ne prouvent pas les pointeurs FIFO, leur CDC, ni le GPU complet. Aucun processus
Icarus/GowinSynthesis restant au contrôle final hôte. Le VVP temporaire du probe
est supprimé avec empreinte conservée dans CLEANUP.json.

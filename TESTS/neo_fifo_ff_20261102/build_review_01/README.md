# Expérience Neo : deux mémoires de commandes en bascules

La référence est REJECT R1, VG `76d56bd49776d12919c8051f5460bb5e7cadf73fb388ac2bd2cddea63c63b255`, bitstream chargé `f9f379e6aea82dda358aef1f34508c246920c89c877e9a5847162e32c3919e15`. Le diagnostic NGDB a observé 32 mots reçus et le dernier mot 1. Cela prouve ce témoin de sortie de FIFO ; cela ne prouve pas les sept autres mots du paquet ni une défaillance du stockage SDPB. Le remplacement demandé est une expérience discriminante, pas une cause déjà démontrée.

## Changement autorisé

- `ddr_dcfifo_3.\g_inferred_storage.mem_g_inferred_storage.mem_0_0_s`.
- `blitter.cmem_cmem_0_0_s`.

Seul leur type devient `neo_command_ff128` ; les six paramètres SDPB fixés par instance sont retirés. Noms d'instances et douze connexions sont conservés, y compris horloges, CE, reset, données et adresses. Ni pointeur, ni flag, ni machine à états, ni observateur ne change. Une inversion vérifiée restaure le texte intégral du VG original. Le helper est maintenu uniquement dans `../mapping_01/implementation/neo_command_ff128.v` ; la copie dans un stage est une archive de construction épinglée.

La compatibilité sémantique est une responsabilité distincte du contrôle structurel : mêmes dimensions accessibles 128×32, même latence de lecture, priorité du reset de sortie, mémoire non réinitialisée par le reset local. L'agent de mapping contrôle ces points contre le modèle fournisseur. Le GSR de l'application est inactif après chargement ; une assertion GSR en fonctionnement n'est pas couverte par cette substitution.

## Chaîne reprise

`recipe.py prepare` crée uniquement le projet du helper et l'application modifiée sous forme gzip. Le projet XML reprend les options de la synthèse des helpers REJECT R1, avec autre top/source/sortie. `recipe.py synth --root-reviewed-helper-synthesis` réutilise le moteur figé `TESTS/neo_copy_dma_20261101/build/build.py` : gardes de régression Neo/ProDock, environnement Gowin, verrou, lancement unique, processus identifié et reçu d'erreur. Il ne synthétise jamais le reste de l'application et ne lance pas de PNR.

`recipe.py assemble` exige le reçu de synthèse et les empreintes, l'interface exacte, des primitives connues et au moins 4096 FF de stockage par helper. Toute primitive mémoire RAM/SP/SDPB/DP/ROM est refusée dans le helper. Deux instances du même module sont ajoutées à l'application : c'est un module partagé unique, pas deux copies maintenues. Le VG synthétisé volumineux est un artefact fournisseur archivé, pas un fichier source maintenu.

`finalize.py` exige ensuite une qualification indépendante associée au SHA du VG assemblé. Il crée le manifeste et un petit `route.py` reprenant `route_variant.py` figé. Root seul peut préparer/lancer cette route, une fois, après revue ; aucun appel automatique dans cette livraison.

## Contraintes et ressources

CST `6330c9dd971b9151c08bddcf8b7b6a529983bc25f1c03ab4193b0b6a224aeac1` et SDC `c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113` restent byte-identiques. L'adaptateur historique utilise les mêmes contraintes/ROM que REJECT R1. `cmem_s3`, visé par le CST ligne379, est la LUT d'activation du stockage : cette LUT est préservée, ce n'est pas la primitive SDPB remplacée. Les paramètres de placement et routage restent identiques ; le nouveau placement physique n'est pas garanti identique.

Le rapport parent est conservé dans BASE_RESOURCES.json : 87018 Logic, 56305 FF, 59413 CLS, 263 BSRAM. Les compteurs du helper après synthèse sont des cellules logiques, pas une occupation PNR. Environ 8192 FF de stockage +64 FF de sortie sont attendues pour les deux instances ; le mux de lecture et le décodage ajoutent de la logique. L'occupation, le timing et le comportement matériel du nouveau candidat restent à qualifier séparément.

## Tests

`python3 -B -m unittest discover -s TESTS/neo_fifo_ff_20261102/build_review_01 -p test_recipe.py -v`

Trois cas sur le VG réel : delta autorisé/inversion ; refus READ_MODE modifié ; refus type mémoire inattendu. Les tests de comportement mémoire sont livrés par `mapping_01`, puis rejoués sur le helper synthétisé. Aucun test matériel, routage ou chargement n'est effectué par cette recette lors des vérifications hors ligne.

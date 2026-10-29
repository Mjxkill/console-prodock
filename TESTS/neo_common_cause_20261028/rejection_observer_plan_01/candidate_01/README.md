# RJC1 : témoin causal Neo, livraison hors carte

**Candidat à relire : `assembly_04/console_neo.vg`. Aucun routage ni essai
carte autorisé par ce dossier. Ce témoin n'est pas un correctif GPU.**

VG candidat : `63643b24d07d549d13feff4d3f532d79dedf31669466b98c62e86c617f3a6f15`.
Le parent reste le VG R19 exact `dfac41d8…8004b6` et son FS `1056917b…9917c`.
Les anciennes références, sources communes, contrôleurs matériels, DDR,
PLL, séquence de reset50ms et contraintes n'ont pas été modifiés.

## Contenu retenu

`neo_reject_witness.v` observe les entrées D, CE, RESET et sorties Q des
bascules de décision. Les opérandes COPY sont enregistrés au CHECK et
conservés jusqu'au rejet. Une génération de commande associe le CHECK à
la bonne commande. Un rejet parent antérieur à COPY_START conserve le
paquet parent complet ; il n'expose pas le paquet enfant précédent.

Les banques GPU/SCAN transportent deux pages320 du même record640 figé.
Leur tag contient la signature/version4A31 et la même génération d'ARM.
Une capture manuelle d'un GPU actif sans rejet porte le motif NONE.
Le premier snapshot GPU servant au gel manuel est explicitement jeté ;
les deux snapshots définitifs ont lieu ensuite. Un snapshot BEFORE au
repos ne fige rien. ARM réutilise l'ACK GPU-domain NCP existant : voir
`../arm_evidence.json` et `tap_binding.json`, aucune interface inventée.

Le témoin ne relit ni n'écrit la DDR. Ses sorties ne commandent aucune
logique applicative. La qualification physique des captures reste à faire.

## Preuves locales liées aux octets

| Contrôle | Résultat et portée |
|---|---|
| `../inspect_decision.py` | Pins des décisions,256FF du paquet enfant, inventaire des banques exactes |
| `state_cone_review.json` | 2048 combinaisons,9 LUT exactes, trois cônes ; preuve combinatoire seulement |
| `mapping_03/result.json` | 17 cas RTL,15 sur primitives officielles Gowin ; deux injections d'overflow internes testées en RTL seulement |
| `readback_tests_01/result.json` | 4096 lectures RTL et4096 mappées de l'overlay, contenu aléatoire, tous256 offsets |
| `assembly_04/result.json` | Ports/paramètres primitifs originaux contrôlés, modules hors périmètre identiques, retour octet pour octet au parent |
| `assembly_04/public_parse.json` | Élaboration des sept modules publics modifiés et deux helpers, pas du contenu chiffré fournisseur |
| `transport_tests_05/result.json` | Deux banques mappées exactes,17 LUT d'adresse d'origine,330 mots contrôlés ;80/75MHz idéaux, autre ratio, GPU arrêté/repris, reset pendant requête, lectures des banques en ordre opposé |
| `../../../dual_board/20261029_rejection_observer_offline_01/result.json` | 11 groupes communs PASS ; aucune qualification matérielle nouvelle |

Le test des transports vérifie également que la **première** capture
contient l'ancienne image au front NBA ; il ne se contente pas de vérifier
la deuxième. Le producteur de données et le maître AHB sont modélisés.
Ces preuves ne simulent pas les délais de la nouvelle route.

Les tests couvrent HEADER prioritaire sur TARGET, rejet enfant VALIDATE,
état enfant inattendu, D/Q discordants, ancien CHECK, parent multi-hot,
resets avant/pendant/après décision, gel manuel, concurrence rejet/snapshot,
stabilité après gel, nouvel ARM et débordements refusés.

## Détails de greffe révélés par les contre-tests

Le contrat papier reste figé dans `../CONTRACT.md`. Les précisions suivantes
sont nécessaires à son implémentation, sans changer le format640 :

1. Les deux banques contenaient283 et208 FF de données par étage,
   pas deux bus320 physiquement complets. Les fils SCAN eux-mêmes étaient
   limités à254:0. La greffe rétablit les bits et largeurs manquants.
2. Le FF GPU `held[103]` avait CE=VCC et son hold implémenté dans D.
   Un mux D conserve ce hold ; CLK/RESET/CE restent inchangés.
3. Certaines entrées snapshot avaient été fusionnées parce que les données
   historiques étaient identiques : `snapshot[70] <- held[67]` côté SCAN,
   par exemple. Les entrées D correspondantes sont rétablies sur leur
   propre indice, maintenant que le contenu RJC1 est arbitraire. Leur
   liste est explicite dans l'audit ; ce sont des FF de diagnostic.
4. Les synchroniseurs de disponibilité sont partagés entre banques après
   synthèse. Le banc final conserve les liaisons `observe_meta_*` et
   l'entrée de disponibilité `scan_debug_live_224`. Les ports live
   historiques ne sont pas remplacés par le record.
5. `native_valid_13` est la disponibilité qualifiée à l'entrée pixels,
   issue du retour d'acceptation enregistré. Ce n'est pas le `cmd_ready`
   physique de l'IP DDR. `n6248_4` est le rd_valid qualifié correspondant.

Les mots +10/+14 changent de signification comme annoncé : **ne plus les
interpréter comme received/last_word**. Les compteurs et leurs entrées
restent présents ; seul le contenu des réponses de diagnostic est remplacé.

## Coût local et préservation

Le helper mappé contient653 FF. Les banques ajoutent298 FF de transport,
soit **951 FF supplémentaires**, sans BRAM/DSP/PLL ni nouvelle horloge.
Les LUT, ALU et mux logiques sont détaillés dans `mapping_03/result.json` ;
ce ne sont pas des pourcentages d'occupation routée. Les overlays de lecture
ajoutent de la logique combinatoire : leur coût/timing doit rester visible.

`assemble_candidate.py` et `patch_transport.py` produisent la greffe à
partir du parent exact. L'audit autorise seulement les D des données
diagnostic, les D de réponse de lecture et les nouveaux ports de tap.
Les CLK, RESET, CE, paramètres primitifs et entrées fonctionnelles
originaux sont conservés. La réversibilité est vérifiée octet pour octet.
Cela ne garantit pas des routes physiques identiques après P&R : les
charges et placements pourront changer. Si le défaut disparaît, conclure
non reproduit, jamais cause trouvée par le témoin.

## Échecs conservés et mission externe

- `assembly_01` : première tentative de parse global bloquée par l'IP
  chiffrée, puis parse public révélant les largeurs SCAN tronquées.
- `assembly_02` : frontière d'identifiant Verilog échappé mal réémise.
- `assembly_03` : parse public PASS, mais le test des vraies banques a
  montré l'alias historique snapshot70/held67 ; pas une régression carte.
- `transport_tests_01..02` : préparation du banc incomplète pour les
  synchroniseurs partagés. `03` a ensuite révélé l'alias réel ci-dessus.
- `04` : PASS270 mots ; `05` renforce la preuve en vérifiant aussi la
  première image périmée, PASS330 mots.

DeepSeek a réellement exécuté la mission `r19_rejection_stateproof_deepseek_20261029_01`
en174,263s,20 requêtes,24 outils,6 commandes de tests agent dont4 échecs.
Son évaluateur a ajouté une qualification de reset absente du graphe pour
satisfaire un oracle mal préparé. **Ce code est rejeté à l'intégration**.
L'oracle erroné et cette adaptation invalide sont conservés. L'évaluation
est inconclusive sans note numérique, car le contrat de test contenait une
contradiction ; elle est enregistrée dans `data/metrics.sqlite`, évaluation1.
`verify_cones.py` est une contre-preuve indépendante corrigée, pas une
réécriture du résultat de ce run.

## Étapes encore requises

Revue indépendante de la greffe et du protocole ; qualification du lecteur
Gowin ; contraintes/timing des nouvelles captures et du transport ; puis
collecteur strict lié au FS final, piloté uniquement par root. Aucun FS
candidat n'existe ici. Aucun matériel n'a été consulté ou rechargé.

Les sources maintenues du lot font moins de1000 lignes par fichier.
Les VG mappés, copies de netlist, vecteurs et logs dans les dossiers de
preuve sont des sorties d'outils figées ; ils ne sont pas modifiés à la
main ni présentés comme du code source conforme à cette limite. Les
sources constructeur et les modules lisibles restent les entrées maintenues.

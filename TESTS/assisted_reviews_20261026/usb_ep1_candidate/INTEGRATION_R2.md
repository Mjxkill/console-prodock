# F01 — intégration BOT, révision 2

Le candidat passe le scénario exécuté contre le modèle officiel Gowin HS 3.3 ; la source de production échoue précisément sur `F01_STALE_DATA_AFTER_BOT`. Aucun RTL de production ni résultat R1 n'a été modifié. Ceci est une simulation numérique UTMI/AHB, sans carte, PHY, câble, pilote hôte ou CPU firmware.

## Preuve exécutée

- `integration_candidate_r2/result.json` : `pass: true`, retour 0, entrées inchangées. La suite officielle historique termine encore avec HS=1, 1 562 octets IN de motif, 25 paquets IN acquittés, 4 reprises, 134 NAK ; 6 175 octets OUT de motif, 10 NAK et 1 NYET ; CDC livre 11 octets. Ces compteurs historiques mélangent des périmètres : les compteurs d'octets de motif n'incluent pas les CBW/CSW ni les 30 octets du nouveau scénario. Les marqueurs F01 complètent la preuve, ils ne sont pas déduits de ces compteurs.
- `integration_original_r2/result.json` : `pass: false`, retour 1, mêmes entrées sauf le FIFO sélectionné, entrées inchangées. Après le même événement BOT et la même purge, le contrôleur émet DATA0 avec 13 octets `55` au lieu de NAK. Il s'agit d'une ancienne réservation/longueur survivante ; ces octets ne sont pas les 13 octets initiaux. L'échec n'est donc pas présenté comme la retransmission exacte de l'ancien contenu RAM.
- Dans les deux traces : événement BOT reçu une fois ; firmware toujours propriétaire après BOT ; assertion puis libération de `quiet_h` par la commande AHB `+0x14[0]` ; 100 fronts USB de purge observés, tous sous EP0. La propriété EP0 est surveillée pendant toute la fenêtre de purge.
- Dans le candidat : ancien paquet abandonné → NAK ; second CBW de 31 octets reçu et comparé via AHB ; 17 nouveaux octets exacts, avec un premier octet distinct ; CSW de 13 octets exact (signature, tag, résidu zéro, statut succès), ACK reçu et FIFO vide.

`tasks_r2.svh` exerce le nouveau cas avec le garde BOT actif. Le maître AHB représente la réaction firmware : deux CBW INQUIRY valides, purge explicite, handback puis reclaim, données puis CSW. Les 13/17 octets de données sont des motifs de transport, pas une implémentation de la sémantique SCSI INQUIRY. La suite historique désactive temporairement le garde pour son ancien test de transport brut ; cette convention reste limitée à ce test historique.

La séquence hôte utilise de vrais SETUP/OUT/IN, CRC et ACK UTMI. Après BOT et les deux CLEAR_FEATURE sur `81`/`01`, seul l'état du modèle hôte revient à DATA0 et abandonne l'attente de reprise. Aucune variable interne DUT n'est forcée ou écrite. La source historique contient quelques observateurs hiérarchiques en lecture ; le scénario F01 ajouté utilise les interfaces publiques. Les tâches ajoutées rejettent aussi les valeurs AHB inconnues.

## Reproduction

Chaque sortie doit être nouvelle ; le lanceur refuse d'écraser JSON, journal ou dossier d'artefacts existants.

```sh
python3 TESTS/assisted_reviews_20261026/usb_ep1_candidate/check_integration_r2.py --output TESTS/assisted_reviews_20261026/usb_ep1_candidate/integration_candidate_new/result.json
python3 TESTS/assisted_reviews_20261026/usb_ep1_candidate/check_integration_r2.py --original --output TESTS/assisted_reviews_20261026/usb_ep1_candidate/integration_original_new/result.json
```

La deuxième commande doit retourner 1 avec le marqueur F01 précis ; un autre échec n'est pas une preuve de ce défaut. Le lanceur conserve les sources de banc générées, le journal de compilation, les empreintes des sources/modèle/primitives, les marqueurs et le journal complet. Le modèle HS exporté est vérifié contre sa provenance et le descripteur courant. Les compilateurs peuvent être fournis par `--iverilog`, `--ivl-root` et `--vvp`.

## Proposition d'intégration permanente — non appliquée

1. Reporter uniquement les tâches `f01_command`, `f01_status`, le moniteur de purge et le bloc final F01 dans `TESTS/rtl/usb_msc_controller_tasks.svh`, en conservant tous les scénarios existants et leur ordre. Le même fichier est déjà consommé par `tools/check_usb_msc_sim.py`, lancé dans le groupe `usb_msc` de `tools/run_board_regressions.py`. Ajouter aux critères de succès de ce wrapper les quatre marqueurs F01 (deux CBW, une purge, un NAK, une fin de reprise), la stabilité des entrées et la conservation des artefacts. Ne pas ajouter un second wrapper permanent copié : le wrapper R2 reste une preuve isolée.
2. Promouvoir le banc d'interfaces `ep1_flush_interfaces_tb.sv` vers `TESTS/rtl/usb_ep1_flush_interfaces_tb.sv` et adapter son lanceur vers `TESTS/test_usb_ep1_flush_interfaces.py`. Ce banc rapide couvre la matrice EP0/1/2, impulsions 1/2/64 cycles, ACK/POP/txact, transition EP2→EP1, conservation d'un vrai paquet EP2 et reprises bit exactes. Il complète le scénario BOT réel ; il ne le remplace pas.
3. Pour les régressions courantes après adoption du correctif, le lanceur rapide teste le RTL courant et des mutants temporaires explicitement étiquetés. Le témoin de production historique en échec reste archivé ici avec son SHA ; ne pas exiger que le futur RTL corrigé échoue sous le nom « original ». Les mutants ne doivent jamais modifier les sources partagées.
4. Rattacher le banc rapide au groupe USB ou à un groupe dédié dans `tools/run_board_regressions.py`, sans supprimer aucun groupe existant. Les chemins proposés sous `TESTS/*.py` et `TESTS/rtl/*` entrent déjà dans `board_contract.regression_inputs()`. Vérifier aussi l'inventaire des wrappers modifiés. Toute adoption change les entrées et impose une nouvelle campagne complète avec un nom unique ; seul le parent la pilote.
5. Conserver séparément : simulation locale, synthèse, timing, essais Pro Dock et essais Neo. Aucun PASS de ce paquet n'autorise à remplacer G22r0/R17, ne qualifie une carte ou ne dispense d'identifier le bitstream exact avant un essai.

Les résultats R1 sont conservés comme erreurs de banc : ils supposaient à tort que BOT rendait automatiquement la propriété lorsqu'un firmware la détenait. La révision R2 exprime le contrat réel et ne transforme pas leur échec en preuve du correctif.

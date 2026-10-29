# CPU32 et CLEAR — résultat corrigé, hors carte

Huit scénarios PASS sur gpu_v1 R19 + adaptateur/arbitre natifs exacts.
L’adaptateur et l’arbitre sont identiques octet pour octet à G22r0. Les autres
moteurs GPU diffèrent entre snapshots : aucune qualification globale G22 déduite.
Le maître CPU est une source128bit séquentielle, pas l’AE350/bridge/CDC réels.

| Cas | CPU observé complété/émis | GPU done/busy observé | natifs read/write/return observés | full/tags arb/tags adapt | CPU final | GPU final | écritures finales |
|---|---|---|---|---|---|---|---|
| 0 | 16/16 | 2/0 | 16/1/16 | 0/0/0 | 32 | 2/0 | 1 |
| 1 | 0/1 | 1/1 | 0/0/0 | 0/0/1 | 32 | 2/0 | 1 |
| 2 | 0/1 | 1/1 | 0/0/0 | 0/0/1 | 32 | 2/0 | 1 |
| 3 | 8/8 | 1/1 | 8/43/8 | 0/0/0 | 32 | 1/1 | 125 |
| 4 | 0/1 | 1/1 | 16/0/0 | 1/16/1 | 32 | 2/0 | 1 |
| 5 | 32/32 | 1/1 | 32/0/32 | 0/0/0 | 32 | 1/1 | 0 |
| 6 | 0/1 | 1/1 | 1/35/0 | 0/1/1 | 32 | 1/1 | 141 |
| 7 | 32/32 | 1/1 | 32/0/32 | 0/0/0 | 32 | 1/1 | 0 |

Cas0 : sain. Cas1 : commande native pas prête. Cas2 : écriture native pas prête.
Cas3 : acceptation arbiter→GPU coupée, écritures répétées. Cas4 :16lectures
scan synthétiques avec retours retenus. Cas5 : requête nativeGPU supprimée.
Cas6 : retourGPU coupé + retourCPU retenu. Cas7 : requêteGPU supprimée +
écriture pas prête. Tous les32mots CPU ont été comparés (dont96B de sentinelles).

## Conclusion exploitable

- Cas2 : la sélection blitter reste attribuée pendant l’attente d’écriture ;
  elle peut empêcher l’émission CPU bien que le canal commande soit disponible.
  C’est un comportement reproduit du RTL, pas la preuve de la cause matérielle.
- Cas7 : écriture pas prête seule ne suffit pas : sans requêteGPU concurrente,
  les32lectures aboutissent. Le contexte de l’arbitre compte.
- Cas3 : CPU32PASS et région effacée restent compatibles avec GPUbusy/done1,
  quand le modèle coupe le retour d’acceptation. Il n’existe pas d’ACK DDR
  d’écriture séparé sur cette interface : b_ready reconnaît l’acceptation.
- Cas5 : CPU32PASS et motif initial intact restent compatibles avec une
  requêteGPU qui ne parvient pas à l’arbitre. Ce n’est pas une attribution auRTL.
- Cas4 : filepleine réellement créée via16requêtes, sans force interne. Dans
  la version revue, CLEAR VALID=1 et56cycles ont offert simultanément les deux
  READY natifs sans accepter l’écriture. Relâcher les retours vide la file et
  permet CLEAR+CPU32. Cet historique scan est synthétique ; le FB R19 étaitoff.
- Cas6 : un retourCPU perdu bloque la lecture avec une seule étiquette et
  une file non pleine. Un timeoutCPU seul ne distingue donc pas les causes.

## Correction de la contre-revue

DeepSeek avait observé le cas4 après8cycles, avant nativeVALID. Les8tests
passaient mais la preuve du blocage de cette requête manquait. La copie
`review_corrected_01` attend VALID puis80cycles, et exige ≥20cycles READY
simultanés durant full. Résultat56. La sortie originale est conservée, ainsi
que le patch. Les sept autres cas sont inchangés. L’ancien rapport est nommé
MODEL_REPORT_ORIGINAL.md : ses valeurs cas4 ne sont plus les valeurs corrigées.

Les instantanés de READY sont des niveaux à un cycle, pas des preuves que ce
niveau est resté constant. Les contrôles hold_* injectés et le compteur de
cycles prêts établissent l’observation temporelle. Les écritures répétées
injectées sont idempotentes ici, mais pas un fonctionnement acceptable.

## Limites pour le futur lecteur carte

Le lecteur ILM est une intervention qui crée du trafic et peut changer
l’arbitrage. Comparer les captures avant/après ; ne pas assimiler un journal
partiel aux valeurs0 en DDR.32lectures réussies prouvent la progression de cette
fenêtre/zone, pas une DDR intégralement saine ni une cause unique du GPU.
Aucune cause physique démontrée : pas de calibration, chronométrie de routage,
AE350, AHB DDR/CDC ou réponses de la vraie IP dans ce banc. Aucun accès carte.

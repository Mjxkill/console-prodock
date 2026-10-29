# Console Pro Dock et Neo

La Pro Dock fonctionnelle doit être conservée pendant le portage Neo.
Lire `ARCHI/COMPATIBILITE_CARTES.md` et `tang/boards/ownership.json` avant
toute modification de source ou de constructeur.

- `shared` signifie utilisé ou destiné aux deux cartes : le nom `prodock-*`
  d'un pilote Linux ne le rend pas spécifique à la Pro Dock.
- Les sources propres aux cartes et les substitutions Neo sont inventoriées.
  Ne pas appliquer un correctif expérimental Neo au RTL commun par défaut.
- Toute modification d'une entrée invalide les résultats locaux précédents.
  Exécuter `python3 tools/run_board_regressions.py --out TESTS/dual_board/<nom-unique>`.
  Corriger ou signaler les échecs ; ne pas réduire la suite pour obtenir PASS.
- Les builds Pro Dock modifiés exigent `--candidate`. Ce marquage n'est pas
  une qualification matérielle. Les builds Neo restent candidats.
- Les tests locaux des deux profils, la synthèse, le timing et les essais sur
  les deux cartes sont des résultats distincts. Quand une carte est éteinte,
  les essais matériels de ses nouvelles versions restent explicitement en attente.
- Ne pas remplacer les références Pro Dock G22r0 / NEBULA R17, ni leurs
  fichiers protégés, par un build Neo ou un candidat non validé sur Pro Dock.
  La référence historique conserve ses limites de timing/USB documentées.
- Avant un essai carte, identifier la carte et le bitstream exacts. Ne pas
  toucher à la Pro Dock pour une expérience Neo. Ne pas lancer deux sondes
  simultanées sur la même carte ; respecter les verrous de diagnostic.
- Ne pas supprimer les builds protégés ou les archives de référence lors
  d'un nettoyage. Ne pas arrêter les compilations d'autres projets.

Les fichiers communs restent uniques ; l'inventaire et les profils définissent
leur utilisation. Les différences d'un snapshot expérimental doivent être
documentées sans prétendre que les deux cartes emploient déjà le même RTL.

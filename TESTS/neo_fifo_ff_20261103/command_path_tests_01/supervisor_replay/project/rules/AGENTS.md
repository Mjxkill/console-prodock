# Console Pro Dock et Neo

La Pro Dock fonctionnelle doit être conservée pendant le portage Neo.
Lire `ARCHI/COMPATIBILITE_CARTES.md` et `tang/boards/ownership.json` avant
toute modification de source ou de constructeur.

## Diagnostic avant correction — règle impérative de Michael

- Avant toute correction, diagnostiquer avec les moyens disponibles pertinents :
  documentation, sources et paramètres exacts, simulations, compteurs, mesures
  temporelles, JTAG et observations matérielles. Ne pas attribuer une panne au
  timing, au routage ou à une IP sans éléments qui discriminent les causes.
- Séparer explicitement faits mesurés, hypothèses et conclusions. Chaque essai
  indique la cible/version, les conditions, les unités, les résultats attendus,
  les résultats observés, les preuves et les limites. Une mesure inconnue reste
  inconnue ; une simulation réussie ne qualifie pas le matériel.
- Concevoir des expériences qui permettent de départager les hypothèses, en
  contrôlant les variables et les effets de l'instrumentation. Pour les E/S,
  distinguer volume demandé, volume réellement transféré, cache, anticipation,
  métadonnées, reprises et temps passé dans chaque étape pertinente.
- L'instrumentation diagnostique doit être bornée et réversible, conserver les
  preuves et les références, et respecter les verrous matériels. Ne pas la
  présenter comme une correction. Les correctifs candidats restent hors carte
  tant que le diagnostic ne justifie pas le changement proposé.

## Règle d’or — simplicité, responsabilités et cause démontrée

Cette règle s’applique à tout le projet : RTL FPGA, pilotes, firmware, Linux,
jeux, outils, tests, constructions et travaux délégués.

- Une fonction remplit son contrat et sa responsabilité explicite. Séparer
  configuration, travail normal, diagnostic et récupération ; aucun effet de
  bord caché pour compenser une erreur située ailleurs.
- **Pas de correctif pour une erreur dont la cause n’est pas établie.**
  Identifier le défaut par la documentation, une observation discriminante ou
  une reproduction ; expliquer le mécanisme causal et prévoir un test qui
  échoue avant la correction et réussit après. Une hypothèse seule ne suffit pas.
- Quand la cause reste inconnue, poursuivre le diagnostic. Ne pas empiler des
  conditions, états mémorisés, délais, reprises, resets ou verrous pour donner
  l’apparence d’un succès. Pour la Neo notamment, changer le placement/routage
  ou multiplier les bitstreams sans hypothèse testable n’est pas une correction.
- Une instrumentation expérimentale doit annoncer la question qu’elle tranche,
  ses effets et ses limites. La conserver distincte d’un correctif. Une amélioration
  observée sans cause démontrée reste un résultat de diagnostic, pas une résolution.
- Propager les erreurs avec leur contexte. Ne pas transformer un échec en succès,
  ignorer silencieusement un paramètre, masquer un résultat négatif ou contourner
  un test. Refuser explicitement ce que l’interface ne prend pas en charge.
- Choisir le code le plus simple qui respecte le contrat. Toute synchronisation,
  reprise ou protection doit répondre à une nécessité identifiée ; supprimer
  les mécanismes et abstractions inutiles après vérification de leurs usages.
- La revue évalue séparément fonctionnement et qualité de conception. Des tests
  PASS ne suffisent pas si le contrat est contourné ou la cause reste inexpliquée.

## Compatibilité et validation

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

## Interfaces C et pilotes SPI

- Règle de Michael : les `.h` du code développé exposent types, constantes et
  prototypes ; aucune implémentation de fonction, même `static` ou `inline`.
  Compiler les implémentations `.c` séparément, sans inclure un `.c` dans un
  autre. Les bibliothèques fournisseur et archives de preuve restent identifiées.
- Séparer initialisation/configuration, transfert normal et récupération après
  erreur. Ne pas réinitialiser ou reconfigurer systématiquement un périphérique
  sans exigence documentée. Utiliser des noms explicites pour registres et bits.
- Pour le SPI AE350 : l'implémentation commune maintenue est
  `linux/drivers/prodock-spi-pio.c`. Les anciens snapshots de diagnostic ne
  constituent pas une autre source courante. Un constructeur doit identifier
  exactement le pilote et le cœur effectivement compilés.

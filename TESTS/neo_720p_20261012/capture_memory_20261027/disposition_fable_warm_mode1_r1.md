# Disposition de la revue Fable UART mode 1

Revue : `TESTS/assisted_reviews_20261026/neo_fable_warm_mode1_r1/answer.txt`.
Elle porte sur le paquet figé SHA
`59742b195c5bc1bd3f57ef33c982ce2c6967bf6563d889ed1541dbb21034e886`,
contenant le contrôleur initial `239c4b5d…`. Le contrôleur relu par le parent
est `f27c18c63aa04bf7493d14ecd0c3b26b5a3fe1d438757ef616beba1e0b5dd672`.
Aucun résultat matériel n'est revendiqué dans cette disposition.

Après cette disposition et sur demande du parent, seules les corrections
de reporting ont été appliquées : SHA final
`4ac4b7dbd0648192149795dcbbb4cf2d9f9613c360d7e1fcf239cbf3099ca408`,
16 tests locaux PASS. La restauration est tentée au plus une fois avec
signaux protégés, les NCP bruts sont écrits avant assertion et la clé
`r19_reset_observed_after_frame` remplace une déclaration de preuve d'époque.
L'essai matériel ultérieur du parent est consigné séparément dans
`warm_mode1_20261027_094017/` ; la revue initiale n'est pas réécrite en succès.

## Points retenus

- Le témoin NCP 2/2 vers 0/0 démontre un reset du domaine, pas la lecture
  directe de l'époque UART. Une perte spontanée de calibration/reset dans la
  même fenêtre n'est pas logiquement exclue. La conclusion doit conserver
  cette limite même après contrôle des lignes série.
- Le contrôleur initial incluait ouverture et fermeture dans la fenêtre de
  causalité. **Déjà corrigé avant réception de la revue** : la version
  `f27c18…` vérifie 2/2 après ouverture, puis 0/0 avant fermeture, dans le même
  handle. Elle vérifie à nouveau 0/0 après fermeture. Cette méthode est plus
  discriminante qu'un premier cycle d'ouverture vide suivi d'une seconde
  ouverture contenant la trame.
- Une restauration qui échoue dans la branche négative peut être rappelée
  depuis le gestionnaire externe. L'assertion de journal existant empêche
  effectivement une seconde programmation, mais le rapport d'erreur devient
  inutilement confus. Un unique drapeau `restore_attempted` et une protection
  contre les signaux dans `restored()` sont des corrections locales utiles.
- La garde Tcl imprime actuellement les compteurs seulement après ses
  assertions. En cas de non-reset, enregistrer les valeurs brutes avant
  assertion rendrait l'échec exploitable sans inférer sa cause.
- `CPU_ROM_execution_after_reset=True` était excessif. **Déjà corrigé** en
  `CPU_ROM_restart_possible=True`, indépendamment de
  `CPU_resume_command=False`. Chaque reprise exige le parking vérifié.

## Réserves sur les suggestions Fable

- Le commentaire proposé « trame reçue sans reset » si les compteurs restent
  2/2 est incorrect : cela prouverait seulement l'absence de reset observé,
  pas la réception. Une trame perdue dans le relais/parseur demeure possible.
- Une lecture de `heartbeat_count` date grossièrement l'activité depuis le
  reset ; elle n'identifie pas sa cause. Elle ne remplace pas une époque
  UART exportée.
- Il n'existe ici aucune preuve que DTR/RTS soient câblés au reset FPGA ;
  l'énoncé général sur des ponts Sipeed ne doit pas être transformé en fait
  sur cette carte. Le contrôle dans le handle traite cette possibilité.
- Le délai de 30 s est une borne diagnostique, pas une promesse d'achèvement
  pour 100 tours de timeout. Les ARM/SNAP normaux doivent répondre rapidement.
  Un timeout doit rester un échec technique ; augmenter automatiquement la
  borne à 60 s n'est pas nécessaire pour le premier essai.
- Les différences de texte `left_state` ne sont pas un défaut d'essai. Une
  future ancre doit identifier explicitement ce résultat et ses champs,
  plutôt que réutiliser une ancienne description comme ABI implicite.

## Preuves présentes hors du paquet compact

Le parent a relu les imports `board_trial_r21`, `board_trial_r19`, le
contrôleur matériel et les hash FS. `local_plan()` lie le FS candidat à la
revue post-routage et le FS R19 à son SHA exact. La présence réelle de
`u_reset_trial` et l'identité de ses primitives/connexions entre R19 et R21
sont établies par `cpu_route_compare_01/result.json` ; l'hypothèse « R19
ne contiendrait pas le parseur » n'est donc pas retenue.

La connexion `cpu_reset_n` du séquenceur est `soc_dbg[0]`, c'est-à-dire la
sortie `init_sync[1]` envoyée aux entrées reset du bloc AE350, et non
`EXTS_HRSTN`. Une horloge AHB absente peut empêcher cette synchronisation et
laisser le hold actif ; une absence de reprise ne distingue pas ce cas d'une
trame non reçue. Aucun modèle ne prouve une cause physique sur la seule revue.

Le helper `hw.run_child` termine son groupe enfant sur timeout ; les appels
du contrôleur restent séquentiels. Les tests locaux sont des mocks de contrôle
de flux, pas une simulation UART ou une qualification matérielle. Ils
conservent cette portée dans leur JSON.

# Disposition de la contre-revue et limites physiques R21r1

Le routage a terminé sans accès matériel. Le résultat complet est
`postroute_01/result.json`, SHA-256
`a57b3c69e8cb4bf7343fe0361b48e32b3e7b7a86280a43e5d9de1e58b737665c`.
Le bitstream est `2fd6f3b01bee26a835aefcef3c34712de649f0af4e1fa24ff5bb4983430200d7`.
Il reste **FAIL global** : setup −2,602 ns / 56 endpoints, hold +0,124 ns,
recovery +0,381 ns, removal +0,168 ns. Aucun chargement n'est autorisé par
le script d'audit ; la décision diagnostique appartient au contrôleur root.

## Disposition de Fable

La seconde revue est conservée dans
`TESTS/assisted_reviews_20261026/neo_fable_r21_physical_audit_r2/answer.txt`.

1. Les identités des pilotes sont maintenant comparées même lorsque le nom
   du net d'une pin ne change pas. Sur ce résultat, aucune équivalence par
   renommage de net n'a été nécessaire : la liste `alias_only_parent_changes`
   est vide. Le parent comporte 143 599 primitives ; 143 366 sont hors helper.
   Toutes leurs pins et tous leurs paramètres sont conservés, sauf les sept
   LUT d'entrée `shadow` du header diagnostic explicitement vérifiées.
   Les cinq primitives nouvelles hors helper sont la liste blanche exacte.
2. Chaque bit de `held` est relié au FF mappé attendu, puis à la LUT de
   `shadow` attendue. Les alias 50→49, 62→60 et 63→60 et les constantes 55/61
   sont issus du helper synthétisé exact. Les origines SDF correspondent à
   ces FF, et non simplement à un préfixe de nom.
3. Une pin constante n'est admise que si elle était constante dans le helper
   synthétisé. Il n'existe aucune constante inattendue. Chaque FF des groupes
   capture/sticky/held a au moins une borne de setup calculée.
4. Les types des FF sont contrôlés : les 352 FF observateur sont DFFCE. Le
   helper physique conserve aussi les types, INIT et connexions internes de
   ses 249 primitives synthétisées (233 auparavant). Une origine DFFN n'est
   pas assimilée à une origine positive.
5. Chaque IOPATH LUT/INV attendu et chaque interconnexion non constante des
   cônes parcourus doivent exister. Aucun trou, origine inconnue, clock/setup
   absent, boucle combinatoire ou origine asynchrone n'est trouvé dans ces
   cônes. Les arcs présents sont tous parsés, y compris les deux triplets
   montée/descente lorsqu'ils existent.
6. L'ajout proposé de skew GPU/HCLK à la borne `held→shadow` n'est pas requis
   par le protocole utilisé : le budget est exprimé en deux cycles destination
   supplémentaires **après** reconnaissance de l'ACK synchronisé, et non en
   relation de phase entre deux clocks synchrones. `held` et ACK sont lancés
   au même front GPU. Cette borne conservatrice inclut CQ, tout le chemin
   de données et le setup de destination. Elle reste distincte du max_delay
   SDC de 8 ns et ne supprime aucun échec STA.

La table des pilotes du script connaît Q/F/O/G/V. Des sorties COUT/SUM,
DO/DOA/DOB, Q0/Q1 et CLKOUT existent aussi dans l'application. Elles ne sont
pas utilisées pour accepter une équivalence : leurs primitives et leurs
pins restent exactement identiques et aucune alias-only n'est acceptée.
Le contrôle actuel ne prétend donc pas constituer un prouveur général de
renommage pour ces primitives.

Les propositions de pseudo-code Fable ne sont pas recopiées aveuglément :
les vrais suffixes de FF sont notamment différents de ses exemples.
`timing_checks` exige réellement les quatre tableaux Setup/Hold/Recovery/
Removal, et l'audit exige désormais leurs quatre clés exactes. Les violations
interdomaines restent dans la STA globale ; aucun groupe n'est exempté.

## Sens et limites des bornes de capture

- Période GPU 13,333 ns et bus 12,500 ns lues dans le SDC **et** comparées au
  tableau STA ; il s'agit des contraintes, pas d'une mesure sur carte.
- Les 48 FF at/after, quatre sticky et 59 held sont parcourus sur D et CE.
  Les 64 shadow sont contrôlés bit à bit. La couverture est une garde.
- La borne conservatrice est `T + min(CLK_destination) − max(CLK_source)
  − max(CQ + combinatoire + routage) − max(setup)`. Les extrêmes de corners
  sont combinés pessimement, sans arrondi préalable à la décision.
- Minimum obtenu : **+0,334 ns**, depuis `engine_resetn_6_s0/Q` vers
  `after_event_16_s1/D`. Le maximum CQ+chemin est 10,886 ns ; le setup0,057 ns.
- `held→shadow` : CQ+chemin maximum2,684 ns, marge protocole minimum22,259 ns
  sur le budget25 ns après déduction du setup.
- Ce calcul SDF est une vérification locale conservatrice, pas une seconde
  implémentation de STA complète. Il ne qualifie ni le moteur GPU entier,
  ni la DDR, ni le fonctionnement physique des réseaux d'horloge.
- Les arcs de reset manquants dans le SDF fournisseur ne sont jamais pris
  égaux à zéro. Les contrôles asynchrones sont listés dans le résultat ; la
  recovery/removal est celle de la STA globale. La séquence de reset et les
  synchroniseurs d'ARM/SNAP restent couverts par leurs simulations et leur
  structure, pas par une simulation analogique de métastabilité.
- Les flags observent les signaux réellement présentés au helper ; ils ne
  prouvent pas que les FSM fonctionnelles ont correctement capturé leurs
  propres données. Notamment `v1_pending_s2→v1_accepted_s0` reste en violation
  setup de **−0,362 ns**, et les chemins resetqualifier→blitter atteignent
  **−0,600 ns**. Ces défauts de timing restent explicites pour interpréter
  tout prochain essai COPY/CLEAR.
- L'ajout de charges d'observation et le reroutage peuvent modifier le
  symptôme. Les deux essais indépendants doivent d'abord reproduire ou
  constater la disparition du symptôme R19 avant d'interpréter les traces.

Les deux avertissements PR1014 (`clk_d`, `ae350_tck_d`) sont les mêmes que
sur R19 ; les huit clocks PRIMARY obligatoires sont conservées. Occupation :
86 187/138 240 logique, 56 082/139 095 registres, 263/340 BSRAM, 176,5/298 DSP.
Aucune nouvelle qualification Pro Dock n'est revendiquée ; sa référence
n'a pas été modifiée.

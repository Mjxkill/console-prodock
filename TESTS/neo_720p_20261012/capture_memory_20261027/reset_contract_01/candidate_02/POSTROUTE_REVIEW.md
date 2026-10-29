# R21r2 coupled : revue du routage, 27 octobre 2026

Le bitstream `33589f89e8f6a57e683b35723e2ab2cc5862e121ee9f97636f00ab3768db2710`
est routé, mais sa qualification globale reste **FAIL** : setup −4,813 ns,
hold +0,124 ns, recovery −2,680 ns, removal +0,355 ns. Aucun essai matériel
n'est exécuté ni autorisé par cette note. Les trois audits initiaux sont conservés
dans `postroute_01`, y compris leurs FAIL.

## Intégrité du changement

- Hors `u_reset_trial`, aucune modification inattendue de primitive, broche ou INIT
  face à R21r1. Les deux LUT et les deux CLEAR correspondent au correctif relu.
- L'audit strict du helper signale les transformations physiques usuelles, puis
  `postroute_helper_equivalence_02/result.json` établit leur équivalence binaire :
  4 INV deviennent des LUT1 INIT1 et 47 ADD MODE0 permutent I0/I1.
  Le graphe de toutes les autres broches et tous les paramètres sont identiques.
  Les modèles officiels couvrent toutes les entrées binaires et des corruptions
  négatives sont détectées. Trois différences X/Z du modèle ADD sont explicitement
  conservées ; aucune identité à quatre états universelle n'est revendiquée.
- Le FAIL du profil DDR est hérité : son contrôle strict signale déjà le fichier
  `ae350_soc.v` dans R21r1 face à G22r0. Entre R21r1 et R21r2, les 20 fichiers du
  profil DDR sont identiques, ainsi que 13 268 primitives routées et 13 358 paramètres
  sous `u_soc/g_ddr`. Le raccordement `rst_key_n` est modifié dans le top seulement.
  Preuve : `postroute_ddr_identity_01/result.json`. Cela ne qualifie pas la DDR physique.

## Recovery du reset CPU

La violation concerne **les deux étages**, y compris le second :

```
PLL_INIT/state_1_s0.Q (clk50)
  → pll_ae350_lock_s (LUT4 INIT8000 : state111 et LOCK brut)
  → neo_qualified_pll_lut (INIT2 : masque par ae350_rst_sync[1])
  → u_reset_trial/n261_s1 (INIT7 : !available)
  → u_reset_trial/release_request_d_s (INIT1000)
  → u_soc/neo_qualified_clear_lut (INITB)
  → init_sync_[0,1].CLEAR (bus80)
```

Ce chemin ne traverse pas la primitive PLL ; l'état du séquenceur PLL masque sa
sortie LOCK. Le rapport STA donne −2,680 ns vers les deux CLEAR, depuis clk50 vers
bus80 avec la contrainte existante `set_max_delay 8`. Le D du premier étage est
également négatif, −2,287 ns. Les états PLL_INIT 0 et 2 ont d'autres violations
recovery de −2,376 et −2,400 ns. Aucun faux chemin n'a été ajouté.

Dans R21r1, les CLEAR avaient pour seul pilote `ae350_rst_sync[1]`, donc un départ
bus80 et une arrivée bus80 : recovery +8,851 ns, removal +1,416 ns. Le correctif
introduit réellement une nouvelle autorisation asynchrone sur ces CLEAR ; cette
différence n'est pas dissimulée derrière le nom de la ressource de routage.

La sensitisation fonctionnelle est distincte du chemin STA. Les 512 combinaisons
binaires des LUT routées prouvent que `delay_done=0` impose `trial_request=0` et
`CLEAR=1`, quels que soient l'état PLL_INIT, LOCK et les autres entrées. Au démarrage
légal, `delay_done` est initialisé à zéro et ne monte qu'après la qualification
complète. La première montée du LOCK masqué ne peut donc libérer ce reset pendant
les 50 ms. Lors de l'expiration légale, la source active est `delay_done` en clk50.

Pour `delay_done→CLEAR`, les données SDF donnent 0,961 / 1,621 / 2,278 ns. En combinant
les pires coins d'horloge, l'exigence recovery exportée de 0,313 ns et la borne8ns
existante, la borne conservatrice est +1,735 ns sur les deux étages. **C'est une
borne calculée sous cette contrainte, pas une preuve de phase asynchrone ni un
résultat STA supplémentaire.** La chaîne réelle est vérifiée, et les exigences
proviennent du SDF. Les violations STA originales restent FAIL.

Preuves exactes, valeurs par coin et comparaison parent :
`postroute_release_paths_02/result.json`.

## Couverture restante et portée d'un éventuel essai

Les quatre trajets D entre étages reset ont des bornes setup conservatrices
positives : AE350 +8,894 ns, SoC +9,590 ns, ready_meta +16,291 ns,
reset_meta +16,291 ns. Leurs huit FF sont tous identifiés ; aucun arc ou horloge
manquant dans ces quatre cônes n'est ignoré.

Cela ne couvre pas : largeur minimale de capture du LOCK asynchrone dans le
silicium, métastabilité, PRESET de la première chaîne exclu par les exceptions
héritées, reset interne du hard CPU absent de l'export SDF, ni tous les chemins
CPU/ILM (deux familles setup négatives à −0,298 et −0,182 ns).

L'observateur reste non qualifié pour ses captures dynamiques : son audit calcule
une borne setup sample de −1,938 ns. Les observations D/Q/CE et les quatre événements
mémoire ne doivent pas être utilisés pour tirer une nouvelle conclusion GPU sur
ce routage. Un éventuel essai borné CPU garé / mire demeure un **diagnostic**, décidé
séparément par l'opérateur root, et ne transforme aucun FAIL en PASS.

Les causes des échecs physiques antérieurs de R21r1 ne sont toujours pas établies
par ces simulations ou ce routage. Pro Dock et Neo R19 n'ont pas été touchées par
ces audits.

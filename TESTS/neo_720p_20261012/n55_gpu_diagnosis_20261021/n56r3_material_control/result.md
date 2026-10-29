# N56r3 : compilation terminée, qualification FAIL

Le constructeur revu a terminé avec le code 0. La première tentative dans
le bac à sable avait échoué avant PnR sur l'accès AF_NETLINK/hostid de la
licence ; son dossier est conservé séparément. La relance du même constructeur
hors bac à sable a produit tous les rapports et le bitstream. Aucun accès
matériel, chargement ou changement des sources communes n'a été effectué.

Bitstream : `tang/impl/console_neo_n56r3/impl/pnr/console_neo.fs`.
SHA-256 : `77a76cdc6d16aaa34a939296cc74ed7f6e29980682ac2756b6b2658ae443fbe2`.

| Contrôle temporel | Marge minimale |
| --- | ---: |
| Setup | −0,453 ns, 2 endpoints |
| Hold | +0,124 ns |
| Recovery | +0,306 ns |
| Removal | +0,049 ns |

Les deux violations setup sont dans l'observation CDC, avec la borne de
8 ns inchangée :

- `u_accel/u_v1/u_pixels/packet_25_s0/Q` →
  `u_gpu_debug/observe_words_s1_57_s0/D`, −0,453 ns ; source R39C41[3][B],
  arrivée R43C143[0][A], tNET 8,149 ns.
- `u_accel/u_v1/u_pixels/packet_17_s0/Q` →
  `u_gpu_debug/observe_words_s1_49_s0/D`, −0,278 ns ; source R51C41[0][B],
  arrivée R50C136[0][B], tNET 7,969 ns.

Les chemins détaillés commencent aux lignes 16601 et 16643 du rapport `.tr`.
Les lignes 139/140 en donnent le résumé. Les délais ne sont pas réduits à
leur tNET : le calcul complet conserve clock-to-Q, skew et setup.

**L'échec n'est pas seulement temporel.** Le routeur a retiré le CE matériau
`u_accel/u_v1/n56864_3` des LW, mais a ajouté
`gpu_debug_state[48]` aux LW, malgré le `LOCAL_CLOCK` existant sur ce nom.
Ce net est `engine_resetn[4]`, utilisé pour le reset du moteur pixel
`u_v1/u_pixels` : il appartient au chemin fonctionnel. L'audit
`gpu_reset_tree` rejette donc la construction. La dérogation de diagnostic
réservée au setup seul ne s'applique pas à ce résultat.

L'audit spécialisé des quatre contrôles passe : types/pins/INIT des pilotes
et ensembles complets de charges inchangés (312, 283, 2, 253), tous absents
du tableau des ressources globales. La seule source changée depuis N56r1
est le CST avec la contrainte matériau revue. Netlist, SDC, horloges, DDR et
initialisations restent identiques. Tous les autres audits de qualification
passent. Les CE géométriques `n57378_3` et `n59467_5` restent sur LW ; cette
expérience ne démontre toujours pas leur fonctionnement en rendu.

Rapports autoritatifs : `tang/impl/console_neo_n56r3/qualification.json` et
`local_controls_audit.json`. Le résultat condensé, les empreintes et les
chemins négatifs sont conservés dans `result.json` à côté de cette note.
Le build n'est ni promu ni chargé.

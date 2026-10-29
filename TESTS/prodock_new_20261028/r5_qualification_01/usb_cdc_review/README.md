# R5 USB : revue contradictoire CDC/reset, en attente après bring-up

**R5 reste non fermé en timing.** Les deux pires chemins de données aboutissent
à des premiers étages de synchronisation. Les pires recovery/removal portent
sur de véritables broches de reset asynchrone, dont la protection fonctionnelle
doit être étudiée séparément. Aucun de ces constats ne démontre la cause de
l'absence d'énumération observée par root sur la nouvelle Pro Dock. Le contrôle
G22 exact sur la même carte est prioritaire pour ce problème matériel.

Cette revue n'a modifié ni RTL, ni SDC/CST, ni bitstream; aucun accès matériel
ou lancement Gowin. Elle porte sur R5 VO `7d615031…`, sources USB identiques
à G22. La différence de SDC concerne cinq requêtes de rapport supprimées,
pas de nouvelles contraintes. La qualification R5 parente reste inchangée.

## Faits retenus et limites

| Chemin R5 | Slack | Résultat de la lecture |
|---|---:|---|
| PHY highspeed → `hs_s[0]/D`, bus80 | setup −7,789ns | Premier étage suivi de `hs_s[1]`, CLK AHB, CLEAR=0, CE=1. Le CDC voulu est présent; ce seul fait ne qualifie pas son MTBF/placement. |
| AHB Gray → `wr_gray_s1[1]/D`, PHY | hold −3,451ns | Premier étage suivi de s2. Encodage Gray avant, décodage après s2. Cette vérification d'un bit ne constitue pas un contrôle complet du skew du bus Gray. |
| `rst_usb` PHY → `gather[7]/CLEAR`, bus80 | recovery −12,298ns | Connexion asynchrone directe via LUT2 INIT=B, pas un premier étage de synchroniseur de données. |
| `phy_lock_reset` clk50 → compteur PHY/CLEAR | removal −2,265ns | Assertion asynchrone; le séquenceur maintient ensuite count=0/reset=1 tant que lock_sync[1]=0, puis compte64cycles. Garde fonctionnelle utile, pas preuve analogique. |

La LUT B calcule `n6_5 = rst_usb || !vid_hrstn`. L'inventaire direct du **VO
complet** trouve161FF AHB et105FF PHY sur ce net, plus9FF PHY sur
`phy_lock_reset` (275connexions répertoriées dans
`owner_review/raw_reset_fanout.json`). Les shifters de libération locale font
partie du compte, comme des données et des registres de contrôle. Le compte
est celui des broches directement raccordées; il ne couvre pas les descendants
combinatoires d'autres resets ni tous les chemins négatifs du design.

`vid_hrstn` lui-même vient de la copie registrée EXTS_HRSTN dans EXTS_HCLK
(`ae350_soc.v:330–331`); la STA identifie ce domaine comme bus80. Le reset
composé n'est donc pas seulement une traversée PHY→AHB : sa composante
`vid_hrstn` peut aussi changer hors du domaine PHY. Le reset du contrôleur
USB/PHY n'est pas construit avec ce `vid_hrstn`; ne pas extrapoler le défaut
potentiel de ses périphériques MSC/UTNA à l'énumération complète.

Les gardes `hr/ur/uh/hu` maintiennent les FIFO et les transferts désactivés
jusqu'à observation des deux horloges. Dans MSC, `hreset` force **gathered**
(nombre d'octets) à0; **gather** (32bits de données) reste inchangé tant
qu'aucun octet n'est déplacé. Son CE n'est donc pas constamment actif.
En revanche des états AHB (`write_pending`, `read_pending`, `tx_room`, etc.)
peuvent évoluer avant la fin du garde local. Ni «tout est remis à zéro par
hreset» ni «aucun CE n'est utilisé» n'est une description correcte.

Le modèle officiel Gowin est explicite : `DFFRE.RESET` est **synchrone**,
prioritaire sur CE. `DFFCE.CLEAR` est asynchrone. Le modèle timing publie pour
ce dernier un `$recrem(negedge CLEAR,posedge CLK)` sans condition CE.
La seule présence de `DFFRE.RESET` dans la FIFO n'est donc aucune anomalie
de mapping de son reset synchrone. Aucun défaut d'IP FIFO n'est établi ici.

## Contre-avis GLM et corrections indépendantes

Mission OpenCode **exécution**, modèle demandé/observé `glm-5.3-flash`,
run `prodock_r5_usb_cdc_glm_20261029_01` :492,857s,30requêtesAPI,39outils,
une session. Trois tests agent (deux échecs puis PASS), baseline superviseur
FAIL puis validation finale PASS. Les neuf faits structuraux demandés sont
retrouvés; les processus isolés ont tous terminé et les entrées sont intactes.
Le rapport et le code GLM sont conservés sans correction dans
`glm_execution/isolation/tree/owned/`.

La revue humaine indépendante **n'accepte pas son rapport technique en l'état** :

1. Sa section FIFO/U4 appelle DFFRE.RESET asynchrone et envisage un changement
   de sémantique par Gowin. Le modèle officiel le réfute directement.
2. Il confond remise à zéro de gathered et gather, puis affirme une absence
   générale de CE. Le RTL et le CE physique du gather réfutent cette conclusion.
3. Il suggère un dysfonctionnement de `set_clock_groups` ou `-add` pour
   expliquer PHY↔bus80. Les groupes actuels n'opposent jamais directement
   ces deux horloges. Les exceptions ne se déduisent pas transitivement par
   une troisième horloge. Modifier l'ordre de création de sclk n'est pas un
   test discriminant justifié par ces faits.
4. Il appelle G22 un build fermé et suppose des contraintes différentes.
   G22 a ses limites historiques documentées; la différence présente de SDC
   n'est que la suppression des requêtes de rapport. Ce contexte n'était
   pas intégralement fourni dans son paquet; ces extrapolations sont retirées.
5. Les gardes ne prouvent pas une perturbation limitée à un cycle ni une
   incertitude «±1cycle inoffensive» après violation recovery/removal.
   L'absence de panne n'est pas déduite d'une simulation numérique.
6. Les tests fixes valident neuf champs, pas chaque phrase du rapport.
   L'affirmation que toutes ses conclusions seraient re-dérivées par le
   validateur est donc excessive. Des parties du sourceclockchain et le
   modèle officiel des primitives n'étaient pas dans le paquet du modèle;
   la présente revue les complète sans lui attribuer une lecture impossible.

Les observations structurales sont retenues après correction; pas de patch
ou de waiver repris automatiquement, pas de note de qualité automatique.
`owner_review/check_owner_facts.py` reproduit les corrections de sémantique,
le comptage exact et les identités des sources officielles.

## Prochaine vérification discriminante, après bring-up

1. Pour les **données**, finir le contrôle de tous les premiers étages et de
   leurs seuls consommateurs, du timing s1→s2 et du skew/maxdelay des pointeurs
   Gray. Une éventuelle exception devra viser les traversées voulues, sans
   cacher les chemins de reset. Aucun changement de contraintes maintenant.
2. Pour les **resets**, classer les275pins directs entre shifters de
   libération, états fonctionnellement maintenus et états libres d'évoluer.
   Vérifier la propagation de chaque source (`vid_hrstn`, `rst_usb`,
   `phy_lock_reset`) séparément, y compris avec horloge arrêtée/reprise.
   Les transitions dans une simulation avec délais servent à trouver des
   défauts fonctionnels; elles ne certifient pas la métastabilité.
3. Si l'audit établit qu'une libération brute atteint un état utilisé trop
   tôt, préparer un **candidat** avec assertion asynchrone et libération
   synchronisée propre à chaque domaine, en conservant les gardes croisées.
   C'est une piste de conception à éprouver, pas un correctif déjà prescrit.
   Toute nouvelle source commune exige les tests des deux profils et les
   validations distinctes. La référence G22 reste intacte.
4. Après fonctionnement de base de la nouvelle carte, root pourra corréler
   redémarrages/rebranchements et snapshots. MSC+04 fournit lostbit7,
   seen_bus_resetbit2, seen_bot_resetbit3. Ne pas transformer des lectures
   de collecte en commandes ou en lectures destructives +08/+20. L'absence
   d'événement d'énumération seule ne tranche pas un problème MSC/UTNA.

Aucun de ces travaux n'est un motif de lancer un routage spéculatif pendant
le contrôle SD en cours. Les minima négatifs restent consignés comme tels.

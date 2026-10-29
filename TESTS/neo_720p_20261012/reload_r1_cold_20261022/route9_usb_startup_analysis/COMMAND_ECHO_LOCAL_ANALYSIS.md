# N56r8 : commande ARM appliquée, écho bit0 absent

Le [second essai à chaud](n56r8_usb_capture_02_warm/trial.log) conserve le
FAIL et apporte enfin les deux banques brutes identiques. ARM, séquence3,
renvoie `[55544e41,1,0,…]` au lieu de commande1 ; DISARM, séquence4,
renvoie `[55544e41,1,4,…]`. L'absence du bit0 est donc reproduite après un
premier disarm, pas seulement dans la première capture depuis reset.

La banque ARM contient l'ancien ticks `891fa9` et armed=0 ; celle du
disarm contient `8923f4` et armed=1. Cela concorde avec la capture de l'état
pré-clear puis un armement effectif. L'écho incorrect reste un défaut du
résultat de diagnostic, pas un résultat accepté sous une autre convention.

## Trajet exact dans le VO N56r8

Le VO est figé au SHA
`33c919d5c8ab6e90ec6b68f44849ff9d6f2c5682a40192d12c55298494afccc9`.
Les noms suivants sont préfixés `u_usb_idle_trace/`.

| Étape | ARM bit0 | DISARM bit2 |
|---|---|---|
| Sortie FIFO commande | `u_commands/head_0_s0/Q` → `command[0]` | `u_commands/head_2_s0/Q` → `command[2]` |
| Capture | `snapshot_64_s0/D` → `snapshot[64]` | `snapshot_66_s0/D` → `snapshot[66]` |
| Horloge / CE / reset / INIT | `phy_clk / n1170_3 / n5312_3 / 0` | Identiques |
| Première LUT du multiplexeur | `n181_s43/I1` | `n179_s52/I2` |
| Dernière LUT | `n181_s33/F` → `n181_37` | `n179_s33/F` → `n179_37` |
| RAM de réponse | SDPB `u_replies/g_inferred_storage.mem_g_inferred_storage.mem_0_0_s`, DI0 → DO0 | Même SDPB, DI2 → DO2 |
| RAM de banque, mots0..15 | RAM16SDP4 `bank_bank_0_0_s`, DI0 | Même RAM16SDP4, DI2 |
| Adresses RAM de banque | WAD=`receive_index[3:0]`, RAD=`address[5:2]` | Identiques |
| Autorisation RAM de banque | WRE=`bank_245`, CLK=`vid_hclk` | Identiques |

Références du VO : capture lignes171257–171280, premier multiplexeur
160970 et161034, SDPB185601–185620, banque179081–179091. La banque mots16..31
emploie une seconde RAM16SDP4, qui reçoit aussi reply[3:0]. Les quatre
bits d'un mot partagent ses adresses et son WRE ; leur stockage est distinct.

`command[0]` a deux charges directes : D de snapshot64 et I0 de
`n5310_s1`, qui produit le clear des compteurs. Le fait que l'armement
agit prouve l'effet de cette seconde branche ; il ne mesure pas la valeur
capturée par snapshot64 au même front. Le bit0 du chemin commun n'est
pas globalement forcé zéro : ID/version et ticks impairs passent dans les
mêmes lanes de RAM pour d'autres mots.

## Vérification logique locale, sans compilation

[trace_command_echo.py](trace_command_echo.py) a reparsé les primitives
routées, leurs INIT et les connexions. Sa
[preuve JSON](command_echo_cone.json), SHA
`4b49f4b22c286ff54204ded65ae1bf8be84bafa4fcb79301ccf78d9697658c89`,
conserve 148 primitives et 335 interconnexions SDF avec fronts et
min/typ/max séparés.

Pour `send_index=2`, l'évaluation conservatrice des LUT établit :

- DI0 du SDPB vaut snapshot64, pour snapshot64=0 **et**1 ;
- DI2 du même SDPB vaut snapshot66, pour snapshot66=0 **et**1.

Tous les autres états séquentiels terminaux sont laissés libres {0,1}.
Le résultat unique dans chacun des quatre cas exclut une constante0 ou
un mauvais décodage booléen du mot2 dans ce multiplexeur. Ce contrôle à
délai nul n'établit pas la valeur réelle du FF, les marges temporelles,
le contenu matériel des RAM ou la fiabilité de la capture.

Quelques interconnexions SDF, min/typ/max ns, identiques entre fronts :

| Segment | Min / typ / max |
|---|---|
| command0/Q → snapshot64/D | 0,519 / 0,787 / 1,054 |
| command2/Q → snapshot66/D | 0,443 / 0,670 / 0,898 |
| command0/Q → branche clear n5310/I0 | 0,320 / 0,490 / 0,660 |
| dernière LUT bit0 → SDPB DI0 | 0,592 / 0,967 / 1,342 |
| dernière LUT bit2 → SDPB DI2 | 0,638 / 1,054 / 1,469 |

Ce sont des délais de liaisons, **pas des slacks**, ni des chemins
complets launch/capture. Ils ne permettent pas de désigner une cause.

## Protocole discriminant proposé, non exécuté

Les gardes N56r8/parking/mire, l'identité Neo/ESP, le verrou, 100 kHz,
le timeout, l'ID/statut idle, la cohérence double lecture, le compteur
et l'écho exact restent exigés. Tout défaut conserve FAIL et déclenche
uniquement le disarm sûr prévu ; aucune reprise automatique après un
écho refusé et aucun reset pour effacer l'observation.

1. Sur une capture existante, comparer les deux lectures bloc32mots à
   deux lectures **unitaires 32 bits** du mot2, E9002048, en vérifiant le
   compteur avant/après. Cela départage une dépendance à la lecture bloc
   et une valeur stable de la banque. Aucun changement de RTL ni d'état
   observateur n'est nécessaire pour cette première observation.
2. Essai indépendant avec commande2 seule, observateur désarmé, puis
   disarm4. Écho attendu2. Cela teste le troisième bit de capture/mux
   snapshot65 et le même mot de RAM, sans clear/arm.
3. Un nouvel essai ARM1 n'est utile que s'il ajoute la lecture unitaire
   précédente. L'écho attendu reste1 ; s'il vaut0, conserver les deux
   blocs et les deux mots unitaires, arrêter et disarmer. Les deux essais
   déjà faits suffisent pour établir la reproduction à chaud.

Ces accès publics ne donnent ni snapshot64 ni DI0 du SDPB directement.
Même si les contrôles ci-dessus passent, ils ne distingueront pas à eux
seuls captureFF, trajet physique du multiplexeur, écriture/lecture SDPB
et cellule du mot2 dans la RAM de banque. La localisation interne exacte
demande une observabilité supplémentaire ; elle ne peut pas être
fabriquée par interprétation des seuls compteurs. Aucune FIFO n'est
déclarée fautive sur la preuve actuelle.

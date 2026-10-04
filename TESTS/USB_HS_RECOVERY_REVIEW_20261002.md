# Revue HS : initialisation, abandon EP0 et reprise après ACK perdu

Date : 2 octobre 2026. Revue indépendante initialement en lecture seule, puis
correctif EP0 autorisé après reproduction du défaut. Aucun accès carte ni
modification de netlist fournisseur ou d'un dossier de compilation existant.
Les variantes Full Speed sont écartées conformément à l'exigence utilisateur
de **480 Mbit/s minimum**. Aucun nouvel essai FS n'a été lancé.

## Résultat établi

Un **défaut de retransmission des réponses de classe EP0** est reproduit avec
le modèle officiel intact du contrôleur HS Sipeed et le vrai
`tang/rtl/usb/uart/usb_uart_config.v` : après réception d'un GET_LINE_CODING
dont l'ACK hôte est perdu, la nouvelle IN renvoie **DATA1 de longueur zéro**
au lieu de retransmettre la réponse précédente.

Le défaut touche à la fois la réponse CDC normale de 7 octets et la sonde
privée de 32 octets. Il est distinct du défaut bulk observé sur carte : aucune
preuve ne relie actuellement ce défaut EP0 à l'insertion d'un octet dans
`gpu_usb_hs33_ready_r2`.

## Preuve intégrée

Nouveaux fichiers de test :

- `tools/check_usb_ep0_recovery.py` ;
- `TESTS/rtl/usb_ep0_recovery_tasks.svh`.

Le runner réutilise le câblage et les tâches hôte de
`TESTS/rtl/usb_controller_packet_tb.sv`, dans une copie temporaire. Il remplace
uniquement la séquence de test et applique le même override RXRDY d'EP0 à 1
que le top de production actuel. Il instancie le gestionnaire CDC réel, la
FIFO réelle et le modèle `.vo` officiel. Aucun état interne fournisseur n'est
forcé ; les compteurs et registres internes éventuellement affichés sont lus.
L'empreinte du fichier fournisseur `.v` associé au modèle doit correspondre à
celle du contrôleur de référence du projet avant exécution.

Chaque scénario démarre par une négociation HS simulée, SET_ADDRESS=7,
SET_CONFIGURATION=1, SET_LINE_CODING et SET_CONTROL_LINE_STATE. Deux témoins
GET_LINE_CODING normaux suivent, de 7 puis 32 octets : PID DATA1, contenu,
CRC16 et ACK de la phase d'état OUT DATA1 ZLP sont vérifiés.

| Scénario | Résultat | Preuve |
| --- | --- | --- |
| Réponse CDC7 reçue, ACK perdu, nouvelle IN sans SETUP | FAIL : réponse `4b 00 00` au lieu de 10 octets PID+payload+CRC | `usb_hs_ep0_retry7_20261002.json` et `.log` |
| Réponse diagnostic32 reçue, ACK perdu, nouvelle IN sans SETUP | FAIL : réponse `4b 00 00` au lieu de 35 octets PID+payload+CRC | `usb_hs_ep0_retry32_20261002.json` et `.log` |
| Nouveau SETUP avant la première IN, longueurs 32→7 puis 7→32 | PASS : nouvelle réponse exacte et phase d'état correcte | `usb_hs_ep0_preempt_wait_20261002.json` et `.log` |
| Nouveau SETUP après émission sans ACK, longueurs 32→7 puis 7→32 | PASS : nouvelle réponse exacte et phase d'état correcte | `usb_hs_ep0_preempt_sent_20261002.json` et `.log` |

Les quatre rapports donnent `sources_unchanged=true`. Les deux cas PASS
terminent aussi par GET_CONFIGURATION=1 complet. Les deux FAIL sont des
échecs de l'oracle de retransmission, après réussite des témoins normaux ; ce
ne sont pas des échecs de démarrage du banc.

Contre-exemple CDC7 exact :

```text
première réponse : 4b 00 c2 01 00 00 00 08 c8 1b
ACK volontairement absent
POP=7, FIN=0, endpt0_send=0, endpt0_dat=08, sub_stage=7
nouvelle IN : 4b 00 00
```

Contre-exemple diagnostic32 : première réponse DATA1 avec rampe 00…1f et CRC
94 a8 ; après les 32 POP, FIN reste à zéro et `endpt0_send` vaut déjà zéro.
La nouvelle IN renvoie également DATA1 ZLP. Les espacements hôte réutilisent
le banc existant ; la reprise est demandée après 120 cycles UTMI sans ACK.

Reproduction, par exemple :

```sh
python3 tools/check_usb_ep0_recovery.py --case retry7 --output /tmp/usb_ep0_retry7_review.json
python3 tools/check_usb_ep0_recovery.py --case retry32 --output /tmp/usb_ep0_retry32_review.json
python3 tools/check_usb_ep0_recovery.py --case preempt_wait --output /tmp/usb_ep0_preempt_wait_review.json
python3 tools/check_usb_ep0_recovery.py --case preempt_sent --output /tmp/usb_ep0_preempt_sent_review.json
```

## Cause dans le gestionnaire CDC ouvert

Dans `usb_uart_config.v`, les lignes 266–296 consomment la réponse sur POP et
abaissent `endpt0_send` dès son dernier octet. Or POP prouve seulement que le
contrôleur a pris l'octet pour une tentative d'émission. Ce n'est pas la preuve
que l'hôte a acquitté le paquet. Le module ne reçoit actuellement aucun
`usb_txpktfin` : il ne peut donc distinguer ces deux événements.

Les lignes 303–305 remettent seulement `sub_stage` à zéro lorsque TXACT
retombe. Elles ne restaurent pas l'offre ni son premier octet. Le banc
intégré tranche l'incertitude concernant un éventuel tampon du contrôleur :
dans ce modèle, il ne retransmet pas à lui seul les octets de classe perdus.

La correction à préparer doit conserver une réponse et sa longueur jusqu'à
l'acquittement, réarmer le pointeur pour une tentative suivante, et annuler
l'ancienne réponse sur nouveau SETUP accepté ou reset. Le signal public
`usb_txpktfin`, déjà disponible au top, est un candidat pour distinguer
lecture et validation. Un simple reset périodique du contrôleur ne corrige
pas ce contrat. Le correctif testé ensuite est décrit ci-dessous.

Il faut valider le futur changement sur les deux tailles, plusieurs pertes
d'ACK successives, une nouvelle requête préemptive, un reset, le cas normal
et les interactions EP2. Les requêtes tronquées et les nouveaux SETUP de CRC
erroné ne sont pas couverts par les quatre scénarios ci-dessus.

## Comparaison précise avec les corrections USB3

Source consultée en lecture seule :
`/home/michael/logic_analyser_wifi/TESTS/TESTS_USB_ANALYSE_2026-09-29.md`,
sections G19 et G22b/G25b/G26b, lignes 2178–2613.

- **G19, PowerPresent constant et Compliance bloquée** : mécanisme propre au
  LTSSM/PIPE USB3. L'intégration USB2 ne possède ni ce port PowerPresent ni
  cet état Compliance public. Aucun état HS équivalent bloqué n'est établi.
  Importer ce watchdog sans preuve serait injustifié. Dans le dernier essai
  HS3.3, le rechargement fait passer l'adresse USB 105→106, avec vitesse 480,
  configuration 1 et deux interfaces : il y a bien une nouvelle énumération
  avant l'échec bulk.
- **G22b/G25b, nouvel SETUP qui n'abandonne pas l'ancienne réponse/rafale** :
  l'analogie mérite un test, mais les deux scénarios préemptifs USB2 testés
  passent ici. Notre EP0 de classe n'utilise pas la même mémoire ping-pong ni
  le protocole DPH/DPP USB3. Le défaut reproduit ici concerne la reprise sans
  nouvel SETUP.
- **G25b/G26b, longueur capturée avant fin du rewind** : le contrat « une
  retransmission garde le même paquet » s'applique aussi à USB2. Le bulk EP2
  possède déjà `tx_pending`, `tx_saved_len` et le délai `tx_retire` dans
  `usb_fifo.v:330–363`. La longueur est figée au premier POP utile jusqu'à
  FIN ; les nouveaux octets UART ne sont pas ajoutés au paquet repris. Le
  banc `usb_in_packet_tb` couvre ces cas, y compris reset et arrivée tardive.
- **G26b, ancienne fin DPP qui consomme une nouvelle réponse** : les interfaces
  et mémoires sont différentes. Aucune preuve de cet événement n'est obtenue
  dans l'USB2 actuel ; on ne peut pas transposer son masque de fin tardive.

## Réinitialisation et FIFO : vérifications complémentaires

Le top qualifie les locks PLL dans les domaines concernés, puis relâche le
reset du contrôleur. FIFO, gestionnaire CDC et pont UART partagent
`usb_app_reset = RESET | usb_busreset`. Cela conserve l'assertion asynchrone
lors d'une perte de lock, même si la sortie `usbrst_o` du contrôleur ne peut
plus évoluer faute d'horloge. Les deux côtés des FIFO reçoivent ce reset.
Ce point avait déjà un test contrôleur positif et un témoin négatif archivés
dans `usb_controller_reset_20261002.json` ; il n'a pas été modifié ici.

Cinq bancs existants ont été réexécutés sans changement de source. Rapport :
`TESTS/usb_hs_recovery_existing_20261002.json`, cinq PASS, sources intactes.

| Banc | Couverture utile |
| --- | --- |
| `usb_control_diag_tb` | réponses normales CDC7, deux pages diagnostic32, retour CDC7 |
| `usb_reset_release_tb` | relâchement retardé, perte de lock, horloge arrêtée, impulsion de lock brève |
| `usb_in_packet_tb` | longueur reprise EP2 figée, données UART nouvelles, fenêtre vide, retrait après ACK, reset |
| `usb_tx_retry_tb` | 191 octets vérifiés, reprise après interruption et passage de frontière RAM |
| `usb_cdc_fifo_tb` | 125/124,5 MHz, phase 0,317 ns, 59 877 octets vérifiés, 123 abandonnés volontairement au reset |

Ces simulations ne prouvent ni la métastabilité ni les marges physiques.
La saturation prolongée sans consommation reste une limite de l'interface
UART→FIFO : le producteur n'a pas de retour de pression. Elle ne correspond
pas au contre-exemple matériel d'un octet isolé et n'est pas retenue comme
explication de celui-ci.

## Limites et suite discriminante

Les premières séries ci-dessus utilisent le **contrôleur HS original Sipeed**,
exact pour son fichier fournisseur associé. La confirmation sur le modèle
officiel HS3.3, obtenue ensuite, est détaillée à la fin de ce rapport.

Les tests sont numériques à la frontière UTMI : pas de PHY ni de câble, pas
de preuve de timing et pas de nouveau chargement carte. Le résultat matériel
`TESTS/usb_ax15_20261002/usb_hs33_ready_r2/` reste FAIL : premier bloc64 avec
une insertion observée à l'index14 et suppression du dernier octet dans la
lecture de 64 octets. Ce défaut bulk doit continuer à être étudié séparément.
Corriger EP0 doit d'abord rendre ses reprises déterministes et fiabiliser les
requêtes de contrôle, sans être présenté comme la résolution de tout le HS.

## Correctif ciblé et résultats après modification

Le correctif conserve séparément **l'intention de répondre** et **TXVAL de la
tentative courante**. Nouveau port `usb_txpktfin` dans le gestionnaire,
raccordé à FIN au top ; registre `endpt0_pending` initialisé au reset, armé
après décodage du GET et effacé sur nouveau SETUP ou FIN d'EP0.

La baisse TXVAL au dernier POP est conservée exactement. Lorsque TXACT
devient inactif sans acquittement, l'index, le premier octet et TXVAL sont
réarmés pour retransmettre la réponse conservée. Le snapshot diagnostic
reste celui capturé au SETUP. Les resets et horloges du top ne changent pas.

Un premier candidat maintenant TXVAL haut jusqu'à FIN a été **rejeté** par
la simulation intégrée : le contrôleur ne terminait plus sa première réponse.
Il utilisait TXVAL comme fin du flux de classe EP0, malgré txlen=7. Les
rapports suffixés `_fixed_20261002` sans `_r2` conservent ces essais rejetés ;
ils ne valident pas le correctif retenu. Le code retenu correspond au SHA :

```text
usb_uart_config.v : 3b241ade43973aa5d8f4f3d457443a32d9335f1683d473f092e0512e5084975a
```

| Essai du correctif retenu | Résultat |
| --- | --- |
| `usb_hs_ep0_retry7_fixed_r2_20261002.json` | PASS : CDC7 retransmis, DATA1/contenu/CRC/status exacts |
| `usb_hs_ep0_retry32_fixed_r2_20261002.json` | PASS : diagnostic32 retransmis, snapshot inchangé, status exact |
| `usb_hs_ep0_normal_fixed_r2_20261002.json` | PASS : séquence normale CDC, diagnostic et GET_CONFIGURATION |
| `usb_hs_ep0_normal_equivalence_20261002.json` | journal avant/après **strictement identique**, timestamps compris |
| `usb_uart_config_recovery_fixed_r2_20261002.json` | deux bancs applicatifs PASS ; 188 octets couvrant les cas limites |
| `usb_hs_ep0_preempt_wait_fixed_r2_20261002.json` | PASS : préemption avant IN, 32→7 et 7→32 |
| `usb_hs_ep0_preempt_sent_fixed_r2_20261002.json` | PASS : préemption après émission sans ACK, 32→7 et 7→32 |
| `usb_hs_ep0_ep2_fixed_r2_20261002.json` | PASS : 133 contrôles, 131 octets IN exacts, 524 OUT exacts, trois reprises |

La comparaison normale est faite contre une copie intacte de la source avant
fix, `TESTS/usb_hs_ep0_before_20261002/usb_uart_config.v`, dans le même banc.
Elle couvre les événements affichés, les paquets UTMI complets, leurs octets,
PID, CRC, FIN et timestamps ; elle n'est pas une équivalence universelle de
tous les signaux internes ou de tous les stimuli possibles.

`TESTS/rtl/usb_uart_config_recovery_tb.sv` vérifie les reprises après seulement
trois POP, trois reprises complètes supplémentaires, la conservation du
snapshot malgré une entrée live modifiée, FIN d'EP2 sans effet sur EP0,
préemption dans les deux sens et reset pendant l'arrêt de l'horloge.

Le test intégré EP0/EP2 inclut trois requêtes de contrôle pendant qu'un paquet
bulk reste non acquitté, des SOF, des sondages de notification EP3 et 64 phases
d'arrivée UART face à une IN vide. Aucun ZLP parasite n'est observé ; PID,
longueur et octets du paquet bulk repris restent corrects. Les rapports de ce
dernier lot donnent tous `sources_unchanged=true`.

Les quatre tops historiques reçoivent aussi le nouveau port. Preuve de
syntaxe : `TESTS/usb_ep0_legacy_ports_20261002.json`. Trois tops passent ;
`ddr_test_cdc.v` conserve une anomalie historique indépendante, déclaration
double de DDR3_INIT, reproduite sur HEAD avant modification.

L'export HS3.3 officiel est réalisé dans
`tang/impl/gpu_usb_controller33_hs_model_r1`. Il emploie le VG exact du stage
`gpu_usb_hs33_ready_r2`, SHA
`270faa84b48751cc87df7845e1aaaafa48cd37c4572e46f5cfeda6529582f828`,
avec le wrapper ouvert `TESTS/rtl/usb_hs_controller_model.v` et la ROM réelle.
La réduction des ports consiste à garder cette ROM dans le wrapper ; les
entrées BOS y sont explicitement nulles, différence déclarée par rapport au
top qui a des fils BOS non pilotés. Aucune requête BOS n'est testée.
L'export a nécessité Gowin hors sandbox pour sa vérification locale de licence
AF_NETLINK ; le lancement hors sandbox a été repris par l'agent principal.
Le journal `generate_authorized.log` se termine normalement le 2 octobre
à 22:46:23 et annonce la création du modèle `.vo` officiel.
Ce projet sert à produire un modèle de simulation, jamais un bitstream carte.

Le témoin matériel avant fix
`TESTS/usb_ax15_20261002/usb_hs33_ready_r2_ep0_baseline/` a 14 réponses EP0
exactes, puis EPROTO71 sur la quinzième demande (page diagnostic haute).
Il ne force pas d'ACK perdu et ne prouve donc pas que le contre-exemple
simulé explique à lui seul cette erreur matérielle.

## Confirmation sur le contrôleur HS3.3 officiel

Le même banc utilise désormais l'export officiel :

```text
export/controller33_hs/impl/pnr/controller33_hs.vo
SHA-256 : aa94743bb6922840761dfb2d6ba84f9c522f5b8b220f5feda95ca61a173dbaae
```

Aucune netlist fournisseur n'est modifiée ou déchiffrée. Le runner vérifie
l'empreinte du VG et des entrées de l'export avant simulation. Les références
privées du modèle ancien, utilisées seulement pour afficher toggle/clear,
sont remplacées par des valeurs d'affichage constantes dans cette variante
du banc. Les oracles utilisent les **ports publics**, octets UTMI, PID, CRC
et acquittements ; ils ne dépendent pas de ces affichages.

| Rapport `TESTS/…json` | Résultat |
| --- | --- |
| `usb_hs33_ep0_retry7_before_20261002` | FAIL attendu : DATA1 ZLP après ACK perdu |
| `usb_hs33_ep0_retry32_before_20261002` | FAIL attendu : DATA1 ZLP après ACK perdu |
| `usb_hs33_ep0_retry7_fixed_20261002` | PASS : mêmes 7 octets retransmis, DATA1, CRC et phase d'état corrects |
| `usb_hs33_ep0_retry32_fixed_20261002` | PASS : même snapshot32 retransmis, DATA1, CRC et phase d'état corrects |
| `usb_hs33_ep0_preempt_wait_fixed_20261002` | PASS : nouveau SETUP avant première IN, 32→7 puis 7→32 |
| `usb_hs33_ep0_preempt_sent_fixed_20261002` | PASS : nouveau SETUP après émission sans ACK, 32→7 puis 7→32 |

Les **six rapports** donnent `sources_unchanged=true`. La séquence témoin CDC7
et diagnostic32, présente avant chaque scénario, a un journal **strictement
identique avant/après**, timestamps compris. Résumé machine :
`TESTS/usb_hs33_ep0_summary_20261002.json`. Les réponses corrigées sont suivies
d'une phase d'état complète puis de GET_CONFIGURATION=1 réussi.

Exemple de reproduction avec le modèle HS3.3 :

```sh
python3 tools/check_usb_ep0_recovery.py --case retry7 \
  --controller-model-dir tang/impl/gpu_usb_controller33_hs_model_r1 \
  --output /tmp/usb_hs33_ep0_retry7.json
```

Pour le témoin avant correction, ajouter :

```text
--config-rtl TESTS/usb_hs_ep0_before_20261002/usb_uart_config.v
```

Le VG de l'export provient de `gpu_usb_hs33_ready_r2`. Le build console corrigé
`gpu_usb_hs33_ep0_r1` régénère un VG d'empreinte différente ; les **quatre
entrées de génération** du contrôleur sont identiques octet pour octet,
ainsi que toutes ses options hors chemin d'inclusion. Vérification archivée
dans `TESTS/usb_hs33_ep0_controller_provenance_20261002.json`. Ce constat porte
sur la provenance de la logique ; il ne prétend pas démontrer l'équivalence
physique de deux placements/routages.

L'archive `TESTS/usb_hs33_ep0_recovery_20261002.tar.gz` conserve le modèle,
les entrées d'export, le journal Gowin, les rapports/logs des six essais et
les sources de reproduction du projet. Son manifeste compagnon donne les
SHA-256 de chaque membre et de l'archive. Aucun bitstream de ce projet
d'export ne doit être chargé sur carte.

**Conclusion limitée :** le défaut de retransmission EP0 est reproduit puis
corrigé en simulation avec les contrôleurs HS original et HS3.3. Cette preuve
ne déclare pas les insertions/pertes bulk physiques corrigées et ne remplace
ni le contrôle du timing du build console ni son essai matériel.

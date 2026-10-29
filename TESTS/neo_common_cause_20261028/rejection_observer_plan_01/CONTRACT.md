# RJC1 : proposition unique d'observation causale du rejet R19

Statut : **contrat proposé, non implémenté**. Aucun RTL, bitstream, routage ou
essai matériel ajouté. Les essais dimension/adresse sont suspendus. Le but
est d'identifier la décision réellement prise, pas de corriger une cause
supposée ni de qualifier la DDR.

## 1. Pourquoi les lectures actuelles ne peuvent pas conclure

Le R19 exact a pour SHA VG `dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6`
et FS `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
Les essais COPY vide et COPY vide avec bases égales terminent avec
`done=2,busy=0,rejected=1`, sans erreur géométrique. CLEAR0 a réussi dans la
même séquence avant COPY0. Ces observations ne révèlent pas la porte de rejet.

Les simulations adverses déjà produites dans
`../execution_diagnostic_02/copy_width_discriminant_01/beam_execution_01/`
donnent le même tuple de compteurs pour plusieurs défauts différents : cible
invalide, paquet enfant corrompu, `copy_bad` forcé et en-tête parent invalide.
Elles prouvent cette indistinguabilité des observables, **pas la présence
physique d'un de ces défauts**. Le run OpenCode a statut FAILED pour preuve
d'exécution agent insuffisante ; les cas RTL du superviseur sont distincts.

Les deux mots de paquet visibles aujourd'hui sont seulement des en-têtes,
avec synchronisation bit par bit non atomique. Le compteur de cycles
géométriques ne compte pas l'attente pixels. Le R19 chargé n'inclut aucun
GAO actif : les fichiers de configuration présents ne constituent pas une
sonde disponible sur ce bitstream.

## 2. Un seul instrument, deux banques existantes

Réutiliser les deux transports `neo_gpu_debug_0` et `neo_gpu_debug`, sur les
horloges GPU et AHB existantes. Chaque transport conserve son handshake,
ses synchroniseurs, sa sélection et sa latence AHB. Ses 320 bits `held` puis
`snapshot` transportent une moitié du **même enregistrement figé de 640 bits**.

Les adresses canoniques restent `E9005000` et `E9006000`. Dans chacune,
les huit mots `+20..3C` sont les bits0..255, `+10` les bits256..287,
et `+14` les bits288..319. Aucun nouvel offset ni nouvelle commande AHB.
Les alias actuels sont conservés. La page7 n'est pas utilisée.

Le format des données change explicitement : **+10/+14 ne sont plus les
compteurs received/last_word** dans ce candidat. Les anciens décodeurs R19
ne peuvent pas interpréter ces pages. Le tag de chaque banque contient la
signature/version `0x4A31` et le même événement non nul sur16 bits.
L'identité NGDB historique ne suffit plus à identifier le contenu : le
décodeur exige les deux tags et le SHA du candidat.

Important : ne pas remplacer les ports `live` historiques. Leur bit36
alimente le comptage received et d'autres bits alimentent la métadonnée.
Tous ces raccordements et compteurs restent inchangés. Seules les entrées D
des bascules `held`, puis les bits de transport/lecture manquants, reçoivent
les pages RJC1. Les sélections d'adresse déjà présentes sont réutilisées.

## 3. Captures aux fronts causaux

L'instrument utilise uniquement `gpu_clk`. Il observe l'acquittement ARM
NCP déjà synchronisé dans ce domaine ; aucun nouveau passage de commande
AHB→GPU. Une nouvelle ARM, après fin des lectures précédentes, libère le gel
et crée un événement non nul. Le reset de l'observateur suit celui du
transport existant ; les resets applicatifs sont des données observées.

1. À chaque capture réelle du paquet parent, incrémenter une génération16
   bits. À la capture réelle du paquet COPY (`n7630_6`), lui associer cette
   génération. Les débordements ou captures multiples incohérentes rendent
   l'enregistrement non interprétable ; pas de rebouclage silencieux.
2. Au front du vrai CE des `descriptor_bad` (`n5984_12`), enregistrer le
   **paquet enfant Q256**, le paquet parent w0, la cible, `src_end/dst_end`,
   l'état enfant brut, les trois entrées D réelles et le masque8 de
   différences mot par mot parent/enfant. Enregistrer la génération CHECK.
3. Au front suivant, enregistrer les trois Q des `descriptor_bad`.
   Le CE et le RESET prioritaires des vraies bascules sont pris en compte.
   Ne jamais reconstruire ces opérandes à partir des valeurs après FINISH.
4. À la première transition réelle qui demande BAD au parent
   (`D(state[1])=1`, ancien Q=0, RESET=0), figer son état brut, son en-tête,
   target_valid, bad_header et les témoins. Vérifier Q(BAD) au cycle suivant
   avant publication. Si le CHECK appartient à cette même commande,
   conserver le paquet enfant et ses opérandes déjà saisis. Sinon capturer
   **le paquet parent complet**, marquer les données CHECK absentes et ne
   jamais présenter l'ancien paquet COPY comme celui de la commande.
5. Observer aussi la transition D→Q de `copy_bad` et son état enfant brut.
   Cela distingue une décision VALIDATE d'un état enfant inattendu ; on ne
   déduit pas un défaut FSM du seul `copy_bad=1` final.

Une transition D observée sans Q correspondant, un reset entre les deux,
un nouvel ordre de capture ou une génération discordante conserve une
preuve marquée invalide. Elle ne produit pas un motif causal certain.

Les nombres d'état enfant mappés ne sont pas supposés égaux aux `localparam`
du RTL. Le décodeur conserve les5 bits bruts et exige une table établie par
preuve de mapping ; le parent conserve ses58 bits bruts sans compression.

## 4. Disposition des 640 bits

Banque GPU, 320 bits : paquet sélectionné256 ; tag32 ; en-tête parent32.
Le bit de provenance distingue paquet parent et paquet enfant au CHECK.

Banque SCAN, 320 bits, ordre des bits faibles vers les bits forts :

| Champ | Bits |
|---|---:|
| Tag identique à la banque GPU | 32 |
| Cible : base32, stride16, largeur16, hauteur16 | 80 |
| src_end et dst_end réellement utilisés au CHECK | 66 |
| État parent à la décision | 58 |
| État enfant au CHECK / à la montée de bad | 5 + 5 |
| D puis Q des trois descriptor_bad | 3 + 3 |
| Masque des huit mots parent/enfant différents au CHECK | 8 |
| Drapeaux de validité/provenance | 13 |
| Motif | 3 |
| Génération de commande / génération CHECK | 16 + 16 |
| Témoins d'activité instantanés | 12 |

Les positions exactes sont calculées et vérifiées dans
`decision_evidence.json` : total320, aucun état tronqué.

Drapeaux proposés (13 bits) : record prêt ; événement de rejet ; paquet
enfant ; CHECK associé ; Q après CHECK disponible ; Q parent BAD confirmé ;
bad_header ; target_valid ; reset applicatif vu depuis ARM ; CE CHECK vu ;
anomalie de capture/débordement ; transition enfant bad observée ; erreur
de relation D/Q. Les drapeaux sont des preuves complémentaires, pas une
priorité de motif implicite.

Motifs3 bits : NONE(manuel), HEADER, TARGET, CHILD_VALIDATE,
CHILD_OTHER, PARENT_OTHER, CAPTURE_INCONSISTENT, RESERVED.
L'ordre HEADER puis TARGET suit la priorité réelle de DECODE. Un état
parent incohérent n'est pas artificiellement assimilé à TARGET.

Témoins12 bits au gel : native_valid, native_write, native_ready,
native_rd_valid, copy_start, copy_valid, copy_bad, copy_done,
parent_reset, child_reset, freeze_manual, freeze_pending.
Les nets native sont ceux **à la frontière pixels/arbitre** ; ils ne
prouvent pas l'acceptation physique par l'IP DDR. Le raccord exact de ces
12 témoins devra être audité avant implémentation.

## 5. Aucun rejet : observation de CLEAR1 bloqué

Après CPU arrêté, une demande de snapshot GPU existante peut demander le
gel manuel, à condition que le témoin soit armé, qu'aucun rejet ne soit déjà
gelé et que le GPU soit actif. Observer `req_s != ack` dans le domaine GPU,
puis saisir le paquet parent, l'état parent et les12 témoins sur un même
front. Un snapshot BEFORE pris au repos ne fige donc pas une image vide
avant la commande. Provenance parent, motif NONE, rejected=0,
CHECK absent si aucune validation correspondante. Les champs arithmétiques
non applicables ne sont pas présentés comme opérandes d'une décision.

La demande ne produit aucune commande GPU, ni écriture DDR, ni contrôle du
framebuffer. Un gel manuel reste immuable jusqu'à la prochaine ARM ; un
rejet postérieur ne le remplace pas silencieusement.

## 6. Collecte cohérente et résultat interprétable

Préparer le témoin par ARM avant le microprogramme. Après retour/timeout,
arrêter le CPU, vérifier le contexte et la fin d'ARM. Émettre une première
demande de snapshot GPU et **jeter sa capture** : au front de cette demande,
`held` peut saisir l'ancien record tandis que le helper gèle le nouveau
(sémantique NBA). Attendre sa fin sans changer ACK ni le handshake. Émettre
ensuite les demandes finales dans chacune des deux banques et lire deux
fois les20 mots, les états et les séquences de transport avant/après. Le gel
doit précéder ces deux demandes finales. Si le GPU était inactif sans rejet,
aucun gel manuel n'est créé et le résultat reste NO_EVENT.

Exiger signature/version correcte, tags d'événement identiques et non
nuls, deux lectures identiques, chaque séquence de transport avancée une
fois et stable, aucun busy ni anomalie, aucune ARM concurrente. Les deux
séquences NGDB sont indépendantes : **ne pas exiger leur égalité**, mais
exiger l'égalité des tags contenus dans les deux pages.

Le code de collecte ne doit plus lire ces20 mots avec le décodeur R19.
Il doit attester bitstream, fraîcheur, ARM et absence d'autre sonde. Si les
deux pages se contredisent, le diagnostic reste INCOHERENT, pas une cause.

## 7. Coût et non-régression exigée avant un futur essai

Le VG contient283 bits held/snapshot GPU et208 SCAN, soit491 bits par
étage. Deux transports de320 bits nécessitent149 bits ajoutés par étage,
donc **298 FF de transport supplémentaires**. Ce chiffre est structurel,
pas un résultat de mapping. Les constantes/partages et répliques peuvent
faire varier le résultat final.

Le record contient640 bits dont32 bits de signature constants ; budget de
stockage variable608 bits, plus contrôle/générations de travail. Les champs
CHECK sont écrits dans le record avant son gel, sans double tampon640.
Enveloppe de préparation : environ1000 FF ajoutés au total ; LUT et timing
restent à mesurer. Ce n'est ni une estimation d'occupation publiée ni une
promesse de réussite du routage.

Réutiliser les gardes de `reply_witness_candidate_01/prepare_candidate.py` :
SHA VG/VO/FS/source, modules/primitives/paramètres/ports originaux,
réversibilité octet pour octet. Mappage du seul helper autorisé après revue,
jamais resynthèse du système parent. Diff autorisée limitée aux entrées de
capture/lecture de diagnostic et nouveaux taps ; aucun signal de retour
vers la logique applicative. DDR5.9/300MHz, PLL, reset50ms, contrôles FB et
contraintes existantes conservés. Nouveaux chemins d'observation à auditer,
pas de false-path ajouté pour cacher une capture non qualifiée.

Tests nécessaires : source et primitives du helper, cas HEADER/TARGET/
VALIDATE/default, Q divergent de D, paquet parent différent de COPY,
CHECK ancien, reset/ARM à chaque frontière, snapshot décalé entre banques,
capture manuelle avec première image périmée, snapshot BEFORE au repos,
débordement, clocks arrêtées et redémarrées. Vérifier
commandes/données GPU strictement inchangées sous ces observations.

Une nouvelle route peut modifier la charge physique malgré l'absence de
retour logique. Si le défaut disparaît, conclure seulement non reproduit.
Si le défaut persiste et les captures sont qualifiées, les opérandes et
motifs permettront de nommer une porte de décision ; l'origine électrique
ou temporelle éventuelle demandera encore une preuve distincte.

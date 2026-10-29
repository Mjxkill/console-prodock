# Validation locale R19 — travaux en cours

Le banc `tb_reviewed.sv` a été préparé par l’orchestrateur pendant le travail
indépendant de Fable. Il n’est pas présenté comme du code généré par Fable.
Les propositions des modèles restent des avis à vérifier.

`rtl_run_01/result.json` : PASS Verilator. Sources applicatives gelées R19,
`gpu_accel` complet avec son vrai slot et `ddr_gpu_arb` réel. Seul le terminal
DDR est modélisé. Le banc envoie les cinq commandes exactes de l’essai matériel
same-address, puis des blocages indépendants commande/données, des masques
partiels, une pause AHB et un reset pendant pending. Il compare 73 728 octets
à chaque point de contrôle, dont les gardes.

Ce résultat couvre les stimuli exécutés ; il ne reproduit pas le blocage
matériel. Il ne qualifie pas la DDR physique, les lectures, la contention
CPU/scanout, la netlist ou le timing. Le bitstream R19 reste FAIL timing.
La fenêtre de 24 cycles après completion est finie, pas une preuve de vivacité
universelle. Le `+1` du comptage final représente explicitement l’unique
transaction abandonnée par reset ; une version suivante comptera cet abandon
directement.

## Revue contradictoire Beam 01

Réponse intégrale dans `../neo_beam_bench_01/answer.txt`. Certains points ne
résistent pas à la lecture du banc et ne sont pas appliqués :

- Compter une entrée sans `!v1_accepted` compterait des cycles que le vrai slot
  refuse précisément pour éviter la recapture. Ce changement serait incorrect.
- Imposer à chaque instant `native_grants == returned_acks` contredit le délai
  intentionnel d’un cycle du retour ACK. Le contrôle à l’arrêt est pertinent.
- Le payload complet est déjà comparé après chaque front où l’ancien pending
  vaut 1, y compris les deux modes de blocage et le front d’acceptation.
- Les accès sont en mots de 32 bits : `ma[2:0] == 0` vérifie exactement un
  alignement de 32 octets. Un masque DDR à 1 inhibe l’écriture ; la terminologie
  « masque actif bas » de la réponse prête à confusion.
- Modifier seulement une valeur attendue prouve la sensibilité du comparateur,
  mais ne prouve pas celle d’un invariant de protocole ; les contrôles négatifs
  seront distingués selon leur portée.

Apports retenus : observer explicitement l’abandon au reset, interdire toute
écriture après completion observée, documenter l’absence voulue de lectures et
éprouver les assertions avec des contrôles négatifs locaux. Une seconde revue
Beam examine ces objections et la chronologie exacte, sans modifier le RTL.

## Renforcement exécuté

`rtl_run_02/result.json` : PASS. Le fichier d’origine et son lanceur sont
conservés intacts ; `tb_reviewed_r2.sv` ajoute la conservation à chaque cycle
avec comptage explicite des abandons au reset, la stabilité du propriétaire,
le retrait de native_valid après l’ACK observé par le vrai FSM, et l’absence
d’écriture pendant les 24 cycles après completion. Aucune correction
`v1_drain` ou modification du RTL n’a été appliquée.

`sensitivity_01/result.json` : les deux contrôles négatifs échouent exactement
sur l’assertion attendue : polarité de masque inversée dans le terminal DDR
modélisé, puis témoin de payload tenu volontairement corrompu. Le second
contrôle prouve la sensibilité du comparateur, pas l’injection d’une faute
physique dans le registre réel. Le même exécutable passe aussi avec les
demi-périodes GPU 6,650 et 6,683 ns (AHB toujours 6,25 ns), sans compilation
supplémentaire ni modification des sources.

La réponse `../neo_beam_bench_02/answer.txt` reconnaît les trois objections
sur l’ACK différé, le garde de chargement et le payload déjà contrôlé. Sa
chronologie est cohérente avec les assertions exécutées de la version r2.

`rtl_run_03/result.json` : PASS après intégration revue du petit bloc proposé
par Fable sim02. Les 14 montées de native_valid sont toutes précédées de
native_issue ; les 13 retours ACK natifs provoquent bien le retrait de VALID.
La quatorzième requête est abandonnée par reset. Le compteur rend le contrôle
ACK explicitement non vide. Cela couvre les états CLEAR exercés et ne justifie
aucun correctif `v1_drain` pour un producteur supposé fautif.

La même réponse Fable confirme le contre-exemple qui interdit le patch
`native_issue || (native_wait && !ready)` : en COLOR_WAIT/Z_WAIT, l’ACK peut
arriver plusieurs cycles avant les données. Après le retrait de ready, ce
patch réémettrait une lecture déjà acceptée. Le RTL gelé garde au contraire
native_valid à zéro jusqu’à un nouvel état d’émission. Le patch n’a pas été
appliqué.

## Limite Icarus

`icarus_run_01/result.json` : compilation correcte mais exécution expirée
après 90 secondes, sans verdict fonctionnel. Une relance courte avec les
statistiques du moteur (`verbose_timeout.log`) indique seulement quatre pas
de temps et environ 690 000 événements en huit secondes : la simulation
reste dans des événements delta au démarrage. Ce résultat n’est ni un PASS
4 états, ni une reproduction du blocage CLEAR sur carte. Le PASS Verilator
reste distinct de cette limite d’exécution. Aucun RTL n’a été modifié pour
faire disparaître cette limite.

## Chemin COPY indépendant du registre native_valid

`copy_run_01/result.json` : PASS sur les mêmes sources gelées et le même vrai
slot/arbitre. `tb_copy.sv` ajoute uniquement le retour du terminal DDR simulé
(réponse de lecture ordonnée après cinq cycles). Après le TARGET habituel,
le paquet `[1d000000,00808000,00100001,00000020,0,0,00100001,0]`
copie 16 pixels depuis une source alignée hors couleur/profondeur vers
`0x00800020`. Une lecture et une écriture de 32 octets sont acceptées.

Une seconde copie partielle, source x=5 vers destination x=3, largeur 7,
laisse passer la lecture pendant le blocage des données d’écriture, puis
termine après la libération. Bilan : deux lectures, deux écritures, quatre
slots et quatre ACK, gardes exactes. Ce test local prépare un essai matériel
discriminant ; il ne signifie pas que COPY fonctionne déjà sur R19 en carte.

COPY émet via `u_copy.valid` et le mux `copy_sel`, puis traverse le même slot
et le même arbitre que CLEAR. Il contourne l’émission `native_issue` /
`native_valid` du moteur pixel. Les connexions gelées du top Neo et de
`ddr_subsys` confirment le retour direct de l’arbitre à gpu_accel, sans étage
Neo de réponse ignoré par ce banc.

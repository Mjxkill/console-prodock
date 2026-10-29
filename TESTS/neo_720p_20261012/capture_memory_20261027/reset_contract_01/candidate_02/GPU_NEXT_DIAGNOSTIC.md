# Diagnostic conditionnel après l'essai de démarrage R21r2

**Proposition seulement : aucun accès carte, nouveau build ou changement de source.**
Le routage reste FAIL. Les données dynamiques D/Q/CE et les sticky bits du nouvel
observateur ne sont pas utilisés. Les expériences R19 sont des témoins historiques,
pas des validations de cette nouvelle route.

## Si le CPU et la mire reviennent

Commencer par les mêmes commandes et adresses que R19, CPU garé, cache désactivé
et relu (`csr1994=0`), scanout DDR et couches désactivés. L'opérateur garde le verrou
Neo et vérifie le SHA du bitstream. Le débit JTAG reste celui qui vient de passer
l'essai de démarrage (100 kHz), pas l'ancien 1 MHz des scripts R19.

Les registres utilisables sont les valeurs **tenues stables après une commande** :
signature BLT2, busy/full, done modulo65536, erreurs commande, perte de FIFO,
V1_rejected, fragments et passed. Leur transport `cdc_word` utilise un mot tenu
et un handshake ; ce n'est ni un banc de captures par cycle ni une preuve physique
universelle. Lire le bloc trois fois à 1 ms d'écart, exiger égalité, et établir sa
fraîcheur par des commandes témoins dont les incréments sont connus. Si les lectures
ne se stabilisent pas ou si le témoin échoue, arrêter l'interprétation.

Le compteur `host_words` de NGDB (0xe9005008) est tenu dans hclk ; +8 indique que
les huit écritures ont été acceptées à l'entrée. Il ne prouve pas leur contenu,
leur passage dans le domaine mémoire ou leur capture correcte dans COPY.
Ne pas employer les captures NCP, les D/Q/CE, les bits mémoire sticky ni les
instantanés multi-bits non qualifiés pour décider du chemin qui est en panne.

### 1. Témoins de configuration sans DMA

1. TARGET exact R19, puis CLEAR avec flags0 et CLEAR vide : done+1, rejet inchangé,
   mémoire inchangée. Cela vérifie que le chemin V1 accepte une configuration et
   des opérations sans transaction. Un TARGET accepté seul ne prouve pas chaque
   champ configuré physiquement.
2. COPY avec le descripteur source valide R19, mais étendue demandée0 : le moteur
   valide le descripteur avant le clipping, puis termine sans lecture/écriture.
   Attendu done+1 et aucun rejet. Un rejet ici situe le symptôme avant l'émission
   mémoire de COPY, sans dépendre du handshake DDR.
3. Témoin COPY identique avec w7=1 : rejet+1, done+1, aucune écriture. Puis relancer
   le COPY vide valide. Cela contrôle que le compteur de rejet reflète des
   opérations fraîches et que le comportement dépend du descripteur.

Les paquets exacts et les attentes sont dans `gpu_next_cases.json`. Arrêter tout
envoi si busy ne retombe pas à la borne prévue ; ne pas empiler les commandes.
Les scripts R19 ne doivent pas être exécutés tels quels : ils contiennent une
ancre et un décodeur NCP R19 qui ne correspondent pas à ce candidat.

Si le COPY vide est rejeté alors que CLEAR flags0 passe, le test distingue le
chemin COPY/configuration de l'émission DMA. Il ne permet **pas** de départager
une capture de descripteur erronée, un champ TARGET erroné, un calcul de bornes,
le contrôle/reset COPY ou une violation physique de timing. Aucune CSR actuelle
n'expose tous les champs COPY tenus stables ni les trois descriptor_bad.

### 2. Preuve mémoire indépendante des échantillons

Seulement après passage des témoins : remplir et relire les petites zones exactes
R19 (couleur à0x00800020, source à0x00808000, profondeur à0x00810000), avec motifs
différents et gardes. Effectuer COPY16 aligné : seuls les32octets couleur attendus
doivent devenir les32octets source. Ensuite COPY7, sourcex5 versdestinationx3 :
seuls14octets changent (`color[38:52] = source[42:56]` dans les dumps avec32octets
de garde initiale). Vérifier toutes les autres zones et gardes.

| Résultat | Déduction autorisée | Limite |
|---|---|---|
| done+1, pas de rejet, mémoire exacte | cette lecture/écriture COPY a effectivement traversé les chemins testés | n'exonère pas toutes les opérations ni tous les timings |
| done+1, rejet+1, mémoire inchangée | refus avant DMA selon la FSM correcte | ne prouve pas quel champ a été mal capturé |
| busy reste1, done inchangé | commande bloquée ou réponse/état mal rapporté | aucun étage mémoire précis n'est identifié |
| done+1, pas de rejet, résultat faux | erreur silencieuse détectée par les données | compteurs seuls insuffisants ; arrêter |
| gardes modifiées | transaction hors de la zone attendue | arrêter immédiatement et conserver les dumps |

Un COPY réussi suivi d'un CLEAR natif bloqué discrimine les producteurs ; ce n'est
pas une preuve universelle d'absence de défaut dans leur chemin mémoire commun.
Le legacy fill32octets exact R19 reste un témoin supplémentaire de l'accès mémoire,
sans confondre son adaptateur avec le chemin natif V1.

### 3. Test discriminant si un CLEAR reste bloqué

Reprendre une seule fois CLEAR couleur16 ou profondeur16, sur un état frais ou
après la séquence complète connue. Conserver compteurs stables, temps borné et
dumps exacts. Le précédent test R19 écrivait avec succès dans une zone CPU séparée
pendant le stall : il prouvait une activité DDR possible, **pas** l'absence de
requêtes GPU acceptées.

Une expérience plus discriminante consiste à écrire par le CPU un nouveau motif
de32octets **dans le bloc que le CLEAR est censé écrire**, puis à le relire
immédiatement et après10/100ms, avec les gardes. Faire au plus deux motifs différents.
Une zone témoin séparée garde une valeur indépendante. Capturer busy/done avant et
après chaque intervention ; si le stall disparaît, l'intervention fait partie
du résultat et le test ne décrit plus le stall initial.

- Si le motif CPU est remplacé à répétition par la couleur/profondeur CLEAR alors
  que done ne progresse pas, il existe une écriture effective sur le bloc attendu.
  Cela réfute « aucune transaction native n'atteint la DDR » pour ce test et oriente
  vers répétition, acquittement perdu ou progression de la FSM.
- Si le motif CPU reste intact, cela **ne prouve pas** que valid est toujours0 :
  écriture masquée, mauvaise adresse, lecture en boucle, absence d'acceptation ou
  commande jamais émise restent possibles.
- Une écriture CPU peut modifier l'arbitrage ; un changement de comportement après
  cette intervention doit être conservé et non interprété comme la trace d'avant.

Ce test exige une autorisation opérateur distincte de l'essai startup en cours,
car il écrit de la DDR volatile. Il n'utilise aucune capture dynamique NCP.

## Si le démarrage échoue

Les observations déjà accessibles sans CPU sont limitées et doivent rester telles :

- Photo HDMI **avant toute tentative DMI** : présence de mire/absence de signal.
  La mire n'utilise pas de framebuffer DDR et ne prouve pas que l'AE350 tourne.
- LED physique `led_n` surV13, si visible par la caméra : le top impose
  `led_n = ~ddr_init`. C'est un témoin de l'état logique de calibration, pas de
  l'intégrité mémoire, de LOCK CPU ou des50ms. Si la LED n'est pas observable,
  ne pas inventer sa valeur à partir d'une image LCD.
- IDCODE/DTMCS par le TAP déjà validé, à100kHz, sans target/halt/reset : accessibilité
  du transport de debug seulement, pas témoin du reset interne ou de l'horloge CPU.
- Écoute UART passive possible, mais l'absence de sortie n'est pas discriminante
  pour un CPU en ROM de parking. Aucun témoin indépendant d'epoch mode1 n'est
  accessible si DMI reste bloqué ; les huit octets acceptés par write côté PC ne
  prouvent pas leur réception FPGA.

L'observable passif reset/clock CPU manque dans ce bitstream. En cas d'échec,
préserver les photos/logs, restaurer l'ancre R19 une seule fois selon le contrôleur
revu et vérifier la récupération. Sans nouvel observable qualifié, répéter des
rechargements ou des messages UART ne résoudrait pas cette ambiguïté.

## Sources locales exactes

- R19 COPY : `local_capture_20261026/r19_copy_20261027_000303/result.json` :
  TARGET accepté, COPY16 rejeté, aucune modification mémoire.
- R19 profondeur/CPU : `local_capture_20261026/r19_depth_cpu_20261026_234857/result.json` :
  CLEAR profondeur bloqué, trois écritures CPU séparées exactes, stall inchangé.
- RTL figé R21r2 : `gpu_copy565.v` lignes76–104 (capture/validation/clipping),
  `gpu_v1.v` lignes428–442 (sélectionCOPY/retourbad), `gpu_accel.v` lignes89–146
  (compteurs et CDC), `cdc_word.v` lignes18–34, `console_neo.v` ligne205 (LED).
- Le manifeste `gpu_next_plan_manifest.json` lie ces fichiers, les paquets et ce
  document. Ce plan ne qualifie ni les sondes anciennes ni un futur essai carte.

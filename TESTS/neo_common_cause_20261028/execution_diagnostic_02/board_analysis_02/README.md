# MicroDMA Neo R19 — analyse contradictoire de l'essai matériel 02

Le CPU relit correctement les 128 octets, TARGET termine, puis CLEAR ne
termine pas. **La cause interne n'est pas encore observée.** Le résultat
matériel reste FAIL et R19 a été restauré par root. Aucun accès carte de
cette analyse ; les preuves originales restent inchangées.

## Faits établis

- Firmware réellement chargé : `dbf293d4ed9c739e4641f0ff531374c5fb9ad8ec7b2b7795f0bf4e609baa934c`.
  FPGA R19 ancré par la programmation précédente :
  `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
  Cette provenance n'est pas une lecture physique du bitstream SRAM.
- CPU en ILM, cache déclaré 0, framebuffer désactivé. Les 32 mots écrits
  par le CPU sont relus exactement avant GPU et après TARGET. Ceci valide
  ce petit trajet CPU/DDR dans ce contexte, pas toute la mémoire ni le débit.
- TARGET 16×1 termine : done=1, BUSY=0 et rejets=0 au contrôle logiciel.
  Le motif entier reste identique. Le défaut de dimensions du premier essai
  a été corrigé ; ce premier rejet était une erreur de sonde, pas de DDR.
- Le CPU revient de huit stores AHB du CLEAR, entre en phase8, effectue
  50 000 lectures de done et sort avec résultat −5. Il rejoint la ROM de
  parking. Ceci prouve la soumission CPU, pas la capture interne des huit mots.
- Le relevé hôte ultérieur, après la temporisation de 2 s, retrouve BUSY=1,
  done=1, erreurs de commande=0, pertes FIFO=0 et rejets V1=0.
- Aucune lecture CPU du scratch après CLEAR n'a été exécutée : compteur
  clear_compared_words=0. Les 128 zéros de cette zone du journal viennent
  de son initialisation. Ils ne sont **pas** le contenu DDR après CLEAR.
- command_words_remaining=1 est écrit avant le dernier store et n'est pas
  remis à zéro ensuite. La phase8 prouve le retour du dernier store ; ce
  champ ne prouve pas qu'un mot manque.
- Les mots GPU+0x20=0x1f et GPU+0x30=0x1ff sont des constantes de capacités,
  pas des mesures de resets ou de moteurs actifs.

Le décodeur strict refuse la réussite. Son libellé `clear_image_mismatch`
exprime l'absence d'une image finale conforme ; avec compteur0 il ne doit
pas être présenté comme une corruption mesurée. Les champs erreurs dans
le journal sont ceux du dernier contrôle réussi (TARGET) ; le relevé GPU
hôte apporte heureusement un second état, plus tardif, également à zéro.

## Hypothèses encore compatibles et observations qui les départagent

| Hypothèse | Contre-épreuve utile |
|---|---|
| Les huit mots CLEAR n'ont pas atteint le consommateur | Compteurs NGDB host_words et received après soumission ; attente 16/16 sur session fraîche |
| En-tête ou lancement perdu entre blitter, géométrie et pixel | Snapshot cohérent : ext_active, état blitter, opcode/ext_command ; les deux en-têtes bruts sont seulement des indices non atomiques |
| Requête native jamais émise ou bloquée avant acceptation | Si CLEAR est capturé, contenu DDR encore intact et absence de done ; R19 n'expose pas directement v1_pending/ready, donc ces données seules ne séparent pas ces deux cas |
| Écriture effectuée, accusé/completion perdu | Après captures sans trafic DDR supplémentaire, lecture CPU des mêmes128octets : couleur exacte et canaris intacts malgré done1 serait discriminante |
| Lecture CPU supplémentaire change l'arbitrage et débloque CLEAR | Captures avant lecture puis après lecture, sans nouvelle commande GPU ; un déblocage dépendant de cette lecture serait un fait nouveau, pas une preuve automatique de FIFO |
| Reset local, distribution physique ou timing | Possibles mais non démontrés par ce journal. Le succès CPU/TARGET exclut seulement une panne totale des clocks/reset/DDR |

Le CLEAR couleur seul n'attend **aucun retour de lecture DDR** dans le RTL.
Il attend l'acquittement de sa requête d'écriture. Les problèmes de tags de
retours et de FIFO de lecture ne sont donc pas l'explication directe la
plus courte. Un état `full` erroné de l'arbitre peut néanmoins bloquer aussi
les écritures : `issue = rst_n && !full` conditionne b_ready. Aucune mesure
de ces signaux n'est contenue dans l'essai02.

## Prochaine collecte, même R19, sans compilation FPGA

1. Root conserve son contrôleur, identité fraîche, exclusivité Neo, watchdog
   hôte et restauration systématique. Réutiliser exactement BIN02 et les
   gardes CPU/cache/ILM/framebuffer déjà testées. Ne pas prendre les registres
   UTW1 de R22 : R19 ne les contient pas.
2. Avant l'exécution, faire un snapshot NGDB pour établir host=received=0.
   Après retour du microprogramme, sauvegarder le journal512B avant toute
   autre action. CPU reste arrêté, aucun trafic DDR ajouté par l'observation.
3. Avant la restauration, faire deux snapshots NGDB distincts, plus le CSR
   GPU complet +0..+0x64. `capture_r19.tcl` fournit uniquement la procédure
   de capture ; elle n'ouvre aucun transport, ne choisit aucune carte, ne
   lance pas de CPU et ne restaure rien. Root l'intègre à son contrôleur.
   Chaque snapshot écrit uniquement NGDB+4=1, observe l'incrément de séquence,
   attend au plus32 polls avec2ms entre eux, puis exige les données tenues
   identiques sur deux lectures. Un accès AHB lui-même peut rester bloqué :
   le watchdog hôte reste obligatoire. Aucune lecture UMSC/USB n'est faite.
4. Selon ces captures, une **seconde étape explicitement séparée** pourra
   relire le scratch par un petit code CPU ILM, sans nouvelle écriture DDR
   ni commande GPU. Conserver le journal initial et capturer avant cette
   lecture, car elle constitue une intervention sur l'arbitrage. Ce lecteur
   supplémentaire n'est pas encore livré ni exécuté dans le présent lot.

### Registres R19 réellement observables

Base NGDB `0xe9005000` : +0 identité NGDB ; +4 status ready/valid/busy bits2/1/0 ;
+8 host_words ; +0xc sequence ; +0x10 received capturé ; +0x14 dernier mot ;
+0x18/+0x1c en-têtes géométrie/pixel asynchrones ; +0x20..0x3c huit mots live
capturés. +0x40 est un méta-état brut, pas un compteur d'arbitre.

Dans live, mot0=done ; mot1 bits0 ext_active,1 ext_start,2 blitter_busy,
3 command_full,4 command_we,5 queue_pop,6 queue_valid,9:7 command_word,
11:10 mrst,23:12 engine_resetn. Mot2 : command_bad[31:16], lost[15:0].
Mots3..5 contiennent debug_blitter : mot3 flags[7:0],opcode[15:8],rp[23:16],
wp[31:24] ; mots4/5 état64bits. Mot6=queue_data, mot7=ext_command word0.
Un blitter en extension attend avec ext_active=1 et état M_SETUP (bit5).
Ces états ne donnent pas directement l'état du pixel ni v1_pending.

Les taps +0x18/+0x1c ne font pas partie du snapshot cohérent. Leur contrat
RTL recommande GPU idle et répétitions égales : pendant le blocage BUSY,
les conserver comme données brutes, sans preuve atomique de capture.

## Preuves locales conservées

`analyze.py` produit `evidence.json` avec SHA des journaux, binaire et sources
R19 examinées. Le banc exact `../microdma_r1/rtl_payload_02/result.json`
confirme que les paquets extraits du BIN02 produisent une unique écriture
native de32octets, malgré9cycles de ready bas. Ce banc ne comprend pas le
FPGA physique, ni toute la chaîne AHB/FIFO/arbitre. Le banc DeepSeek séparé
teste adaptateur/arbitre avec clients concurrents ; il ne transforme pas
l'échec carte en réussite et ne démontre pas la cause du blocage.

La remarque utilisateur sur le SOFT-USB débranché concerne **la Pro Dock**.
Aucune conclusion Neo USB n'est tirée de cette remarque ni de ce microtest.

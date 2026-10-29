# Lecteur CPU après CLEAR bloqué — préparation pour root

BIN `build_01/readback.bin` : **588 octets**, SHA-256
`aa2a1a061c87de6cc47a567a217b6d4078df1d3c982242bfe2275ef7bcc50503`.
Code ILM `[0xa0005000,0xa000524c)`, réservation jusqu'à0xa0006000.
Nouveau journal256B `[0xa0006400,0xa0006500)`.
Ancien BIN02 `[0xa0004000,0xa00043a0)` et journal512B à0xa0006000 restent intacts.

Le lecteur n'écrit **ni la DDR ni les registres GPU**. Il effectue exactement
32 loads CPU sur `[0x12000000,0x12000080)` après vérification des gardes,
stocke leur résultat dans le nouveau journal ILM, puis retourne au parking
ROM0x80000000. Tous les stores sont limités au nouveau journal. Aucun stack,
interruption, cache flush ou appel de bibliothèque. Il remplace temporairement
mtvec puis le restaure. Une trap peut modifier mstatus/mepc/mcause ; root
doit conserver/contrôler le contexte comme pour BIN02. Les GPR sont détruits.

**Ordre obligatoire pour l'expérience** : rétablir contexte R19 gardé, exécuter
exactement BIN02 jusqu'à phase8/résultat−5, arrêter CPU, sauvegarder journal
original et faire les captures NGDB AVANT ; charger/vérifier ce lecteur dans
son ILM distincte, exécuter, arrêter CPU, sauvegarder le nouveau journal et
faire les captures NGDB APRES, puis restauration R19 par le contrôleur root.
Ne pas reprendre une ancienne application ILM. Aucune commande matérielle
n'est exécutée par les fichiers de ce dossier.

Les gardes du lecteur exigent MCACHE_CTL=0, MILMB=a0000001, satp=0,
mie=0 et mstatus.MIE=0 ; ancien journal identitéMD12/version1/phase8/
résultat−5 et comptes32/32 ; framebuffer shadow/commit/active à0 ; identité
GPU BLT2. Il ne bloque pas si done/busy a changé depuis la capture : il
enregistre les deux valeurs avant/après la lecture. Les ancres de carte,
SHA exacts, absence Linux, verrou Neo et exclusivité restent à root.

Chaque load AHB peut rester bloqué : le nombre de loads est fini, mais un
watchdog hôte doit borner leur durée. Sauvegarder le journal partiel si le
CPU ne rejoint pas la ROM. Ne pas appeler ce journal un snapshot atomique
DDR : ses32 valeurs sont des lectures successives. Le trafic de lecture peut
modifier l'arbitrage et éventuellement débloquer le GPU, d'où les captures
avant/après séparées et l'absence de nouvelle commande GPU dans cette étape.

## Journal

32 mots d'en-tête puis32 mots lus. Les champs sont nommés dans `decode.py` :
phase1 gardes, phase2 lecture en cours, phase3 lecture terminée ; résultat1
signifie seulement **32 lectures achevées**, −1 garde refusée, −7 trap.
done/status/errors/lost/rejected sont relevés avant/après, chacun par lecture
CSR indépendante. Ils ne forment pas une capture atomique.

La comparaison embarquée attend couleur0x6b4d aux offsets32..63 et le motif
initial dans les96octets canaris. Elle conserve compteur et première erreur
sans assimiler une différence à une erreur de lecture CPU. Le décodeur classe
`clear_exact_canaries_intact`, `seed_unchanged`, `other_or_partial_change` ou
`unobserved`, sans jamais promouvoir le GPU en PASS. S'il trouve résultat1
avec un journal incohérent, il refuse `readback_valid`.

## Vérifications locales

`test_readback.py` interprète les **octets du binaire compilé**, réutilisant le
petit interpréteur RV32 précédent. Huit cas : CLEAR effectué, motif inchangé,
écriture partielle, canari modifié, trap au8e load, ancien journal non conforme,
cache actif, mauvaise ILM. Tous passent ; les3 gardes refusées font0loadDDR ;
la trap conserve7 lectures et mtval1200001c. Aucun cas n'écrit DDR/GPU ou
l'ancien journal. Ce modèle ne qualifie pas le matériel, les CSR Andes ou le
timing physique. `tests_01.json` lie ces résultats au binaire.

La contre-exécution GLM indépendante ajoute des cas host/adverses ; elle ne
modifie ni ce binaire ni les journaux matériels. La revue/commande carte reste
la propriété exclusive de root.

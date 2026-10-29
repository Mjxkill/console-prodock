# RX2 temporaire — candidat hors carte

Ce candidat ne remplace ni `/tmp/luma-rx` ni les outils gelés R6. Il ne contient
aucune ouverture de port série par défaut, aucun accès FPGA/SD/JTAG et aucun
contrôle du jeu. Le récepteur RV32 statique final est `build_r3/receiver`,
13 132 octets, SHA256
`9a5b401858d72b17be6ea5e6765e9994ba4173c8658f8169dd2de1f529e5810e`.

## Protocole

Un seul paquet en vol. L'hôte émet NUL, Base64 canonique, NUL. L'alphabet sur
le fil est strictement `A-Z a-z 0-9 + / =` et NUL, sans LF/CR, échappement ou
séparateur de commande. Un suffixe reçu par le shell après expiration ne peut
donc pas terminer une commande. Une nouvelle ligne n'est permise qu'après le
RETURN frais du processus et l'annulation de la ligne par Ctrl-U.

Le paquet décodé contient `LX2P`, un nonce128, op/seq/offset/length/CRCpayload
uint32 little-endian, puis CRC32 des40 premiers octets et au plus512 octets.
Toutes les valeurs de l'en-tête sont protégées avant interprétation.
DATA=1, FIN=2, STOP=3. Le bloc écrit est synchronisé avant ACK.
Une erreur write/fdatasync provoque une troncature au dernier checkpoint ;
le résultat de cette troncature est vérifié. Son échec utilise raison9.

Les réponses ASCII portent nonce, type R/A/N/X, prochaine séquence, offset,
CRC32 du préfixe, raison et CRC32 de la ligne. Un ACK perdu ne déclenche jamais
de retransmission dans la même session. Seul un NACK1 correspondant exactement
au checkpoint attendu autorise au plus3 reprises. Un ACK déjà connu peut être
ignoré dans un délai absolu borné. Les CRC ne sont pas une authentification.

Le sender s'arrête sur silence, incohérence ou écriture partielle. Son appelant
doit **toujours** appeler `await_return` en cleanup, même après une exception
de `begin/block/finish`. Cette méthode ne transmet rien. Un X seul ne permet
pas une commande shell : la ligne exacte `RX2_RETURN_<nonce>:<code>` doit être
reçue. Puis annulation de ligne et nouveau prompt contrôlé. Si ce retour manque,
aucune relance, binaire ou commande de diagnostic n'est émise.

La reprise est une nouvelle invocation/nonce, sur un fichier partiel **plat**
`/tmp/rx2-[a-z0-9_.-]+`. O_NOFOLLOW refuse le symlink final et nlink!=1 refuse
les hardlinks. Taille, alignement et CRC du préfixe sont recomputés ; l'hôte les
compare à sa source exacte avant d'émettre. Aucune adoption automatique d'un
partiel étranger, aucun renommage sur un jeu ou une sauvegarde.

## Délais et limites

stdin/stdout passent temporairement en O_NONBLOCK. poll/read/write ont des
délais ; flags et termios originaux sont restaurés aux sorties contrôlées.
HUP/ERR/NVAL quittent immédiatement, sans boucle active. Les réponses disposent
de1s chacune ; un stdout déjà plein quitte en environ2s (READY puis X échoués).
SIGINT/SIGTERM/SIGHUP déclenchent une sortie contrôlée. Le wrapper utilise `||`
pour rester actif même sous `set -e` et imprimer le RETURN après sortie.

L'expiration idle mesure le temps depuis le dernier paquet traité (y compris
NACK/duplication valides), pas depuis le dernier octet. Les octets lents ne la
repoussent pas. Limite totale indépendante≤1h, taille≤32MiB. Le sender refuse
les budgets incompatibles avec son pacing ; 32MiB à16octets/2ms ne tiennent
pas en1h et sont donc refusés. Le débit réel n'est pas mesuré ici.

Ces bornes concernent userspace/Linux en fonctionnement normal avec **/tmp
tmpfs préalablement confirmé**. Aucun logiciel ne garantit un RETURN livré
si le noyau/FS reste bloqué, le processus reçoit SIGKILL, stdout disparaît ou
le shell meurt. Le sender doit alors rester silencieux. Le protocole ne prétend
pas neutraliser une corruption physique transformant l'alphabet en LF/CR, ni
un shell déjà dans un heredoc/une quote/un autre programme. L'appelant assure
exclusivité UART, identité carte, shell ordinaire, espace tmpfs et bootstrap.

## Bootstrap

`bootstrap.py` produit seulement un plan JSON. Nouveau nom exclusif, umask077,
chunks96octets par printf octal, lignes<512octets. Attendre chaque marqueur ;
aucun retry aveugle d'une ligne d'append. Si incertain, arrêter, conserver le
fichier et choisir un nom neuf après diagnostic.

La lecture complète utilise **od -b -v**, déjà présent dans le BusyBox réduit.
Offsets octaux contigus, taille finale, octets et SHA256 sont vérifiés côté PC
avant chmod/exécution. Le plan n'inclut ni chmod ni exécution. L'ancienne image
reste intacte. Prévoir ELF+delta+reconstruction+2MiB et une marge suffisante dans
/tmp ; ce candidat ne supprime aucun fichier pour obtenir de la place.

## Preuves

- `tests_r5/result.json` :32 cas PASS avec l'ELF RV32 exact, Linux/QEMU et le
  vrai BusyBox ash du projet. Bootstrap intégral puis exécution,0/1/511/512/
  513/4096/16384octets, corruption header/payload, pertes/duplications,
  troncatures, ACK perdu, suffixe tardif dans ash, entrée lente, ENOSPC réel
  dans /tmp tmpfs4KiB, reprise, préfixe étranger, vrais symlinks/hardlink,
  stdout bloquant, HUP stdin, wrapper sous errexit.
- `test_sender.py` :20 tests host sur garde/CRC/nonce/absence de retry au silence,
  retour frais, ordre cleanup, budgets et lecture bootstrap corrompue.
- La campagne r2 a trouvé que BusyBox n'a pas `ln` : fixtures remplacées par
  link/symlink C avec vérification lstat. Le FAIL est conservé. r4 n'est pas la
  preuve finale (producteur étendu pendant son exécution) ; utiliser r5.
- DeepSeek a relu le paquet r1. Budgets, HUP, résultat rollback, délai NACK,
  wrapper errexit et chemin plat sont traités. Son assertion que `RX2_PROMPT>`
  commence par `RX2 ` est fausse (underscore) et a un contretest. Cleanup
  explicitement séparé des exceptions est un contrat, testé, pas une permission
  de commande après X. Les vieux ACK restent tolérés sous deadline absolue.

Ces essais ne mesurent ni le débit USB réel ni la stabilité Pro Dock/Neo.
Aucun essai matériel de ce nouveau récepteur n'a été réalisé par cet agent.

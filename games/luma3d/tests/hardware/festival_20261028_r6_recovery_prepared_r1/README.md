# Récupération bornée de la console Pro Dock — incident Festival R6

Préparation hors carte. **Root seul peut exécuter après sa revue** ; aucune carte
n'a été ouverte par ce lot. Le lancement sans `--run` vérifie uniquement les
fichiers locaux. La référence est le R6 manifeste `66e113ea…`, ACK0 à ACK115 puis
silence au bloc116, GM1 PID3158/start27508908. Le code n'est pas un récupérateur
générique ni un nouvel essai de Festival.

## Actions autorisées par ce contrôleur

1. Vérifier les empreintes du paquet, la preuve R6, le FPGA de référence et la
   revue root liée au manifeste, à l'hôte réel `michael-AX15` et à l'alias `ax15`.
2. Verrou exclusif `/tmp/prodock-diagnostic.lock`, contrôle propriétaire `fuser`,
   ouverture exclusive du port exact. Vérifier le termios existant sans le
   modifier. Aucune purge, modification baud/DTR/RTS ni reconfiguration.
3. Écouter **15 secondes sans émettre**. Le moindre octet, même un ancien marqueur
   correct, refuse cette procédure. Aucun prompt n'est adopté silencieusement.
4. Créer atomiquement la revendication locale unique `...66e113ea17517cbf.claim`.
   Elle reste présente même après échec/interruption ; aucune seconde émission
   avec cette procédure. Envoyer une seule suite de **2064 octets** : 2048 NUL,
   puis `LMA1`, seq0, longueur0, CRC0. Lots16 octets espacés de2 ms. Un write court
   ou interrompu arrête tout, sans retransmettre le reste.
5. Attendre15 s maximum le retour complet **neuf**
   `LMA_RX_EXIT_festival-r9f.delta.lz4:1` sur sa propre ligne. Le code1 est attendu
   ici car116 blocs ont déjà été acceptés : le header seq0 ne peut pas terminer
   correctement ce transfert. Acquittements limités à A116, N116/N117 et F avec
   taille59392..60416. Un D, un autre marqueur, un doublon ou texte inattendu
   refuse. Les fragments CRLF et de marqueur sont conservés.
6. Seulement après ce retour et500 ms de silence, envoyer Ctrl-U puis LF pour
   annuler la ligne éventuelle. Exiger le prompt ordinaire et seulement des
   séquences d'effacement reconnues ; aucune commande après une resynchronisation
   ambiguë. Pas de Ctrl-C.
7. Lire les identités PID/start/argv/exécutable exactes, le noyau, les5292 octets
   du save avec SHA, deux compteurs GPU espacés de3 s, df/tmp, taille du delta
   échoué, puis revérifier identité/save. Requêtes fixes en lecture seule, retour
   marqué avec un nonce nouveau par lancement. Aucun appel à un helper GPU.

Jamais d'arrêt ou relance GM1, jamais de reflash, reset, JTAG, écriture SD/save,
suppression de fichier de la carte, redémarrage du transfert ou chargement du
jeu. Le delta partiel est **toujours déclaré inutilisable**, même après succès.
Les NUL peuvent achever un bloc en attente ; si son CRC correspondait, ce bloc
pourrait être écrit dans ce seul fichier temporaire. Il n'est jamais réutilisé.

## Limites et tests

Les28 cas du vrai récepteur RV32 sous Linux/QEMU + BusyBox ash établissent la
séquence pour le récepteur attendu ou une ligne shell ordinaire. Ils ne prouvent
pas la sûreté en présence de corruption transformant un octet en LF, de blocage
noyau, autre processus, quote/heredoc ouvert, ou marqueur ancien rejoué.
La revue root doit confirmer la continuité R6 et ces préconditions. La fenêtre
passive sans données et le marqueur lié au fichier limitent la confusion ; le
protocole historique ne fournit pas de nonce dans ce marqueur et ne permet donc
pas une preuve cryptographique de fraîcheur. Toute incertitude reste un échec.

Les14 tests de transcriptions vérifient les fragments1/2/3/4/5 octets, les sorties
inattendues, mauvais code/nom, troncature, doublon, délais, écriture partielle,
interruption, revendication unique et interdiction des requêtes avant retour.
Ils testent également le refus d'une sortie ressemblant au prompt secondaire
`> ` ; ils ne prétendent pas simuler tous les états internes du shell.

Le contrôleur ne fait aucune tentative de cleanup par UART après un échec.
Il conserve tous les octets reçus et son état, ferme le port sous le verrou,
puis publie `result.json`. Un PASS exige aussi la conservation de GM1/save et
l'avancement du GPU sans erreurs/underflows/faults.

## Exécution root après revue explicite

Copier ce dossier sur ax15. Créer une revue à partir de `review.example.json`
en vérifiant les confirmations ; l'exemple contient volontairement des refus.
Le timestamp doit dater de moins de30 minutes. Commande (valeurs exactes à lire
dans le manifeste figé) :

```text
python3 -B recover.py --run --expected-manifest SHA_DU_MANIFESTE --review /chemin/review.json --out /chemin/nouveau_resultat
```

Sans `--run`, aucune ouverture de périphérique. Ne pas supprimer la revendication
unique pour réessayer : un échec exige une nouvelle analyse par root.

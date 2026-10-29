Étude hors carte de la proposition root : 2048 octets NUL, puis en-tête
`LMA1 / seq=0 / len=0 / crc=0`, soit 2064 octets sans LF ni CR. Aucun garde
ou paquet matériel n’est modifié et aucune autorisation d’envoi n’est créée.

`run_r2/result.json` : 28 cas PASS sur l’ELF historique exact SHA5964389b…,
le véritable BusyBox ash de ce projet et Linux/QEMU, avec PTY.
Les offsets0..16 de l’en-tête, plusieurs points du payload512, un payload1024
quasi complet, une longueur invalide2048, l’état RX vide et une ligne shell
partielle contenant `touch /tmp/EXECUTED;` ont été exercés. Aucun fichier
EXECUTED n’a été créé. Le Ctrl-U et les requêtes textuelles du banc ne sont
envoyés qu’après réception du marqueur complet frais du wrapper RX, ou dans
le cas de test explicitement connu comme shell idle.

Le préfixe NUL suffit à compléter au plus12octets de header et1024octets de
payload, avant que le parser ne recherche le magic suivant. Le header final
len0 termine alors le processus, par F ou D selon son état. Une fin anticipée
pendant les NUL est également possible. Le reste devient une ligne shell
sans LF dans les cas vérifiés. Une concordance CRC peut écrire une dernière
portion dans le fichier temporaire ; ce fichier doit être abandonné après
une récupération, jamais utilisé comme delta valide.

Limites explicites : aucune corruption physique, octet transformé en LF/CR,
écriture noyau bloquée, shell en quote/heredoc, programme différent ou ancien
marqueur rejoué n’est couvert. Le témoin shell ordinaire ne démontre pas une
séquence de récupération universelle. L’absence de marqueur complet demeure
un échec non résolu et n’autorise pas une commande shell.

Le premier run conservé avait une recherche de préfixe seulement pour le cas
du RX vide. Le run_r2 exige aussi son code0 et sa fin de ligne complète.

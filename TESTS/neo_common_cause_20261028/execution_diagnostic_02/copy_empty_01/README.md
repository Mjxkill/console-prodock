# COPY vide : contrôle du rejet avant transaction mémoire

Préparation uniquement, sans bitstream ni matériel. BIN928B :
`build_01/microdma.bin`, SHA-256
`0e9b249f276a9c660bebf2a74774b7930cdaa02bb9fbfffc01136d7f0eb8bbc7`.
Il dérive du COPY928B validé précédemment (`4d3b91…`). Deux mots changent :
offset432 attend le seed lors de la comparaison finale ; offset920 (`w6`)
passe de `00100001` à `00000000`, donc rectangle demandé0×0.
Le descripteur **source** reste16×1/stride32, à12000000.

TARGET et ses validations sont inchangés, destination12000020 et Z12000040,
dimensions16×1/strides32. Même scratch128B, mêmes gardes CPU/cache/FB/ID,
code4000 et journal512B6000, mêmes comptages bornés et retour ROM.
La CPU écrit toujours le motif128B puis le vérifie avant et après TARGET,
et après l'opération vide. Aucun transfert GPU n'est attendu.

Paquet COPY :
`1d000000 12000000 00100001 00000020 00000000 00000000 00000000 00000000`.

Le résultat de contrôle attendu est phase10/result1, done0→1→2, busy/full0,
errors/lost/rejected0, trois comparaisons32/32/32 et trois images égales
au seed128B. Décodeur dédié :
`decode_empty.decode(raw512, firmware_sha256=SHA_BIN)` ; il renvoie
`empty_copy_test_passed`. Ne pas utiliser le décodeur COPY non vide.

## Preuves hors carte

- 13 cas exécutent le binaire RV32 exact : réussite, délai, timeout,
  done encore occupé, rejet, altérations destination/canari, erreurs seed,
  TARGET, cache/ILM et trap. Chaque appel GPU read/write est interdit par
  le modèle du contrôle vide. Les échecs sont distingués du succès attendu.
- 15 contrôles du décodeur couvrent succès, métadonnées, comptages, mémoire,
  longueur/identité et mauvais SHA.
- La chaîne RTL R19 entière (AHB/FIFO/géométrie/pixels/arbitre) est rejouée
  dans un nouveau dossier avec un seul mot de paquet changé et l'oracle
  zéro transaction. Deux phases d'horloges et deux cas avec ready commande
  ou ready écriture maintenu bas après TARGET passent : done2,16mots reçus,
  **zéro lecture, zéro retour, zéro écriture native** et aucune activité tardive.
- Le banc DeepSeek indépendant de validation du descripteur teste également
  ce paquet vide, avant toute proposition d'essai matériel.

Le modèle CPU n'est pas un modèle électrique du hard CPU ou de la DDR. Les
quatre simulations de chaîne n'incluent pas le PHY physique. Root conserve
les verrous, l'identité de R19, le watchdog et la restauration. Aucun ajout
de ce profil au contrôleur matériel n'est réalisé ici.

## Interprétation limitée

La validation source et les calculs src_end/dst_end restent les mêmes que
pour COPY non vide ; `w6` intervient ensuite dans les limites et CLIP.
Si le contrôle vide est rejeté lui aussi, l'accès DDR n'est pas nécessaire
pour reproduire ce rejet. S'il termine proprement, cela distingue les deux
séquences sans prouver la cause physique de leur différence.
Un résultat doit rester lié aux SHA du firmware et du bitstream exacts.

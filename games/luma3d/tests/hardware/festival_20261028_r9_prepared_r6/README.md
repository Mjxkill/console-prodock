# R6 : réutilisation du helper MC1 relu par root

Ce paquet ne peut être figé sans le résultat root de la récupération tmpfs :
`prepare.py --reuse-proof <cleanup_r3>` exige result.json PASS et les octets
`helper_verified.bin` de la lecture complète. Il vérifie l’égalité exacte avec
le helper MC1 conservé localement (221180octets, SHA7cc3e1766d15cb47ac98ab4a6ab33540b5a281c9715afc760c68ab0af03effaf),
l’identité GM1, la sauvegarde, l’absence de signaux au jeu et la poursuite des
présentations. Ces deux fichiers de preuve sont inclus dans le manifeste.

Le champ supplémentaire de la revue root est obligatoire :

```json
"helper_reuse": {
  "path": "/tmp/mc1-helper",
  "sha256": "<SHA du fichier mc1-helper dans le manifeste>",
  "proof_sha256": "<SHA de helper_reuse_result.json dans le manifeste>",
  "readback_sha256": "<SHA de helper_reuse_verified.bin dans le manifeste>",
  "continuity_confirmed": true
}
```

L’attestation porte sur la continuité du fichier depuis la lecture complète ;
le contrôleur ne l’infère pas d’un PID ou d’une date. Au moment de l’essai, le
helper doit encore être un fichier exécutable régulier sans lien symbolique.
Sa taille et son CRC sont recontrôlés avant tout transfert. Cette vérification
rapide ne remplace pas la preuve SHA indépendante : le helper sert à exécuter
son propre contrôle CRC, ce qui est accepté uniquement avec l’attestation
explicite de continuité liée à ses octets relus et à la preuve root.

Seul `festival-r9f.delta.lz4` est transmis. Aucune commande chmod, écriture,
relecture octale ni suppression n’est appliquée à `/tmp/mc1-helper`. Le jeu
R9 reste identique et est reconstruit sous `/tmp/luma3d-f9f` ; fichiers de test
`festivalr9f_*` neufs. Le récepteur est toujours relu et vérifié, les gardes
32Mio sont conservées, les six fenêtres et la restauration GM1 sont inchangées.
Aucun nouvel essai matériel n’est autorisé par la préparation seule.

R5 demeure disponible pour un essai avec retransfert complet si la preuve ou
la continuité de ce helper ne peut pas être attestée. Cette variante n’est
pas un remplacement de la référence Pro Dock.

Revue pré-exécution : root a rejeté un premier paquet R6 dont un remplacement
global de nom avait altéré le SHA FPGA. La version fautive est conservée
séparément dans festival_20261028_r9_r6_rejected_fpga_anchor, sans exécution.
Cette version compare le contrôleur et le manifeste à une copie inchangée de
tang/boards/prodock/reference.json ; le test local lit également le véritable
bitstream protégé. Une corruption simultanée de la constante et du manifeste
est ainsi refusée. Les ancres de R5 restent intactes.

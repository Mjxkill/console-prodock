# FC1 combiné — transfert préparé, aucun accès carte agent

Paquet à relire et lancer uniquement par root. Phase de transfert seule : le Festival actuel reste actif ; aucune commande de signal/arrêt/lancement de jeu, aucun FPGA/noyau/SD écrit. Retour shell ambigu : aucun ordre, seulement attente passive du RETURN de la session RX2 exacte. Pas de réessai automatique de session.

Source distante : `/tmp/luma3d-fm4a`, 16640496 octets, SHA local attendu `6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7`, CRC complet `fa358bf4`.
Cible : `/tmp/luma3d-fc1`, 16644780 octets, SHA local `950ced706963b9f7591f45c067b80ee515dcae084a061c78274fe0f00f3871f7`, CRC `ad06b5da`.
Delta :118315 octets ; une session232 blocs DATA, plus FIN. Le receiver tamponné et le helper existants sont réutilisés après contrôles CRC et attestation root de continuité de leur relecture SHA complète. Le QEMU exact a reconstruit les16644780octets identiques ; le contrôle distant est un CRC complet, pas un SHA matériel prétendu.

Ancre active : PID3940/start35705238, `/tmp/luma3d-fm4a --festival --festival-save /tmp/fm4live1.festival.save --memory-save /tmp/fm4live1.memory.save`. Le pidfile est `/tmp/fm4live1.pid`. Les anciens PID3158/3880 ne sont pas utilisés. Le processus actuel peut naturellement autosauvegarder pendant le transfert ; le contrôleur ne touche pas ces deux fichiers. La sauvegarde historique `/tmp/op2-live.save` garde son SHA protégé.

Capacité obligatoire : cible+delta+8MiB soit25151703 octets ; aucune suppression automatique. Le dernier relevé14 504KiB ne suffisait pas. Root doit vérifier/libérer uniquement les anciens temporaires attribués, sans supprimer fm4a, GM1 ou leurs sauvegardes. MemAvailable>=64MiB. Vérification répétée avant reconstruction.

`transfer.py` réutilise sans changement `stage.segment`, `Channel`, `UART`, le senderRX2 avec drainNACK corrigé et les parseurs d’identité éprouvés. Les constantes anciennes présentes dans ces modules conservés ne servent pas à l’ancre : la nouvelle phase emploie uniquement `transfer.ANCHOR`, `BASE`, `TARGET`, `ARGS`. Les13contre-tests locaux vérifient les gardes et le transcript, pas le transport matériel. Les preuves RX2/QEMU antérieures restent distinctes.

Exécution root après revue remplie fraîche (tousles booléens explicites) :
```
python3 -B transfer.py --run --expected-plan PLAN_SHA --review ROOT_REVIEW.json --out NEW_RESULT_DIRECTORY
```
Sans `--run`, aucun périphérique n’est ouvert. Pas de bootstrap ni copie directe des16,6Mo ; pas de prétention de liaison stable (les retries restent visibles). Le plan contient les six fenêtres identiques auR4 et une septième jardin avec `LUMA_SUBMIT_DIAG=1`. La phase de mesure/restauration reste une opération root séparée à relire.

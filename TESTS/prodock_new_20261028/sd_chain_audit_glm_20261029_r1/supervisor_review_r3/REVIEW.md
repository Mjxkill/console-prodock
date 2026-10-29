# Revue Codex indépendante de l’audit GLM R3

Périmètre : copie figée de la chaîne ROM, U-Boot, paquet CM1 et Linux SD opt-in. Aucune carte, aucun périphérique ni réseau d’administration ; aucun nouveau noyau, jeu ou bitstream. Le seul compilateur utilisé reconstruit le petit décodeur C des en-têtes pour les tests, en répertoire temporaire nettoyé.

Le troisième essai GLM produit un audit exécutable et un rapport. Ses deux premières tentatives incomplètes restent FAILED et sans score. La reprise a utilisé les limites nouvellement installées, sans quota artificiel de 24/32 étapes.

La contre-revue a corrigé la recherche des options noyau (=n pouvait être accepté), l’absence de vérification complète des en-têtes et mesures manquantes des gros fichiers, et les 40 octets oubliés dans le tampon U-Boot. Trois groupes adverses échouent sur les octets GLM puis passent sur la copie revue. Le rapport avait aussi des erreurs de transcription : CRC Linux, nom du manifeste, région ITCM, LFN désactivé et34 décimal converti incorrectement en hexadécimal. Elles sont corrigées, sortie brute conservée.

Résultat de la copie revue :10 tests unitaires PASS,19 cas contre le décodeur C réel,14 contrôles statiques satisfaits sur 16. Les 2 autres sont la ROM R3 incohérente (preuve déjà connue) et l’absence de qualification post-routage R4 dans les entrées capturées. Aucun nouveau défaut de la carte n’a été établi. R4 représente l’état capturé du paquet d’audit, pas le suivi en direct du travail root.

Ce script est un audit spécifique de ces preuves figées, pas un validateur générique de futurs builds. Certains contrôles sont des lectures de source et ne remplacent ni une simulation d’exécution ni les essais de boot/coupure/GPU. Les grands binaires ne sont pas fournis au modèle : leurs mesures proviennent du superviseur et du résultat d’installation SD root. Les fichiers et résultats exacts sont liés dans final_tests.json et DELIVERY.json.

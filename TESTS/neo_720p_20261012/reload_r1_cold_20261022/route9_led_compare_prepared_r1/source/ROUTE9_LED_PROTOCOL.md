# Essai comparatif LED : préparé, non exécuté

Le protocole compare **N56r8 → R9 exact → N56r8**, sans nouveau bitstream. Il recueille une observation indépendante du CPU sur le composant **V13 de la LED utilisateur**. Ne pas confondre cette LED avec un voyant de batterie/alimentation. Les notes matérielles [CONSOLE_138K_PINS.md](/home/michael/ala-v2/docs/hw/CONSOLE_138K_PINS.md), ligne 87, décrivent G11/U12/V13 comme LED utilisateur actives bas ; aucune couleur précise n’est présumée ici.

Les sources figées et netlists prouvent, pour les deux images, `ddr_init_complete_d_3_s0.Q → ddr_init → LUT1 INIT=1 → OBUF → led_n/V13`. Le niveau électrique bas/allumage de ce composant signifie donc `ddr_init=1`. Un voyant mal identifié, clignotant ou peu lisible doit être enregistré `unclear` ou `blinking`, jamais transformé en mesure binaire.

R9 reste **FAIL** : setup −0,849 ns, recovery −0,360 ns et reset4 sur LW. SHA R9 `1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde`. N56r8 de repli : `51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35`. La source de l’ancre est exclusivement [le résultat 100 kHz](r9_route9_rgb_trial_100k/result.json), [son repli vérifié](r9_route9_rgb_trial_100k/restored.log) et [la confirmation visuelle](r9_route9_rgb_trial_100k/visual_confirmation_fallback.json). Les trois empreintes sont imposées par le script.

Le [nouveau contrôleur](probe_route9_led_compare.py) réutilise les gardes stricts de l’ancien essai 100 kHz, sans modifier cet essai ni le chargeur générique. `--check-only` vérifie uniquement des fichiers : aucun verrou carte, aucune énumération USB, aucun subprocess ou accès matériel, aucun dossier d’essai ni consommation d’ancre.

```sh
python3 -B TESTS/neo_720p_20261012/reload_r1_cold_20261022/probe_route9_led_compare.py \
  --bitstream-sha256 1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde \
  --out TESTS/neo_720p_20261012/reload_r1_cold_20261022/r9_led_compare_trial \
  --check-only
```

L’exécution matérielle n’est pas lancée par cette préparation. Après revue du coordinateur, autorisation applicable et disponibilité de l’utilisateur, il reprend la même commande **sans `--check-only`**, dans une session conservant stdin ouvert (PTY). Un seul opérateur Neo ; aucune autre sonde pendant l’essai.

1. Prendre `TESTS/neo_board.lock` et le conserver jusqu’à la fin. Vérifier le programmateur Neo série `2025041420`, VID/PID `0403:6010`, et l’unique ESP-Prog produit `Dual RS232-HS`, lui aussi `0403:6010`. Vérifier N56r8 par JTAG 100 kHz : CPU arrêté, M-mode/satp0, PC et ROM de parking, géométrie 1280×720, mire interne/checksum. Aucun changement de framebuffer.
2. Le processus imprime `LED_OBSERVATION_REQUIRED` avec phase `n56r8_before` et un token neuf. Le coordinateur attend la réponse réelle de l’utilisateur, puis saisit une ligne JSON comme ci-dessous, en reprenant le token reçu. Les réponses sont attribuées explicitement à l’utilisateur et sauvegardées avant l’action suivante.
3. Consommer l’ancre une seule fois via création exclusive de `r9_route9_rgb_trial_100k/led_compare_consumed.json`. Charger **uniquement R9 en SRAM**, vérifier DONE/erreurs de configuration et attendre deux secondes. Aucun DMI à cette étape. Le CPU avait été confirmé garé avant la reconfiguration ; son état sous R9 n’est pas présumé.
4. Phase `r9` : conserver R9 et le verrou pendant l’observation. **Aucun délai automatique ne restaure l’image avant cette réponse.** Après sa sauvegarde seulement, effectuer `init; halt; reg pc`, borné à 30 secondes, sans lecture/écriture GPU ou DDR. Un timeout DMI devient un résultat `r9_dmi`, sans invalider ou effacer la LED. Une interruption explicite reste une annulation avec repli.
5. Recharger N56r8 en SRAM. Vérifier le parking à 100 kHz et deux échantillons de 32 registres : signature GPU, géométrie, mode/commit zéro, checksum `1ff8f800` et progression des frames. Alors seulement `fallback_restored=true`.
6. Phase `n56r8_after` : recueillir l’observation finale de la même LED. Le résultat conserve les trois observations, la réponse DMI et les preuves du repli. `passed=true` signifie que **le protocole** a terminé ; `functional_qualification=false` et la qualification FPGA FAIL demeurent.

Exemple de format uniquement, **à ne pas envoyer avant l’observation réelle** :

```json
{"phase":"r9","token":"TOKEN_IMPRIME_POUR_CETTE_PHASE","observer":"user","value":"off","note":"Paroles exactes de l’utilisateur concernant V13"}
```

Valeurs permises : `on`, `off`, `blinking`, `unclear`. Une mauvaise phase ou un token ancien est refusé et laisse le processus attendre. Une fermeture de stdin/EOF, Ctrl-C, SIGTERM ou SIGHUP est une **annulation** : elle tente le repli si la programmation de R9 a été engagée. Avant une restauration, tout programmateur/OpenOCD enfant interrompu est tué dans son propre groupe et attendu ; aucun lancement concurrent n’est permis. Une restauration échouée reste explicitement une erreur, sans prétendre que la mire est revenue. Si l’annulation arrive après un repli déjà vérifié, il n’est pas reprogrammé inutilement.

L’observation permet de séparer « DDRinit annoncé à zéro » de « calibration annoncée terminée mais CPU/DMI bloqué ». Elle ne mesure ni PLL LOCK, ni qualité DDR, ni tension/œil, et ne suffit pas à attribuer une panne à une route particulière. Le test n’envoie aucune commande GPU, ne charge aucun framebuffer, ne reprend pas le CPU et ne démarre ni Linux, ni SD, ni flash.

[Tests locaux](test_probe_route9_led_compare.py) : refus des identités et des ancres périmées, conservation FAIL, ordre LED puis DMI, timeout enregistré, repli sur programmation/interruption/EOF, refus de repli sans progression/checksum, et arrêt effectif d’un groupe de processus enfant avant retour. Les tests utilisent des doubles et des fichiers temporaires ; ils ne qualifient aucun essai matériel.

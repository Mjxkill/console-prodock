# Contre-revue du contrôleur UTNA/vidéo — 27 octobre 2026

**Pas de GO matériel pour le contrôleur actuel.** Le problème bloquant est
une interruption possible du nettoyage avant son premier masquage de signaux.
Ce défaut concerne l'outil d'essai, pas une cause démontrée de la panne Neo.
Le contrôleur, son Tcl, son manifeste et les sources FPGA n'ont pas été modifiés.
Aucun accès matériel, aucune compilation FPGA ni reconfiguration dans ce lot.

## Avis et contre-épreuves

Les deux revues sont terminées :
`../../assisted_reviews_20261026/neo_usb_video_controller_fable_r1/answer.txt`
et `../../assisted_reviews_20261026/neo_usb_observation_deepseek_r1/answer.txt`.
Elles étaient fondées sur un paquet limité. Les imports réels et le RTL figé
ont été relus ici ; une absence dans leur paquet n'est pas une absence de preuve
dans le dépôt.

| Proposition | Résultat vérifié |
|---|---|
| Fable : signal avant masquage du `finally` | **Confirmé.** SIGINT, SIGTERM et SIGHUP aux lignes 107, 110 et 111 du contrôleur exact quittent `execute` sans tentative `restore_r19`. Neuf contre-exemples avec vrais signaux POSIX, IO matérielles remplacées par mocks ; trois témoins sans signal restaurent une fois. |
| Fable : `io.save` pourrait ne pas être utilisé | **Réfuté pour l'import actuel.** `warm_mode1_trial.py:69,83,90` conserve la fermeture dans `self.save` et l'appelle avant et après programmation. Son SHA est inclus dans la revue. L'affectation à `cleanup_save` est donc effective. |
| Fable : aucune preuve des SHA des rapports de test | **Réfuté pour le manifeste préparé.** Les trois fichiers cités par `offline_result.json` figurent également dans `review_prepared.json.proof_files`, avec SHA concordants. La boucle `local_checks` revérifie toutes ces entrées. Une vérification explicite de leur présence rendrait le contrat structurel plus clair ; aucun fichier n'est absent dans ce paquet. |
| Fable : deadline 2 s jamais atteinte | **Non établi.** La borne 100 polls × 2 ms n'inclut pas les lectures JTAG. Les deux bornes coexistent ; aucune durée exacte de 200 ms ou 2 s n'est promise. OpenOCD est borné séparément à 30 s. |
| Fable : timeout ou ticks nuls rendraient toute la mesure vide | **Trop fort.** Quatre relevés vidéo précèdent UTNA, et le statut de timeout/la banque sont journalisés avant les assertions. La fin POST_USB peut manquer, donc la capture est partielle, pas inexistante. Arrêter et restaurer sur défaut conserve ce constat. L'extracteur traite déjà les logs incomplets en échec explicite. |
| DeepSeek : reset après STABLE accepté par le Tcl | **Confirmé pour le marqueur seul.** Le mock exact accepte POST_USB avec séquence 0 et imprime DONE. Mais l'extracteur existant exige séquence 4 au POST_USB (`extract.py:111`) et rejette cette capture. Contre-test isolé : seul échec `POST_USB: unexpected live UTNA status`. Cela ne démontre pas l'absence de tout reset hors fenêtre. |
| DeepSeek : ACK peut précéder la banque dans le contrat RTL | **Réfuté au niveau RTL actuel.** `usb_idle_trace.v:69–71` écrit chaque mot dans le domaine HCLK et incrémente `snapshot_count`/efface busy seulement au dernier mot. La lecture de contrôle ne voit la nouvelle séquence qu'après ce commit. Un mock ACK anticipé sans commit rompt cet invariant ; ce n'est pas un contre-exemple du RTL. Une faute physique de timing reste une limite distincte. |
| Fable : ticks pourraient être des SOF ou une clock ULPI | **Résolu par les sources réelles.** Le mot 3 est `ticks`, incrémenté à chaque front USB tant que `armed` est vrai (`usb_idle_trace.v:155–159,173–190`). SOF est un compteur séparé au mot 16. Ce PHY est UTMI ; aucune énumération HS n'est déduite de ticks. |
| Fable : `internal bars` garantirait une image visible | Le garde prouve la configuration et les compteurs GPU/NCP frais, pas la visibilité HDMI. La formulation doit rester « mire interne sélectionnée » et les photos doivent être inspectées séparément. |

La définition `ticks(STOPPED)=ticks(DISARM)+1`, puis stabilité, est correcte :
la capture prend l'ancien état au front de désarmement, tandis que le dernier
incrément se produit au même front. `clear` met effectivement ticks à zéro.
Ce sont des propriétés RTL, pas une qualification du routage.

## Correction minimale proposée, sans application dans ce lot

Pour le nouveau contrôleur, enregistrer les signaux dans un drapeau depuis
des handlers qui ne lèvent jamais d'exception. Tester ce drapeau à des points
explicites entre opérations expérimentales, sans test qui interrompe la
restauration. Les sous-processus restent bornés et le verrou est gardé jusqu'au
retour R19. Un arrêt peut alors attendre la fin de l'opération bornée en cours ;
ce délai doit être documenté. Tester les signaux réels aux frontières du finally,
pendant sauvegarde et restauration, pas seulement remplacer `signal.signal`
par un mock.

Le contrôle POST_USB de séquence 4 peut être ajouté au Tcl pour refuser plus tôt
un écart déjà rejeté par l'extracteur. Garder les quatre captures initiales et
les journaux partiels quand le protocole s'interrompt. Ne pas transformer un
timeout en PASS pour obtenir une comparaison complète.

L'IO réelle lance openFPGALoader avec `-m` et le bitstream exact, sans flash ni
powercycle ; OpenOCD a un timeout de 30 s, le programmeur de 120 s et la caméra
de 15 s. `run_child` tue et attend son groupe de processus sur exception. Son
masquage progressif des signaux possède également une frontière vulnérable si
des handlers levant sont utilisés ; le handler à drapeau au niveau du nouveau
contrôleur supprime cette voie pour ses opérations. Aucun contrat de survie
à SIGKILL ou à une coupure électrique n'est revendiqué.

## Extraction et état de qualification

L'extracteur est dans `../usb_video_extract_01/`, SHA
`36a664740143fee248c11ee9e014fe41c7312323c48dc3de1cf5add0a3dea828`.
Ses 20 contrôles hors carte et ses limites sont documentés dans son README.
Il distingue cycles RX error/TX stall, fronts bus reset et cycles SOF ; il ne
calcule pas une fréquence physique à partir des heures hôte précédant les
écritures MMIO. Ne pas reprendre la proposition Fable `ticks / 200 ms`, ni
présenter le ratio des heures hôte comme une mesure précise de PLL.

`reproduce.py` réexécute les contre-épreuves dans ce répertoire seulement.
`result.json` conserve leurs sorties. Le contrôleur revu reste SHA
`e33bf8840587f730f039bdc5986239a7d40c97cd0b788f2252bfdc5342d83397`,
`hardware_ready=false`. La correction devra recevoir un nouveau SHA, ses tests
et une nouvelle revue avant l'essai R19 → R21r2 → R19. Le timing global FAIL
du candidat reste inchangé. La licence Gowin expirée ne bloque pas ces tests
sur bitstreams existants, mais bloque toujours la comparaison du générateur PLL.

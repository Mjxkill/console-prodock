# Disposition des avis indépendants

DeepSeek (`neo_r22_bank_cone_deepseek_r1_network`) et Beam
(`neo_r22_combined_probe_beam_r1`) ont répondu sur des paquets bornés, sans outils.
Le premier lancement DeepSeek a échoué DNS dans le bac à sable ; sa relance
réseau a terminé. Leurs réponses sont des propositions, pas des tests exécutés.

Retenu : l'ajout de 402 FF, de charges/taps et de 32 mux est une vraie modification ;
A/B/A/B ne compare pas seulement le placement. Les collecteurs et leurs cadences
diffèrent. La comparaison du cône legacy et des délais doit rester bornée.
Les gardes des snapshots, idle, nombre de mots GPU, absence de DMA et identité
USB exacte sont reprises ou existaient déjà dans le contrôleur préparé.

Réfuté : le doute de DeepSeek sur l'adresse de bank_version est tranché par
les journaux bruts conservés : 0xe9002044 pour bank, 0xe90020cc/20d4 pour witness.
La fonction d'analyse indépendante compare chacun des 408 enregistrements R22
aux données stockées. Le RTL source usb_idle_trace original n'inclut pas le
witness parce qu'il est ajouté par transformation de netlist explicitement
tracée, pas parce que le bitstream serait sans provenance.

Réfuté : la proposition Beam de débrancher physiquement USB pour exercer rst_usb
ne suit pas du RTL. L'absence de périphérique dans sysfs ne démontre pas l'état
rst_usb ; aucun débranchement n'est demandé. Sa mention de bitstream « qualifié »
est erronée : global timing FAIL demeure. L'absence de la séquence orchestratrice
dans son paquet initial était une limite du paquet, fermée par controller.py.

L'avis Beam sur la sémantique idle est résolu par gpu_accel.v:124 : status[1]
contient queue_full et busy_sync, zéro correspond donc à idle. L'opcode31 est
vérifié dans gpu_geometry.v:269–272,307–317 : matrice puis FINISH, sans DMA voulu.
Aucun patch FPGA n'est justifié par ces avis seuls. La nouvelle collecte ne les
présentera pas comme une cause établie.

# Premier essai AHB : limite de preuve et révision de journalisation

L'essai matériel [n56r8_usb_capture_01](n56r8_usb_capture_01/result.json)
reste **FAIL**. Sa version exacte, SHA
`e19e9bdb38c89e9c681e02cd61e6ae2076ce93cf293de67db7dc828644f63f72`,
est inchangée ; avant création de la révision, ses dépendances et identités
ont été copiées dans
[n56r8_usb_capture_01_source_archive](n56r8_usb_capture_01_source_archive/manifest.json).
Le manifeste d'archive porte le SHA
`c369ded9142e43649cbe68c6dff559236c7b40f0b2eda0830f79ec4b485fee77`.
Ni les preuves matérielles ni l'ancre A/B/A ne sont modifiées.

## Ce que le journal établit

- La garde CPU/ROM/mire a réussi, puis ID `55544e41`, statut0, séquence0.
- La commande1 a produit une nouvelle banque et la séquence1. Les deux
  lectures comparées étaient égales et le compteur inchangé ; sinon
  l'assertion précédente aurait arrêté sur `snapshot changed`.
- Le contrôle ID/version/commande de cette banque a échoué. Les valeurs
  brutes n'avaient pas été journalisées : on ne sait pas lequel des trois
  mots était différent ni si la banque présentait un décalage.
- Le nettoyage Tcl du même processus a envoyé commande4, reçu séquence2
  et une banque cohérente ID/version/commande4. Le disarm a été acquitté.
- Cette dernière banque contient `ticks=0x891fa8` (8 986 536), armed avant
  disarm=1 et les compteurs RXERROR/SOF/reset à0.

La commande1 a donc armé le bloc et le domaine PHY a compté des cycles.
Les captures ont circulé entre PHY et AHB. Cela ne mesure pas la fréquence
réelle. La fenêtre de 1 s n'a **pas** été atteinte : l'erreur ARM précède
`sleep 1000`. À 60 MHz nominal, le nombre de ticks représente environ
0,150 s ; ce calcul est conditionnel, pas une mesure temporelle indépendante.
Les zéros ne décrivent que cette courte fenêtre.

## Le contrat pré-clear ne permet pas un mauvais en-tête

Dans le [RTL figé](../../../../tang/impl/console_neo_n56r8_hdmi_sg4/source/tang/rtl/usb/usb_idle_trace.v),
`live` se termine par `{command,32'd1,32'h55544e41}` (lignes151–155).
Quand `cmd_pop` est vrai, `snapshot<=live` précède logiquement les effets
non bloquants de clear/arm sur les compteurs (lignes156–185).
L'état **des compteurs et de armed** est donc pré-clear ; les mots0/1
restent ID/version et le mot2 est la commande courante, y compris pour le
premier ARM. Garder ces trois assertions est conforme au RTL.

Les deux FIFOs utilisent les spécialisations largeur32/profondeur4 et
largeur32/profondeur32. La substitution Neo en registres de `ddr_dcfifo`
ne concerne que largeur100/64 et profondeur4 ; les FIFOs USB conservent
la mémoire inférée et leur registre de tête. Le contrat RTL publie une
tête valide après la synchronisation du pointeur d'écriture ; il n'autorise
pas un premier mot arbitraire. Ni une corruption de mémoire FIFO, ni un
problème de timing ou de lecture AHB ne sont démontrés par ce journal.

Le banc RTL existant `TESTS/rtl/usb_idle_trace_tb.sv:53–55` attend la fin
de l'armement mais ne lit pas sa banque. Les lectures vérifiées se font
ensuite dans `capture()`. Cette couverture ne prouve donc pas à elle seule
le contenu de la première banque ARM sur le bitstream matériel.

## Révision r2 : journalisation seule

[probe_n56r8_usb_ahb_r2.py](probe_n56r8_usb_ahb_r2.py), SHA
`4d74bcec9f3c2b42d79a17829e851bb7ed505ce722706739e4e4b485b421ed33`,
ajoute exactement deux lignes Tcl : une après chacune des deux lectures
de banque, avant leurs assertions. Chaque banque est affichée même si
son ID, sa version, sa commande, sa stabilité ou son compteur est refusé.
Toutes les gardes, écritures autorisées et assertions restent identiques.

`--check-only` PASS. `test_usb_ahb_r2.py` : deux tests PASS en 0,012 s,
avec cas nominal et corruption successive de chacun des trois mots
d'en-tête ARM : les deux bruts sont conservés, l'erreur est maintenue et
le disarm simulé est confirmé. Aucun accès carte ni build par l'auteur.

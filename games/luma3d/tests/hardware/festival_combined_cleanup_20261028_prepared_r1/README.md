# Nettoyage minimal avant FC1

Préparé seulement ; root seul ouvre la console. Deux fichiers strictement autorisés :
- /tmp/gm1-baseline :8619636octets,CRC80db0d69,archive baseline-riscv SHA028214fd64380ced18558658c3c20641c945df00505b9443c41ddb8f865d886f.
- /tmp/gm1-candidate :10029328octets,CRC1accf6e5,archive candidate-riscv SHA349ff11131b3b97d1787b0815725dff367c99e75b637e59853bf2c25b3f1b0cb.

Archives relues intégralement localement pendant préparation, SHA+CRC+taille exacts. Elles restent conservées. Leplan lie l'inventaire root et lesdeux scripts ; aucun autre chemin supprimable, aucune suppressionrécursive ou jokerdansrm. Le scan/proc contient unglob uniquement enlecture.

Avant chaque suppression : santéFM4A complète (PID3940/start35705238,argv/exe,pidfile), sauvegardeGM1SHA protégée, GPU0; le même sous-shell fait CRC intégral,taille, scanexes, contrôlePID/startticks puisrmducheminlittéral. Unexe illisible estrefusé saufprocessdisparu,zombieouthreadnoyauPF_KTHREAD. Le contrôle initialtest-L seulseraitinsuffisant car/proc/kernelthread/exe peutêtreunliencassé. Les threadsne sont jamais signalés. FM4A normal,GM1normal,saves/logs/SD restent exclus.

La vérification processus est uninstantané puiscontrôleimmédiat, pasuneprimitiveatomiquecontreunexecconcurrent hostile. Root atteste l'exclusivitéconsole; toutautrelancement de cesbenchmarks pendantla fenêtre invalideraitcettehypothèse. Pasd'arrêtglobal pourrésoudrecerisquehypothétique.

Après, mêmesidentité/save/GPU0et progression,puisdf. Toute erreur arrête la suite ; si le retour shell estincertain, aucunnouvelordre niannulationauto, root doitreprendrele diagnostic. Une suppressiondéjàconfirmée restesignaldansresult.removed. Pas d'auto-retry.

Tests :deuxsyntaxes/bin/sh,6refusdetaille,5cheminsprotégésrefusés,6pannesdegardeinjectées,4revuesinvalides. Preuvelisteexactedescommandesdans tests.json. Aucunecommandermexécutéependantlestests.

Réutilisation sanscopie/sansmodificationdupaquetFC1gelé : --runtime désignele dossierdéjàuploadéfestival_combined_20261028_prepared_r1. Sesempreintessontrevérifiéesavantimport. --run estobligatoirepourtoutaccèsdevice.

Commande root après revue fraîche :
```
python3 -B cleanup.py --runtime RUNTIME_FC1_DIRECTORY --run --expected-plan PLAN_SHA --review ROOT_REVIEW.json --out NEW_RESULT_DIRECTORY
```

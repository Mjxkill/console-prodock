# Revue ciblée de --cpu-readback

Aucun bloqueur trouvé dans l’ajout lu. BIN588B SHA aa2a1a… chargé/vérifié à
0xa0005000, journal256B à6400 séparé du BIN02/ancienjournal. Les captures
AFTER/AFTER100 précèdent le traficCPU. Gardes Tcl MD12/1/8/−5 et32/32 cohérentes
avec BIN02 ; le lecteur recontrôle cache/ILM/SATP/interruptions/FB avantDDR.
Aucun storeDDR ou commandeGPU du lecteur. Les captures demandent seulement
le snapshotNGDB ; aucune lectureDDR par OpenOCD.

Le champ diagnostic_passed reste attaché au premier testGPU et faux pourle
blocage ; readback_valid est distinct. Le journal incomplet reste un échec,
pas un motif DDR nul. IO.observe hérité de warm_mode1_trial.py utilise
run_child(...,30) : watchdoghôte30s, halt1000ms dansTcl puis restaurationR19
finally inchangée. Le secondstage peut lui-même bloquer surun load et nepas
atteindre son halt ; ce cas dépend de ce watchdog et de la restauration.

La qualification matériel, le choixdu moment et l’exécution sont propriété
root. Cette revue statique ne lance aucunTcl et ne remplacepas ses gardes
locales/injections. Aucun fichierducontrôleur modifié.

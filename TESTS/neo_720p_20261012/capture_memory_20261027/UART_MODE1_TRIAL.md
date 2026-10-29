# Essai UART mode 1 préparé, non exécuté par le sous-agent

Le contrôleur est `warm_mode1_trial.py`. Son mode par défaut et
`--check-only` ne font que des vérifications de fichiers. Seul le parent,
opérateur exclusif Neo, peut lancer `--run` après sa revue.

## Identités et point de départ

- R19 : `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
- R21r1 : `2fd6f3b01bee26a835aefcef3c34712de649f0af4e1fa24ff5bb4983430200d7`.
- Ancre : `startup_100k_20261027_090320/result.json`, vérification finale R19
  CPU arrêté en parking ROM, GPU/NCP frais. La photo finale séparée
  `r19_after_check.jpg` est liée par son empreinte dans le contrôleur.
- Neo : programmateur Sipeed série `2025041420`, branche `3-4.4.1` ;
  ESP-Prog `3-4.4.2`. UART Sipeed interface 01, 2 Mbit/s, 8N1.

## Discrimination prévue

Sur R19, deux ARM/SNAP de l'observateur portent `arm_count` et
`sequence_id` à 2. Aucune commande GPU ni écriture DDR n'est envoyée.
Une session JTAG séparée relit ces deux compteurs avant ouverture UART.
Après ouverture, le contrôleur exige encore 2/2 avant d'écrire la trame.
Il envoie une seule fois `a5 5a 52 31 35 01 fe 0d`, puis exige 0/0 pendant
que le même port reste ouvert. Une lecture supplémentaire suit la fermeture.
Ainsi, l'ouverture ou la fermeture seule ne peut expliquer le témoin accepté.

Le RTL figé accepte le mode 1 après vérification du préfixe, du complément
et du dernier octet. Il conserve les 50 ms de délai, le hold de 20 µs, la
condition DDR prête et la synchronisation existante. Le changement NCP 2/2
vers 0/0 constitue un témoin de reset ; il ne mesure pas directement
`command_epoch`, qui n'est pas exporté.

Ensuite seulement R21r1 exact est programmé en SRAM. Une photo précède la
première tentative DMI à 100 kHz, limitée à 30 s. Si cette tentative échoue,
une seule trame mode 1 est envoyée, puis une nouvelle photo précède la seconde
tentative. Sans reprise DMI, la réception UART sur R21 reste inconnue : le
succès du témoin R19 ne prouve pas celui de R21. R19 est alors restauré et
vérifié. Si R21 démarre sans trame ou après la trame, il reste arrêté dans le
parking ROM avec GPU/NCP frais, sans test de rendu.

Le contrôleur ne demande aucun `resume` au debugger. Un reset peut toutefois
faire exécuter la ROM par le CPU avant le prochain `halt` ; le rapport utilise
donc `CPU_ROM_restart_possible`, sans prétendre une absence totale d'exécution.

## Preuves et limites

`warm_mode1_controller_test_01.json` : 16 tests locaux de contrôle de flux et
d'erreurs, sans matériel. Ils couvrent l'absence de mutation si l'ancre live
échoue, l'arrêt avant R21 si le témoin R19 échoue, les deux issues de reprise,
la restauration, les noms de photo/journal distincts, le rejet d'un statut
FPGA sans DONE et l'enregistrement du SHA après DONE avant délai/lecture CPU.
Le double échec de reprise puis restauration vérifie aussi qu'une seule
tentative de restauration est lancée.
Ces tests ne qualifient ni l'UART physique ni le fonctionnement de R21.

Le statut de qualification global R21 reste FAIL. DONE sans erreur est le
statut du programmateur, pas une relecture exhaustive de sa SRAM. L'essai
ne touche ni SD, ni flash, ni Linux, ni Pro Dock ; il ne lance aucun routage.
Une erreur caméra est enregistrée explicitement et ne vaut pas observation
visuelle. Les journaux DMI/UART et la photo doivent être interprétés séparément.

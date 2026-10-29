# R3 rejeté avant chargement matériel

Le bitstream `console_prodock_sd_boot_20261028_r3.fs`, SHA-256
`5b516ea97edc04b64a28c5364743ed149216a4359b9e23cc0130e2e8fa7d6859`,
ne constitue **pas** un chargeur SD. Il a été transféré sur ax15, mais n'a
été ni chargé en SRAM ni écrit en flash.

La vérification des primitives SP du netlist après routage retrouve les
paramètres ITCM de G22r0, avec ses anciennes chaînes de diagnostic. Les
fichiers `itcm0..3` préparés correspondent pourtant au nouveau chargeur
`d8ab75277c4cb4eb2a4123fbdf269d96fa8a5cd44cb84eaa11c8e3fdf66d8ae8`.

Cause dans le constructeur : le fichier fournisseur `riscv_ae350_soc.v`
est une netlist déjà synthétisée, dont les initialisations sont intégrées.
Modifier `gw_itcm_config.v` sans régénérer cette IP ne les remplace pas.
Il ne s'agit pas d'une preuve de défaut du routage incrémental de Gowin.

Le constructeur est corrigé pour régénérer l'IP dans le seul dossier candidat,
avec les configurations Pro Dock et les quatre nouveaux fichiers ITCM.
Le candidat R4 est en construction. Sa ROM doit être reconstruite depuis
le netlist après routage et comparée au binaire attendu avant essai carte.
Le contrôle est ajouté aux exécutions futures du constructeur ; R4, déjà
lancé au moment de cet ajout, doit recevoir explicitement ce contrôle.

La SD préparée et vérifiée reste valable. La référence G22r0 et la première
Pro Dock n'ont pas été modifiées par cette correction.

## Addendum matériel du 29 octobre 2026

Le constat ci-dessus décrit la décision initiale, avant les essais R5.
R3 a ensuite été chargé **uniquement en SRAM**, sur la nouvelle Pro Dock
2025071717, comme contrôle USB avec l'ancienne ROM. Il n'a pas été présenté
comme un chargeur SD et n'a pas été écrit en flash.

La configuration FPGA aboutit, mais aucune console USB n'apparaît pendant
60 secondes. G22r0 exact, remis ensuite sur la même carte et le même port,
énumère en HS 480 Mbit/s et répond aux requêtes EP0 et à la commande CPU `?`.
Le défaut des builds reconstruits ne nécessite donc pas la nouvelle ROM SD.
La cause physique ou logique de l'absence d'USB reste indéterminée.
Voir [les preuves comparées](r5_hardware_01/README.md).

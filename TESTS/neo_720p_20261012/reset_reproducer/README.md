# Neo GW5AST-138C : reproduction autonome d’un reset bloqué sur LW

Résultat mesuré le 15 octobre 2026, Gowin **V1.9.12**, cible
**GW5AST-LV138PG484AC1/I0**, programmateur Neo 2025041420.

Le même RTL et une netlist identique (seuls les commentaires date/chemins
changent) donnent ces résultats. Les contraintes changent uniquement le
routage des quatre copies du reset. Aucun CPU, contrôleur DDR, FIFO,
USB, SD, GPU ni IP chiffrée n'est nécessaire au reproducteur.

| Variante | Routage réellement publié du reset 3 | Setup / hold violés | UART reçue en 20 s | Valeur des quatre resets | Erreurs |
|---|---|---|---:|---|---|
| Automatique | LW | 0 / 0 | 955 trames, 60 époques | 0111 | bit 3 constamment différent |
| Demande LOCAL_CLOCK | PRIMARY | 0 / 0 | 954 trames, 60 époques | 1111 | 0 |

La demande LOCAL_CLOCK aboutit ici à PRIMARY ; il ne faut pas la présenter
comme un routage local constaté. Les rapports complets sont inclus.

Les quatre DFFCE et le second étage de référence ont les mêmes D, CLK,
CLEAR et CE. Le circuit déclenche un reset de 256 cycles toutes les 2^24
périodes de l'horloge 50 MHz. Quatre chaînes à décalage de 512, 1024,
2048 et 4096 bascules fournissent des charges différentes. Le moniteur
ne dépend pas du reset testé et conserve les erreurs après les resets.

Sortie UART U15 à 2 Mbauds : R, 40 chiffres hexadécimaux, LF. Les 20 octets
codés contiennent 0x5251, masque d'erreurs et copies, référence, époque
32 bits, compteur d'erreurs 32 bits puis quatre signatures 16 bits.
La broche d'horloge est V22 et la LED V13. Aucun autre port de carte.

Simulation Icarus : 20 phases de reset, assertion avec horloge arrêtée,
libération uniquement après reprise, faute injectée détectée et retenue ;
une deuxième simulation vérifie les 42 octets UART et leur atomicité.

Un second passage (`../reset_probe_board_repeat`) n'a reçu aucun octet
UART sur **les deux** variantes. Il est non concluant, sans mesure du
reset ; ce n'est ni une reproduction positive ni une réfutation du premier
passage. Les restaurations N34r1 passent les préflights DDR et GPU.

Conclusion limitée : défaut de distribution du signal reproductible dans
le premier A/B, sur cette Neo et cette chaîne de génération. Il reste à
séparer le logiciel de routage/génération de bitstream, la révision du
silicium et les conditions de chargement. Aucun erratum matériel universel
n'est démontré. Aucun essai identique n'a été fait sur la Pro Dock.

Sources et captures brutes : `../reset_probe_board/` ; simulation :
`../../rtl/neo_reset_probe_tb.sv` et `../../rtl/neo_reset_probe_uart_tb.sv`.
Les outils `tools/neo/build_reset_probe.py` et `run_reset_probe.py`
figent, contrôlent et testent le circuit avec restauration de la console.

# Analyse du banc croisé CPU128 / GPU256 / scanout

## Objet et composition vérifiés

Le banc instancie la copie R19 de `ddr_ui_adapt` (interface CPU 128 bits,
adresses en mots16) puis `ddr_gpu_arb` (port CPU 256 bits, scanout et
blitter/GPU), terminés par `native_memory`, modèle octet ordonné externe.
Les deux RTL protégés et `native_memory.sv` n'ont pas été modifiés ; seuls
`bench.sv` et ce fichier ont changé.

La comparaison est faite uniquement aux ports publics. `exp_mem` est construit
à partir des opérations de haut niveau (écritures CPU avec rotation/masque,
écritures GPU masquées), jamais depuis `native_memory.bytes`, les tags ou les
pointeurs internes. Chaque réponse CPU, scanout et blitter est comparée à la
requête attendue de son propre client. Les 16 combinaisons moitié/rotation CPU
sont exercées, avec lectures concurrentes des trois clients et écritures
CPU/GPU injectées dans des plages disjointes, puis relecture de ces plages et
d'un canari non écrit.

## Corrections de qualité du banc

1. Les producteurs concurrents du `fork` (`CPU_MIX`, `BLIT_MIX`) n'utilisent
   plus l'entier partagé `j` : chaque branche possède son indice local (`cj`
   ou `bj`) et son tampon local (`cwd` ou `bwd`). Aucun producteur concurrent
   ne partage donc d'état de boucle ou de charge utile.
2. Les deux attentes fixes `repeat (128)` de drainage des écritures ont été
   supprimées. Un compteur `native_wr_accepted` ne compte que l'acceptation
   réelle au port terminal externe :
   `m_en && m_ready && m_cmd==3'b000 && m_wr_en && m_wr_end && m_wr_ready`.
   Les acceptations côté producteur (`u_cmd_ready`/`u_wr_data_rdy` et
   `b_ready`) sont comptées séparément (`cpu_wr_issued`, `gpu_wr_issued`) et ne
   sont pas considérées comme la fin DDR. `wait_native_writes` attend le
   nombre d'écritures déjà émises, avec une borne de 4000 cycles, avant le
   mélange de lectures puis avant les relectures.
3. Un chien de garde global indépendant impose une borne de 20000 cycles à la
   completion de tout le stimulus (`bench_done`). Les timeouts locaux des
   pilotes et du drainage restent en place.

## Résultats mesurés (exécution protégée réelle, après correction)

Compilation Verilator réussie avec `VM_PARALLEL_BUILDS=0` ; cinq cas exécutés :

- `seed=1 fault=0` : code retour 0, `PASS cpu=16 scan=11 blit=11 rotations=16 outstanding=11`.
- `seed=8 fault=0` : code retour 0, `PASS cpu=16 scan=11 blit=11 rotations=16 outstanding=11`.
- `seed=1 fault=1` : code retour -6, `CHECK_FAIL DATA scanout` (`bench.sv:199`),
  données reçues différentes de l'attendu après injection XOR.
- `seed=1 fault=2` : code retour -6, `CHECK_FAIL DATA cpu` (`bench.sv:188`),
  après `INJECT dropped_response=0` : la réponse omise est détectée par
  comparaison de données, pas par un simple arrêt.
- `seed=1 fault=3` : code retour -6, `CHECK_FAIL TIMEOUT cpu read ready`
  (`bench.sv:294`, temps simulé 20730000), réponse absente bornée.

Le harnais protégé conclut `"passed": true` pour l'ensemble. Les deux seeds
saines satisfont cpu>=16, scan>=8, blit>=8, rotations=16 et outstanding>=3.
L'observation `outstanding=11` (au lieu de 12 avant suppression des délais
fixes) est une mesure réelle du recouvrement natif pour cette exécution ; elle
reste au-dessus du seuil exigé.

## Portée et limites

- `native_memory` est un terminal octet ordonné, pas le contrôleur/PHY DDR3
  Gowin. Dans ce modèle, l'acceptation terminale d'une écriture vaut mise à
  jour des octets ; ce n'est pas une preuve de completion DDR physique
  (latence, banques, rafraîchissement, calibration, timing, métastabilité,
  caches et netlist ne sont pas qualifiés).
- Un PASS réfute seulement, pour ces stimuli, l'hypothèse de mélange des
  étiquettes propriétaire/moitié/rotation sous lectures CPU/GPU/scanout
  concurrentes. Il n'explique pas le défaut carte et ne constitue pas un
  défaut matériel identifié.
- Les fautes `+fault1` (XOR), `+fault2` (retour omis) et `+fault3` (aucun
  retour) sont des contrôles négatifs du banc, pas des causes attribuées au
  DUT ou à la carte.
- Aucun DMA, aucune fusion avec les collectes R22r1/R21r1, aucun matériel,
  réseau ou bitstream n'a été utilisé. Les bornes du banc restent finies
  (2000 cycles par pilote, 4000 cycles par drainage/attente d'écritures,
  20000 cycles pour le chien de garde global).

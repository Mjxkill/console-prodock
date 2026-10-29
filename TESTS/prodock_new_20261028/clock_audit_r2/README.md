# Audit des horloges Pro Dock SD R2 / référence G22r0

2026-10-28 — lecture seule des builds, aucun compilateur, optimiseur ou accès
matériel lancé. Le candidat R3 du parent est indépendant de cet audit.

**Les trois avertissements PR1014 de R2 sont identiques à ceux de G22r0.**
Ils ne constituent pas un changement de routage démontré. Le routage exact
de R2 ne peut pas être extrait par l'outil maison actuel : son `.pr` est
propriétaire et ses rapports post-routage sont absents après SIGSEGV.

## Ce qui est vérifié

`python3 -B TESTS/prodock_new_20261028/clock_audit_r2/audit.py` produit
`result.json`, avec empreintes de netlists, contraintes, journaux, caches
PR et outils. Il utilise `optimizer.reports.clock_routing` existant pour
les ressources publiées, et suit les connexions directes des trois nets
dans les hiérarchies des netlists synthétisées.

- Les 128 fichiers source historiques sont contrôlés contre le manifeste
  G22r0. Un seul diffère dans R2 : `gw_itcm_config.v`, chemin d'initialisation
  ITCM. Les nouveaux fichiers du firmware de boot sont hors cet ensemble.
- Les CST résolus sont identiques octet pour octet ; les SDC également.
- Les trois textes PR1014 sont identiques : G22r0 `build.log:22-24`,
  R2 `build.log:498-500`.
- Les connexions directes des trois horloges, suivies de module en module,
  sont identiques jusqu'aux primitives ou boîtes noires observables.
  `clk_d` a 824 connexions de feuille observées, `ae350_tck_d` et `rtc_clk`
  en ont deux chacune. Ces nombres incluent les ports de sortie des sources,
  et ne sont ni une mesure de skew ni un comptage des pistes physiques.
- Les deux tests pertinents du parseur maison passent : conservation des
  ressources multiples/longs noms et absence de rapport qui reste inconnue.

## Classification des trois avertissements

| Net | Contrat logique et contraintes inchangés | Route G22r0 publiée | Route R2 observée |
|---|---|---|---|
| `clk_d` | IBUF depuis `clk`, P16 ; `CLOCK_LOC ... BUFG[0] = CLK` ; domaine source 50 MHz | `PRIMARY`, `PTR0 PTR1 PTR3 PBR0 PBR1 PBR3` | PR1014 seulement, détails inconnus |
| `ae350_tck_d` | IBUF depuis `ae350_tck`, C24, vers le port JTAG de la macro AE350 ; pas de nouvelle contrainte globale | Absent de la table des réseaux globaux ; PR1014 présent | PR1014 seulement, détails inconnus |
| `rtc_clk` | PLL AE350 `CLKOUT4` vers macro AE350 ; période SDC 100 ns ; `CLOCK_LOC "rtc_clk" LOCAL_CLOCK` | Absent de la table des réseaux globaux ; PR1014 présent | PR1014 seulement, détails inconnus |

La preuve `PRIMARY` pour `clk_d` et le PR1014 coexistent dans G22r0. Il est
donc incorrect de traduire cet avertissement par « toute l'horloge clk_d
est routée en LW/local ». Le warning signale l'utilisation de ressources
génériques ; il ne localise pas les branches concernées ni leur délai.
Une partie d'une distribution peut être globale sans que tous ses raccords
soient des pistes dédiées. L'identité précise des raccords concernés n'est
pas établie ici.

L'absence de `rtc_clk` ou `ae350_tck_d` dans la table n'est pas la preuve
qu'ils sont coupés. Les connexions synthétisées sont présentes ; le rapport
liste les réseaux globaux, pas chaque liaison locale ni les chemins internes
de la macro CPU.

## Limites et conséquences

`optimizer/README.md:355-360` indique explicitement que les `.p`/`.pr` ne
sont pas décodés. Les lignes de la visualisation relient des cellules et ne
représentent pas les pistes physiques. L'audit n'utilise pas des chaînes
lisibles éventuelles du binaire PR comme preuve de routage.

R2 a produit un `.pr` de 335 301 361 octets, mais pas de `.rpt.txt`, `.tr`,
`.vo`, `.sdf` ou `.fs`. Son état physique reste **UNKNOWN**, pas PASS ni
« même routage que G22r0 ». La comparaison de connexions ne traverse pas
les boîtes noires chiffrées et n'est pas une preuve d'équivalence de tous
les paramètres, de l'initialisation ROM ou des performances.

La référence G22r0 fonctionnelle conserve ses limites documentées : setup
minimal historique −0,564 ns et neuf violations setup. Sa réussite matérielle
ne qualifie pas R2/R3. En revanche, attribuer le SIGSEGV de R2 ou une panne
matérielle à ces trois warnings anciens ne serait pas étayé par ces preuves.

À la fin de R3, le parent pourra comparer la table « Global Clock Signals »
et les rapports temporels réellement produits. Ce sera une nouvelle preuve,
pas un résultat anticipé de cet audit. Aucun changement de contraintes ou
essai de routage n'est proposé ici.

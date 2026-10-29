# Prochaine expérience GAO : portée et critères

Le diagnostic STA établi est une distribution TCK avec un déséquilibre
entre émetteurs et récepteurs. Sur le pire chemin, `u_gw_jtag/tck_o` atteint
le registre de départ après5,890ns, puis le registre d'arrivée après6,846ns.
Le retard supplémentaire de l'horloge de capture est0,956ns alors que les
données traversent C2Q+route en0,539ns. Le hold finit à−0,384ns. Pour
`address_counter_4` → RAM4 `ADB[6]`, les branches d'horloge sont3,787ns et
5,180ns, avec hold−0,348ns. Ces faits viennent des
[chemins complets de R10](../gao_startup_audit/gao_hold_paths.txt), pas d'une
mesure matérielle de corruption.

Le front JTAG traverse `tck_pad_i` → IBUF `tck_i_c` → `GW_JTAG.tck_o`.
Le dernier segment porte250charges dans le TR ; son nom dans le netlist
GAO généré est `control0[0]`. Le segment du pad ne porte qu'une charge.
L'expérience envisagée par root vise donc cette sortie, avec une unique
contrainte `CLOCK_LOC "control0[0]" BUFS = CLK;`, sous réserve que Gowin
accepte la résolution de ce net GAO depuis le CST. Une erreur CT1135
signifierait un refus d'accès à la contrainte, pas un candidat routé.

Le candidat indépendant devra prouver la distribution réellement utilisée
par ces250charges, les huit PRIMARY applicatifs conservés, les marges
setup/hold/recovery/removal complètes, les treize anciens chemins et tous
les nouveaux échecs éventuels. L'acceptation syntaxique du CST ne prouve
pas l'application de la contrainte. Le dernier emplacement LW libre ne
garantit ni une allocation possible ni la résolution du skew. La fréquence
et les exceptions de timing restent inchangées ; ralentir TCK seul ne
corrige pas la relation entre deux fronts identiques.

Deux variantes distinctes restent possibles, sans les mélanger à cette
première expérience :

- `Force Trigger by Falling Edge` modifie certains registres pilotés par
  TCK selon SUG114-3.4.4E p24. Le fournisseur n'énumère pas les registres
  concernés dans ce passage. Le pire chemin est déjà F/F ; cette option
  ne constitue donc pas une solution démontrée aux treize violations.
- Stockage REG avec16échantillons :16×21=336bits respecte la limite
  documentaire512bits. À50MHz, la fenêtre vaut320ns ; la position de
  trigger128 doit devenir valide pour cette profondeur. Cette variante
  serait surtout utile pour une capture forcée tardive d'états stables.
  Elle supprime les chemins BSRAM actuels (neuf `ADB`, un `CEB`), mais les
  trois chemins logiques actuels subsistent dans le problème à vérifier :
  `enable_reg` F/F et deux `internal_register_select` R/R. Le nouveau
  placement et le multiplexage REG peuvent modifier leurs marges.

Aucun de ces changements n'a été effectué dans R10 par cet audit.

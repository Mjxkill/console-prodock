# Deux expériences distinctes possibles depuis R9

**Analyse seulement. Aucun CST, RTL, netlist, SDC ou constructeur actif n’est modifié ; aucun routage n’est lancé.** Les [cellules, broches, fanouts et 293 arcs SDF relevés](future_cones.json) sont liés aux empreintes des fichiers R9. Les lieux absents du rapport STA restent inconnus. Aucun gain n’est prédit.

L’échec DMI du premier essai et la vérification ultérieure réussie du repli N56r8 à 100 kHz sont des observations de démarrage/debug distinctes. Les données STA ne les expliquent pas à elles seules. Les essais de placement ci-dessous ne remplaceraient pas leur diagnostic.

## 1. Reset pixel : déplacer seulement les deux étages prst

Les deux chemins recovery négatifs relient `u_soc/vid_hrstn_r_s0` R50C120 aux DFFCE `u_gpu/prst_0_s0` et `prst_1_s0`, R103C173. Ils ont chacun −0,360 ns, dont 7,425 ns de route. Aucun des deux DFF n’est ancré actuellement.

La topologie réelle est simple et doit rester exacte : prst0 reçoit D=1, prst1 reçoit uniquement Q(prst0), les deux ont CLK=pixel_clk, CE=1, INIT=0 et le même CLEAR asynchrone. L’arc prst0→prst1 vaut 0,396 ns maximum SDF. Aucune modification du nombre d’étages ni de la polarité n’est proposée.

Une expérience CST minimale ajouterait **deux INS_LOC**, dans une petite région commune plus proche de la source de reset, par exemple R[80:95]C[150:175]. Cette région est une hypothèse à revoir avant construction : les mrst voisins, à R95C176, ont une route de reset de 7,034 ns et une recovery positive, mais cela ne prédit pas le délai des prst ni leur skew d’horloge.

Le coût à surveiller est la distribution en sortie de prst1 : cinq entrées LUT et un inverseur, avec des routes actuellement entre 0 et 2,583 ns. L’inverseur alimente **258 RESET et un SET** du scanout, notamment ses compteurs, coordonnées et demandes de ligne. Déplacer les deux DFF peut raccourcir leur CLEAR et allonger cette distribution synchrone. Ne pas ajouter l’inverseur ou ses 259 charges au premier essai : cela élargirait fortement l’expérience.

Contrôles après routage : les deux recovery prst et leur removal, la liaison prst0→prst1, les six branches de prst1, les 259 destinations du reset dérivé, les marges HDMI et mrst/up/engine_resetn, puis le timing global et les nouvelles allocations LW. Les contraintes DDR et la source `vid_hrstn` restent identiques à R9.

## 2. Busy : réexaminer deux ancrages hérités

Le pire setup R9 est `rp_0_s4 → busy_sync_0_s0`, −0,849 ns, depuis ddr3_sys_clk vers bus80_clk. La route totale est de 6,198 ns, la logique de 2,414 ns. Le chemin traverse la retenue du compteur `fill`, puis deux LUT de statut ; son dernier trajet `gpu_debug_state_96_s0 → n563_s0` prend **4,363 ns**, soit environ 70 % de la route.

Il existe une cause de placement explicite à tester : les **deux** cellules `u_accel/n563_s0` et `u_accel/busy_sync_0_s0` sont forcées R[45:65]C[60:85]. Le blitter/FIFO est maintenant regroupé R[1:25]C[140:175], et sa LUT busy est à R22C142. Ces deux ancrages venaient du [correctif N54r2](../../n54_mask_work_20261020/make_r2_placement.py), qui visait alors un autre détour C42→C133→C44. Leur justification ancienne n’est donc pas directement applicable au placement R9.

La première expérience la plus limitée serait de **retirer seulement ces deux INS_LOC hérités**, en conservant tous les autres ancrages R9, notamment le groupe DMA de huit cellules. Cela laisse le placeur choisir ensemble la LUT et son registre. Une région de remplacement ne devrait être choisie qu’après examen des trois sources : les positions de deux d’entre elles ne figurent pas dans les chemins STA imprimés.

| Branche vers n563, maximum SDF | Coût actuel | Fanout du net source |
|---|---:|---:|
| head_valid_s5 → I0 | 5,783 ns | 6 |
| statut busy du blitter → I1 | 4,363 ns | 10 |
| gpu_debug_state_37_s0 → I2 | 3,157 ns | 3 |
| n563 → busy_sync0.D | 0 ns | 1 |
| busy_sync0.Q → busy_sync1.D | 0,824 ns | 1 |

n563 est une LUT3 INIT `EF`. Son unique sortie va à busy_sync0 ; la sortie de busy_sync0 va uniquement à busy_sync1, lui-même non ancré. Les deux DFF conservent horloge bus, reset et INIT. Il faut protéger les trois entrées, la seconde étape du synchroniseur et le chemin de lecture du registre d’état ; rapprocher seulement la LUT du blitter déplacerait le coût sur une autre branche.

Ne pas déplacer le compteur FIFO ni sa chaîne de retenue pour cette première expérience : leurs liens sont déjà compacts, et leurs autres consommateurs multiplieraient les risques. Ne pas modifier le budget CDC de 8 ns pour masquer ce chemin. La possibilité d’un raccourcissement reste à mesurer, sans présumer d’une fermeture globale du timing.

## Ordre et séparation

Les deux expériences répondent à des problèmes différents. Elles doivent être préparées et comparées **séparément depuis les mêmes entrées R9**, après retour de l’essai matériel en cours et revue du coordinateur. Les deux LUT de position proposées depuis R8 restent une proposition historique non lancée : R9 a déjà réduit plusieurs de leurs arcs de 4,8–5,9 ns. Ni ce progrès ni les pistes ci-dessus ne lèvent le FAIL actuel.

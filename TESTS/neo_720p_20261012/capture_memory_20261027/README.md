# R21 : observation ciblée du COPY et du chemin mémoire

Le candidat ajoute des observations à la netlist exacte R19. Il ne modifie
pas la logique fonctionnelle du GPU, de la DDR, des PLL ou des resets, et
ne constitue pas une correction démontrée des échecs matériels.

Le protocole NCP1 existant, le bus AHB et le registre `held` de 64 bits sont
conservés. Le contrat détaillé est dans `contract.json`.

## Assemblage et preuves locales

- Parent : `console_neo_n56r19_capture_ce_local`, bitstream
  `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
- Helper RTL : `neo_capture_memory.v`, SHA
  `1051163608ea69c7f56ebb2a4363a7ac773285e7284e3f532b377054602f7a90`.
- Helper synthétisé sans E/S : SHA
  `ce8ea7faef323284045dbf410ac7fae1e4bb39803cde43672fa2bbd960510533`.
- Assemblage initial R21 : netlist SHA
  `d773dca99127093b27e713f195b9ff62207c01a7810130c55d5d99499700d4cc`.
- Candidat de format R21r1 : netlist SHA
  `3f49d84ccb8b2001e5afa156b36849705652003fbf4e2a741847dc23f1713338`.

`build_memory_capture.py` prépare et synthétise uniquement le helper puis
assemble la netlist. Le retrait des changements d'observation restitue
l'original octet pour octet. Tous les anciens ports, primitives et INIT
fonctionnels sont vérifiés. Le top, `neo_capture_bus` et `neo_gpu_debug_0`
restent identiques. Les sources communes ne sont pas modifiées.

La synthèse du helper ajoute **huit DFFCE et huit LUT3** par rapport à R19 :
quatre bits sticky et quatre bits supplémentaires conservés dans `held`.
Hors helper, quatre LUT décodent les états COPY et un inverseur restitue
le vrai OR des requêtes pixels à partir du NOR existant. Ce comptage est
celui de la netlist, pas une occupation finale après routage.

`assembled_test_01/result.json` est **PASS** : protocole complet avec le
helper Gowin synthétisé, puis quatre simulations du COPY réel assemblé
avec capture correcte, CE supprimé, Q bloqué et D incorrect. Le banc COPY
extrait la fermeture de dépendances complète de `gpu_geometry` ; il
n'inclut pas le slot de `gpu_accel`. Cette limite est explicite.

`wiring_audit.json` complète cette simulation par la continuité des trois
événements depuis `gpu_accel` jusqu'au helper. Les 64 combinaisons des
sources et les 128 cas état/reset/start sont vérifiés. Toutes les anciennes
déclarations et affectations restent présentes. `root_review_01.json`
consigne une revue structurelle indépendante.

Les simulations RTL complètes du slot/arbitre et les premiers contrôles du
helper sont dans `TESTS/assisted_reviews_20261026/observer_copy_01/README.md`.

## Échec de parsing conservé et variante de format

Le premier lancement R21 s'arrête **avant placement** : le lecteur de netlist
Gowin refuse deux nouveaux fils déclarés après leur première utilisation
(`PA2039`). Les tests Verilog avaient accepté cet ordre de déclaration.
Le journal et `route_result.json` restent dans le dossier R21.

`format_r21r1.py` déplace uniquement trois nouvelles déclarations de fils
dans la liste initiale des déclarations. Les cellules, ports, paramètres,
affectations, sources, CST et SDC restent identiques. `format.diff` contient
les trois déplacements. `root_format_review_01.json` et
`formatted_test_01/result.json` sont **PASS**. Les cas mappés capture normale
et CE absent reproduisent exactement les traces précédentes.

Le routage autorisé de R21r1 est lancé par `route_r21r1.py` ; il lie les
empreintes de l'assemblage, du test et de la revue. Le parsing de R21r1 est
accepté par Gowin et son placement a commencé. Aucun chargement sur carte
n'est lancé par ce constructeur.

## Validation physique encore distincte

`audit_postroute.py` est préparé pour comparer les primitives physiques
à R19, conserver les alias équivalents avec identité du pilote, vérifier
les horloges et contraintes, puis analyser les chemins de capture, sticky
et `held` vers `shadow`. Les résultats doivent être relus avant un essai.

Le timing global FAIL de R19 n'est pas transformé en PASS par l'instrumentation.
Des nets observés reçoivent de nouvelles charges ; un nouveau placement peut
donc modifier le symptôme physique, même avec la logique fonctionnelle intacte.
Les huit bits de largeur ne couvrent pas le descripteur entier, et les quatre
bits sticky indiquent une occurrence sans fournir de compte ni d'ordre.

La contre-revue du contrôle physique a conduit à rendre ses gardes explicites :
le statut agrège invariance, couverture, origines, clocks, bornes et contraintes,
au lieu de ne refléter que le timing global. Les périodes GPU 13,333 ns et bus
12,5 ns doivent correspondre à la fois au SDC et au tableau des clocks STA.
Les chemins sans origine, clock ou setup connu bloquent leur garde ; aucun
arc absent n'est remplacé par un délai nul.

Le transfert `held` ajoute deux cycles de bus après détection de l'ACK déjà
synchronisé. Le budget conservateur vérifié vaut donc 25 ns, incluant CQ,
chemin de données et setup de `shadow`. Il ne remplace pas la contrainte
SDC interdomaines de 8 ns ni les violations STA éventuelles. Les 64 entrées
`shadow` sont contrôlées bit à bit. Le helper mappé comporte 59 FF `held` :
les alias synthétisés sont 50→49, 62→60, 63→60 et les bits 55/61 valent zéro.
Les 48 FF de capture, quatre sticky et 64 `shadow` sont des gardes de couverture.
`audit_parser_test_01.json` conserve la lecture complète du SDF R19 et quatre
contrôles négatifs du lecteur / des périodes ; ce test ne qualifie pas R21r1.

## Fin du routage R21r1

Le routage a terminé (`route_result.json`, exit0). `postroute_01/result.json`
conserve l'audit : invariance de l'application, helper physique, couverture,
origines, clocks et contraintes PASS. La borne locale de capture vaut
+0,334 ns et le chemin `held→shadow` maximal2,684 ns. Le résultat global
reste **FAIL setup−2,602 ns / 56 endpoints** ; hold+0,124, recovery+0,381,
removal+0,168 ns. Le bitstream exact est
`2fd6f3b01bee26a835aefcef3c34712de649f0af4e1fa24ff5bb4983430200d7`.

La disposition des deux contre-revues Fable et les limites précises de ces
bornes sont dans `disposition_fable_r2.md`. Aucun chargement carte n'a été
fait par le constructeur ou l'auditeur ; le contrôleur matériel root garde
la décision diagnostique et les résultats matériels distincts.

## Essais matériels du 27 octobre : démarrage R21r1 refusé

Les essais sont consignés dans `hardware_disposition_01.json`. La carte
locale est la Neo, programmateur série `2025041420`. La Pro Dock n'a pas
été touchée. Aucun test COPY/CLEAR n'a pu être exécuté sur R21r1.

1. `board_trial_20261027_085157` : l'ancre R19 répond correctement à 1 MHz.
   Le chargement SRAM R21r1 termine avec DONE, puis le TAP CPU est reconnu
   mais les opérations DMI ne terminent pas. L'essai est arrêté après 40 s,
   avant toute écriture DDR. Le rechargement R19 termine ; sa première
   vérification JTAG à 1 MHz échoue sur des IDCODE incohérents.
2. `fallback_check_20261027_085512` : sans nouveau chargement, lecture JTAG
   à 100 kHz réussie. CPU arrêté à `0x80000004`, GPU et observateur frais,
   mire interne sélectionnée et bandes visibles sur la photo.
3. `startup_100k_20261027_090320` : contrôle A/B/A à 100 kHz. R19 répond,
   R21r1 est chargé et photographié **avant** interrogation CPU : écran
   sans mire. Son TAP répond mais le DMI expire après 30 s. R19 restauré
   répond immédiatement au même contrôle ; les bandes reviennent sur
   `r19_after_check.jpg`.

La Neo est donc laissée sur **R19**, CPU arrêté, GPU frais, mire interne.
Ni SD ni flash écrite, aucune exécution Linux ou commande GPU lancée.
Le premier `result.json` conserve un champ `left_bitstream_sha256` périmé
après son fallback : il désigne R21 malgré le chargement R19. Cette limite
du contrôleur est explicitée, sans réécrire le résultat historique. La
disposition et les lectures ultérieures identifient l'état effectivement
restauré. La photo automatique du deuxième fallback a rencontré un nom
de journal déjà existant ; la photo finale séparée est liée par SHA.

Le correctif de temporisation 50 ms reste présent, avec logique et INIT
CPU/PLL/reset identiques à R19. Cela ne prouve pas que tous les resets
physiques se libèrent correctement. L'échec R21 à 100 kHz exclut la seule
vitesse JTAG de 1 MHz comme explication de ce contrôle ; il n'identifie
pas encore la cause du DMI bloqué. La comparaison routée CPU/JTAG est dans
`cpu_route_compare_01/`. La promotion nouvelle de `u_gpu/prst[1]` sur LW
est une différence à examiner pour l'affichage, pas une cause démontrée
du blocage CPU.

### Contrôle UART mode 1, délai 50 ms conservé

`warm_mode1_20261027_094017/result.json` conserve un essai supplémentaire
du même R21r1. Le témoin R19 est discriminant : deux ARM/SNAP mettent les
compteurs NCP à 2/2 ; ils restent à 2/2 après ouverture du port UART, puis
passent à 0/0 après la trame `a55a52313501fe0d`, avant fermeture du port.
Le CPU revient au parking et la mire reste visible. Le reset est observé
après cette trame ; l'époque UART interne n'est pas directement lisible.

R21r1 échoue encore au premier accès DMI. Les huit octets de la tentative
UART sont acceptés par `write()`, mais la file de transmission hôte ne se
vide pas dans les deux secondes prévues. **Il n'est donc pas démontré que
R21r1 ait reçu cette commande de reset.** L'essai s'arrête sur cette erreur
technique, sans conclure que le reset de 50 ms serait inefficace.
R19 est restauré une seule fois, contrôlé à 100 kHz et photographié avec sa
mire revenue. La carte demeure dans cet état, sans commande GPU/DDR.
`hardware_disposition_02.json` lie ces observations et leurs limites.

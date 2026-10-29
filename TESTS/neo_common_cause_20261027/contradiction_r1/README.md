# Disposition ciblée DeepSeek / Beam — premier tour

Les deux avis n'établissent pas de cause matérielle. Leur prudence sur le FAIL
STA, les ressources LW, l'identité partielle du RTL et la portée des témoins est
utile. Les classements de causes restent des hypothèses, pas des résultats.
Aucune nouvelle simulation ou expérience matérielle n'a été exécutée ici.

| Proposition des avis | Vérification et disposition |
|---|---|
| DeepSeek lignes 6/71–88 : la cible C ou l'ancien IP ne peuvent être la cause commune | Trop fort. L31r8 et R19 réfutent une incompatibilité universelle empêchant tout fonctionnement C/PG484. Ils ne réfutent pas un problème conditionnel de bloc, configuration, ressource ou intégration. Aucun couplage USB→GPU n'est démontré, mais son absence n'est pas prouvée non plus. |
| DeepSeek ligne 20 : SHA manifeste = SHA Tcl | Faux libellé. Le SHA du Tcl est égal à la valeur stockée pour ce fichier dans le manifeste ; le fichier manifeste a son propre SHA. Le paquet contient les deux champs distincts. |
| DeepSeek ligne 141 : FIFO FF pas nécessairement dans R19 | Réfuté directement. Les trois `source/tang/rtl/board/ddr_dcfifo.v` R19/R21r1/R21r2 ont le même SHA `449b5d7e65d3290f0b9cc1d5e574e09191d40bbfe8960f45374d9690e965103b`. Lignes 8–12 : substitution explicite des quatre slots CPU 100/64 bits. Elle était déjà présente dans R19. |
| DeepSeek ligne 150 : COPY rejeté localise au handshake natif/arbitre | Faux. `gpu_copy565.v:78–94` valide le descripteur avant tout accès natif ; `descriptor_bad` peut mener à FINISH. La première requête de lecture n'arrive qu'en READ0, ligne 128. Le rejet observé ne prouve pas que ce chemin ait été exercé. Le header opcode29 ne valide pas les autres 248 bits ni les valeurs TARGET tenues. CLEAR bloqué et COPY rejeté restent deux symptômes distincts. |
| Les deux avis : UTNA `[ID,0,0]` = snapshot stale | Terminologie fausse. `usb_idle_trace.v:74–78` expose ID, busy/rejected et compteur de captures terminées côté AHB. Ce sont bien les trois registres de contrôle lus, sans requête de capture. La banque USB à +40..bc n'a pas été lue. Ces trois valeurs ne mesurent pas l'activité du domaine USB. |
| DeepSeek ligne 216 : source `vid_hrstn` non fournie | L'extrait du paquet omettait cette portion ; la source n'est pas inconnue. `ae350_soc.v:331–332` enregistre `exts_hrstn` sur `exts_hclk`; ligne369 le raccorde à `EXTS_HRSTN`. Dans le `.vo` R21r2, ligne1234562 : sortie hard CPU HRESETN→`u_soc/exts_hrstn`; lignes1122913–1122920 : DFFCE, D=ce net, CLK=vid_hclk, CE=VCC, CLEAR=GND, INIT0, Q=vid_hrstn. Ce n'est pas directement `hrst_sync[1]`, utilisé pour le pont DDR. Cela n'expose pas sa forme d'onde en MMIO. |
| DeepSeek lignes 65–67/113/221/246 : exiger readback SRAM avant attribution ; SHA final différent | Le SHA final est R19 parce que la restauration est systématique et tracée ; ce n'est pas un désaccord de programmation du candidat. `program_coupled.log` contient le chemin FS exact, CRCCheck ON, SecurityBit ON, DONE et statut après programmation sans erreur détectée. `sram_readback_verified=false` reste une limite réelle, pas la preuve d'un chargement incorrect. La proposition de readback/checksum n'est pas exécutable telle quelle sous cette protection ; ne pas confondre checksum logiciel non vérifié et absence de CRC de configuration. |
| Les deux avis : ticks USB positifs excluent une cause commune | Ils excluraient un arrêt total du domaine USB pendant la fenêtre capturée. Ils n'excluent ni défaut transitoire commun antérieur, ni reset libéré différemment, ni bruit/PLL séparées issues de la même référence. Si les deux observations échouent, cela ne prouve pas non plus un reset commun. Il faut conserver cette asymétrie dans les prédictions. |
| Beam ligne 214 : test UTNA « read-only » | Faux périmètre : les commandes 1/6/2 écrivent l'observateur et modifient son état. Elles ne pilotent pas le datapath USB, mais c'est une nouvelle expérience commandée, distincte des lectures terminées. |
| Beam lignes 32/152 : absence de commit/fetch explique frames0 en mode0 | Non démontré et non nécessaire au motif interne : le balayage de base n'attend pas un commit framebuffer. `gpu_scanout.v:245–274` incrémente frames au passage de trame tant que prst est libéré. Le fetch mémoire est séparé et désactivé dans cet essai. |
| Beam lignes 257/278/283 : STA devient latence supplémentaire ; reset donne forcément aléatoire/guards faux ; rejet déterministe sépare logique et physique | Prédictions non fondées. Une violation peut produire mauvaise capture, état stable erroné ou absence d'effet ; une erreur physique peut être répétable. Une simulation RTL sans délais ne manifeste pas une violation STA. Ces propositions ne constituent pas des tests discriminants valides en l'état. |
| Beam ligne 116 : R19 a corruption UART et boot Linux ; ligne283 : R19 déjà qualifié | Chronologie mélangée. Le boot Linux/UART corrompu cité appartient à R1. R19 est un diagnostic au timing FAIL, avec certains témoins matériels réussis, pas une version globalement qualifiée. |
| DeepSeek/Beam : absence d'exception init_sync = chemin non couvert | Le chemin est précisément analysé et FAIL en recovery. L'absence de false_path n'est pas une absence de couverture. Le rapport établit une nouvelle frontière reset ; il faut distinguer sensitisation au démarrage (delay_done0) et libération finale, comme dans la note postroute. Aucun faux chemin à ajouter. |

Les trois expériences déjà effectuées — CLEAR depth avec écritures CPU, COPY16
avec oracle mémoire, R19/candidat/R19 avec mesures vidéo — ne doivent pas être
relancées à l'identique comme « nouveau discriminant ». Une séquence plaçant
CLEAR avant COPY s'arrête sur le blocage connu et n'apporte aucune observation
COPY supplémentaire. Les simulations de qualification reset et les contrôles
mappés existent déjà ; leur répétition n'établirait pas une occurrence physique.

L'apport concret à conserver est le prochain relevé UTNA frais, avec ACK et
banque stable, couplé aux compteurs vidéo et à une vue non obstruée, sous contrôle
root. Ce relevé teste la vie partielle des domaines ; il ne décide pas à lui seul
entre « une cause commune » et « plusieurs défauts ».

Complément vérifié après le premier paquet : `../init_audit_01/` ne trouve aucun
INIT incohérent avec DFFCE/DFFPE dans les quatre netlists. Cette absence de conflit
ne prouve pas la présence des clocks ni la distribution physique des resets.

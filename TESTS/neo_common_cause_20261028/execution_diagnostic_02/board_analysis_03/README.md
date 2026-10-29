# Complément matériel03 — limite observée plus précise

Les snapshots NGDB sont frais (séquences1,2,3), cohérents et répétés identiques.
Après TARGET+CLEAR, host=received=16 ; wp=rp=16, opcode0x1c, ext_command0
0x1c000000, blitter ext_active=1, busy=1, état M_SETUP0x20. Cet état reste
identique au relevé100ms plus tard. done=1 ; aucune erreur déclarée.

Cela ferme un trou de preuve de l'essai02 : les16mots ont franchi la FIFO
de commandes et le blitter a consommé CLEAR. Le blocage persiste ensuite
pendant l'attente de fin de l'extension. Cela ne mesure pas la requête native
DDR ni son accusé. Les en-têtes géométrie/pixel bruts1c000000 sont des indices
supplémentaires, séparés du snapshot atomique.

Les12bits engine_resetn lus sont tous hauts **au point d'observation du
signal source** ; ce n'est pas une mesure de chaque broche reset des cellules
physiques. mrst vaut3. geometry_cycles3 n'incrémente pas pendant PASS dans
le RTL, donc sa stabilité n'est pas une preuve d'absence de clock.

La simulation complète livrée par DeepSeek termine le CLEAR sain ; bloquer
artificiellement m_ready, m_wr_ready ou couper le feedback d'acceptation peut
produire les mêmes done1/busy1/en-têtes. Ce sont des contre-exemples à
l'interprétation « signature unique = cause unique ». Les fautes injectées
ne démontrent pas qu'un de ces défauts existe sur la carte.

La prochaine observation préparée est le lecteur CPU séparé
`../readback_r1/handoff_01.json` : captures AVANT, lecture seule128B vers
journal ILM distinct, captures APRES. Si le CLEAR est présent malgré done1,
on sépare l'écriture de sa complétion ; si le motif est inchangé, l'absence
de modification ne distingue pas encore absence de requête, refus natif ou
autre défaut d'adressage. Si lire débloque le GPU, conserver l'ordre exact
des captures : la lecture CPU constitue une intervention sur l'arbitrage.

Les résultats02 et03 restent FAIL, R19 restauré par root. Aucun accès matériel,
modification RTL, compilation FPGA ou changement Pro Dock dans cette analyse.

## Prédictions supplémentaires de la seconde étape

Dans l'arbitre R19 exact, cpu_fire dépend de issue, m_ready et de l'absence
de sélection blitter/scanout ; issue dépend de !full. Si les32lectures CPU
aboutissent alors que le GPU reste bloqué, m_ready ne peut pas être resté
constamment bas, ni full constamment haut pendant toute la fenêtre utile.
Cela ne prouve pas leur état antérieur ni l'absence de faute physique locale.

Une écriture GPU dont b_valid reste haut et m_wr_ready bas peut retenir
take_blitter lorsque prefer_blitter=1 ; le lecteur CPU peut alors se bloquer
aussi. Le watchdog et le journal partiel ont donc une valeur diagnostique.
Inversement une requête GPU absente/perdue laisse le trajet CPU fonctionner.
Ces prédictions découlent du RTL, pas encore de la prochaine mesure matérielle.

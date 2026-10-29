# CLEAR flags=0 : contrôle du chemin sans requête native GPU

Binaire928B lié à0xa0004000 ; journal512B à0xa0006000 ; même scratch128B
0x12000000..0x1200007f. Le CPU écrit toujours le motif puis le relit avant et
après TARGET. Il attend ensuite CLEAR terminé (done=2 ET busy/full=0), puis
vérifie le motif initial sur les128B. Aucune instruction ou adresse nouvelle.

Les deux seuls mots binaires différents de BIN02 sont :
- offset432 : `li a1,1` devient `li a1,0`, attente de seed partout au contrôlefinal ;
- offset900 : mot de flags CLEAR1 devient0.

Le paquet TARGET reste16x1, couleur12000020, Z12000040, strides32. Le paquet
CLEAR reste1c000000/0/6b4d/0/0/00100001/0/0. Aucun changement deRTL/bitstream.

Tests exacts :11cas RV32 PASS. Les contrôles négatifs détectent une écritureGPU
indue, un canari modifié, un done2 avec busy encore1, les timeouts et les gardes.
La chaîne RTL R19 complète passe8cas (deux horloges/phases, quatre comportements
READY) avec16mots reçus, done2/busy0/rejected0 et aucune assertion de nativeVALID.
Il s’agit de zéro requête native **GPU**, pas de zéro trafic DDR du CPU.

Le format journal reste MD12/version1, mais l’attente de mémoire finale change :
un décodeur qui exige la couleur CLEAR pour les8mots centraux n’est pas adapté.
Le premier test RV32 produit une image seed/seed/seed ; le manifeste identifie
ce programme distinct. Ne pas transformer ce contrôle négatif en qualification
DMA GPU : il vérifie justement la branche qui ne doit pas émettre de DMA.

Gardes, polling borné et limites inchangés de BIN02. Le watchdog hôte reste
nécessaire si un accès AHB se bloque. Root seul décide du chargement/restauration.

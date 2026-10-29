# Mission : vérifier le mélange CPU128 / GPU256 / scanout dans le DDR R19

Implémenter `bench.sv`, puis exécuter réellement `test_bench.py` avec les outils
MCP. `ANALYSIS.md` contient les observations et limites. Tous les autres fichiers
sont protégés. Ne pas proposer de correction au DUT. Aucun matériel, réseau,
nouveau bitstream ou référence à un chemin extérieur à la copie.

## Trou de preuve ciblé

Le banc R19 précédent `neo_fable_sim_01` vérifiait CLEAR/COPY avec le slot réel,
mais CPU et scanout inactifs. L'ancien banc CPU complet les gardait aussi
inactifs. Le banc de l'arbitre seul mélangeait les clients sans adaptateur128.
Ici on teste la COMPOSITION de `ddr_ui_adapt` CPU et `ddr_gpu_arb`, tous deux
copiés octet pour octet du snapshot R19 (empreintes dans INPUTS.json).

Hypothèse réfutable : mélange des étiquettes de propriétaire et des étiquettes
moitié/rotation sous lectures CPU/GPU/scanout concurrentes. Un PASS fonctionnel
réfute seulement cette hypothèse pour ces stimuli. Il n'explique pas le défaut
carte et ne qualifie ni PHY, netlist, timing, métastabilité ni état des caches.
La collecte R22r1 réussissait une matrice sans DMA ; R21r1 ne démarrait pas et
n'a fourni aucune observation de COPY/CLEAR. Ne pas fusionner ces versions.

## Assemblage et modèle externe

Instancier `ddr_ui_adapt` puis connecter ses `ip_*` au port `c_*` de
`ddr_gpu_arb`. Connecter `g_*` à un producteur de lectures scanout et `b_*`
à un producteur GPU/blitter lecture/écriture. `native_memory` est le terminal
ordonné externe, pas l'IP Gowin. Son interface reproduit les ports `m_*` de
l'arbitre. Horloge de 10 ns, reset commun tenu plusieurs fronts.

Les 4096 octets du terminal sont initialement zéro. Seules les commandes
acceptées modifient le modèle. Adresses natives en mots32, alignées sur32B.
Une lecture rend32 octets en ordre croissant. Une écriture masque chaque octet
dont le bit de masque vaut1. Les readys commande et écriture varient séparément.
Latence de lecture positive3..14 cycles, retours ordonnés. Les fautes +fault1
(XOR des données), +fault2 (un retour omis), +fault3 (aucun retour) sont des
contrôles négatifs du banc, pas des causes attribuées à la carte.

## Stimuli minimaux et oracle indépendant

1. Initialiser plusieurs rafales par le client CPU128, deux moitiés et masques
   non triviaux. Faire aussi des écritures GPU256 partiellement masquées vers
   ces mêmes rafales. Construire l'attendu OCTET PAR OCTET à partir des opérations
   de haut niveau. Ne jamais lire `native_memory.bytes`, les tags, pointeurs,
   full, grants internes ou autre état interne du DUT comme référence.
2. Après drainage borné des écritures, lancer un mélange de lectures des trois
   clients sur ces données, dont les16 combinaisons CPU moitié/rotation.
   Au moins16 retours CPU,8 scanout,8 blitter, et3 lectures natives en vol.
   Chaque réponse se compare à la requête attendue de son propre client,
   jamais à une donnée simplement recopiée depuis le bus natif reçu.
3. Exercer aussi des écritures CPU et GPU pendant ces lectures sur des plages
   DISJOINTES des lectures en cours. Leur contrôle ne doit pas dépendre d'un
   ordre inter-maître non spécifié. Après drainage, lire ces plages et les
   canaris non masqués. Les adresses restent toutes dans `[0,4096)`.
4. Les opérations CPU128 utilisent l'adresse en mots16. Pour une adresse U,
   la rafale16B a pour base `(U & ~7)*2`. Le premier mot présenté correspond
   à l'offset `(U & 7)*2`; les octets suivants tournent dans ces16B. L'oracle
   effectue cette indexation d'octets, sans recopier rotl128/rotr128 du DUT.
5. Respecter les handshakes : CPU command_en seulement au front ready et,
   pour écrire, wr_ready ; commande+data simultanés. GPU et scanout gardent
   valid/payload stables jusqu'au ready. Piloter au front descendant et
   échantillonner au front montant pour éviter les races du banc.

Les attentes sont bornées en cycles. Une mauvaise donnée/propriétaire doit
échouer par `$fatal(1,"CHECK_FAIL DATA ...")` ou `CHECK_FAIL ROUTE`; une réponse
manquante par `CHECK_FAIL TIMEOUT`. En succès seulement, afficher :
`PASS cpu=N scan=N blit=N rotations=16 outstanding=N` avec compteurs réels.
Ne pas dériver les compteurs de paramètres ou de constantes d'intention.

Le runner protégé compile avec Verilator puis exécute2 latences saines et3 fautes.
Commencer par `taskbox_run_tests` pour constater le module inachevé, écrire
uniquement les deux fichiers autorisés, relancer et corriger dans cette même
session. Modules commentés, moins de1000 lignes physiques. Le résumé final
doit distinguer un vrai défaut trouvé du simple succès du modèle ordonné.

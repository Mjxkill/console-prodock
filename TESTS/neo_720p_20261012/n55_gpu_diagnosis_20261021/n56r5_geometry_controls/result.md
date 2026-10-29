# N56r5 : routage terminé, qualification FAIL

Bitstream : `e50b778a672fa10ed5b9a9b2818fabec722073a2804b84f22f3ad00c46e0bdc8`.
Compilation terminée avec code 0. Aucun chargement carte effectué.

| Contrôle de timing | Marge minimale |
|---|---:|
| Setup | −0,234 ns |
| Hold | +0,124 ns |
| Recovery | +0,167 ns |
| Removal | +0,145 ns |

Les deux violations setup concernent exclusivement les entrées du double
synchroniseur de l'observateur, soumises à la borne CDC de 8 ns inchangée :

| Source | Destination | Marge | Délai du net |
|---|---|---:|---:|
| `u_accel/u_v1/u_pixels/packet_1_s0/Q` en R51C48 | `u_gpu_debug/observe_words_s1_33_s0/D` en R50C140 | −0,234 ns | 7,918 ns |
| `u_accel/u_v1/u_pixels/packet_3_s0/Q` en R54C47 | `u_gpu_debug/observe_words_s1_35_s0/D` en R50C141 | −0,159 ns | 7,838 ns |

CAMERA et FACE quittent bien le tableau des routes globales. Les six contrôles
ciblés (commande, capture observateur, mem_up, matériau, caméra, face) conservent
exactement leurs pilotes, charges, connexions et paramètres de primitives.
L'audit comprend les charges CE vectorielles des DSP : matériau 256, caméra
204, face 246.

L'audit reset reste en échec : `gpu_debug_state[48]` (reset4) reste sur LW,
et `gpu_debug_state[44]` (reset0) ainsi que `gpu_debug_state[51]` (reset7)
y sont nouvellement placés. Tous possèdent déjà une ligne LOCAL_CLOCK au niveau
supérieur du CST. Cette expérience ne prouve donc pas leur application physique.
Les autres audits du qualificateur passent, dont DDR5.9/300, FIFO CPU, masque,
sélecteur et absence de duplication du propriétaire GPU.

Ressources : 85058/138240 logique, 54885 registres, 58600/69120 CLS,
263/340 BSRAM et 176,5/298 DSP. Les avertissements PR1014 concernent toujours
`clk_d` et `ae350_tck_d`, comme dans les parents.

Preuves complètes : `tang/impl/console_neo_n56r5/qualification.json`,
`geometry_controls_audit.json`, rapports `.tr`/`.rpt.txt`, et synthèse locale
`result.json` avec SHA. Le résultat n'autorise ni promotion ni qualification
matérielle implicite.

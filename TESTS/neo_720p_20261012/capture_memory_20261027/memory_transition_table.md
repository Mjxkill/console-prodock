# Lecture des quatre témoins mémoire R21r1

Cette table ne suppose aucun résultat matériel : il faut d'abord un préflight
valide, un ARM acquitté à l'arrêt, puis la commande et un SNAP cohérent. Les
bits sont `MEM[3:0]={accepted,pending,pixel_valid,native_issue}`. Ils signifient
« vu au moins une fois », sans ordre, nombre, simultanéité ni garantie d'écriture
DDR. Une nouvelle programmation invalide l'ancien état et ses ancres.

Sources exactes : `tang/impl/console_neo_n56r19_capture_ce_local/source/tang/rtl/`.
Le RTL fonctionnel est conservé dans R21r1. Les primitives physiques et leurs
INIT sont extraites dans `memory_transition_nodes.json` (SHA de la .vo inclus).

| Transition | Condition RTL exacte / cause d'absence possible | Référence et primitive physique |
|---|---|---|
| CLEAR → issue (bit0) | Commande28 acceptée, cible valide, rectangle non vide et flags couleur/Z. `RECT_COLOR && clear_flags[0]` ou `RECT_Z && clear_flags[1]`. Absence possible avant ces états, rejet, rectangle vide, flags0, reset ou capture des paramètres incorrecte. | `video/gpu_v1.v:132`,`:424`,`:578`,`:594`,`:605`,`:611`. `native_issue_s0/F`, LUT4 INITF4FF et cône de requête. |
| issue → pixel_valid (bit1) | Au front GPU sans reset : `native_valid'=native_issue || (native_valid && native_wait && !ready)`. Le pixel valid est OR native/cache/copy. En CLEAR isolé aucun cache/COPY attendu. | `gpu_v1.v:104`,`:138`. `native_valid_s1`: D=issue, CE=`native_valid_8`, RESET=INV(debug[48]), INIT0. CE LUT3 INITFE inclut issue : issue1 impose CE1 logiquement. OR physique = INV de `u_accel/n5020_s1` LUT3 INIT01. |
| pixel_valid → pending (bit2) | Géométrie OR `fetch_valid || shader_valid`, sélection `v1_select`, slot vide et ancien accepted0, `mrst[1]=1`. Si slot déjà plein, pending se maintient sauf ready. | `gpu_geometry.v:52`; `gpu_accel.v:210`,`:215`. `v1_pending_s2`: CE=VCC, RESET=INV(debug[43]), D=`v1_tx_addr_27_9`. |
| pending → accepted (bit3) | Sans reset, `accepted'=pending && ready`. `ready=b_grant=rst_n && !full && !scan_valid && take_blitter && m_ready && (!b_write || m_wr_ready)`. Le grant est une condition de commande/donnée admise, pas une preuve du contenu stocké. | `gpu_accel.v:220`; `board/ddr_gpu_arb.v:47`,`:82`. `v1_accepted_s0`: D LUT2 INIT8 de pending/b_grant, CE=VCC, même reset que pending. |
| accepted → avancement CLEAR | Le retour passe par `accepted && v1_select`, puis `ready && !fetch_valid`. RECT_CSENT / RECT_ZSENT avancent quand ce ready atteint le moteur ; native_valid retombe. Le mux d'adresse/data utilise aussi ext_active. | `gpu_accel.v:247`,`:254`; `gpu_geometry.v:60`; `gpu_v1.v:610`,`:616`. Ces sélections ne sont pas toutes observées par MEM. |

Le chemin fonctionnel `v1_pending_s2→v1_accepted_s0` est à −0,362 ns dans la
STA R21r1. Les bornes positives du helper ne corrigent pas ce chemin : les
flags décrivent ses signaux observés, pas leur conformité au contrat RTL.

## Empreintes attendues et tests discriminants

| MEM final, commande isolée | Déduction limitée | Contre-simulation utile sur le vrai RTL/mappé |
|---|---|---|
| CLEAR0 / COPY0 | Aucun événement observé. Une commande rejetée, vide ou jamais démarrée suffit ; pas une preuve DDR. | Témoin flags0, rectangle vide, COPY descripteur invalide ; comparer done/rejected et capture D/Q. |
| CLEAR1 | issue vu, aucun producteur valide vu. Si reset et ARM exclus, cible native_valid / CE / reset qualifier. | Injecter une suppression de CE au seul FF `native_valid_s1`, sans réécrire le producteur ; vérifier fingerprint1 et invariants de reset. La faute injectée n'est pas une preuve de la cause physique. |
| CLEAR3 / COPY2 | Requête producteur vue mais aucune prise du slot observée. Vérifier sélection propriétaire, reset du slot et accepted empêchant la reprise. | Contrôles ciblés de `v1_select`, reset slot ou accepted maintenu1 ; comparer le vrai mux géométrie et non un producteur inventé. |
| CLEAR7 / COPY6 | Slot vu, aucun accepted vu. Vérifier grant/ready, arbitre, mémoire ou capture du FF accepted. | Backpressure séparée `m_ready=0` puis `m_wr_ready=0`, et reprise : la même transaction doit être acceptée une fois, payload stable. Témoin faute sur capture accepted distinct du stall DDR. |
| CLEARF / COPYE | Les quatre étapes pertinentes ont été vues au moins une fois. Cela ne prouve ni fin de commande, ni bonne adresse/masque/data, ni ACK reçu par le moteur. | Retirer le retour ready au moteur après acceptation tout en gardant la vraie admission arbitre ; observer répétition éventuelle et stall. À comparer à une corruption contrôlée d'adresse/masque, qui peut donner le même MEM mais une mémoire différente. |
| Autre combinaison | Pas une localisation simple : transaction antérieure, ARM tardif, reset partiel, faute d'observation, autre client pixel/geometry. | Refaire les hypothèses de fenêtre avant de déclarer une combinaison « impossible ». Les bits sticky ne donnent pas l'ordre temporel. |

Pour COPY, native_issue n'est normalement pas utilisé : E est donc l'équivalent
attendu de F pour CLEAR. Un COPY rejeté avant mémoire donne0 ; sa capture D/Q
au start peut néanmoins établir une capture manquante de largeur. Huit bits
ne prouvent pas le descripteur entier et CHECK/VALIDATE/bad sont échantillonnés
trop tôt pour être assimilés au résultat final du rejet.

Les bancs existants ont déjà vérifié CLEAR=F et COPY=E sur le slot/arbitre RTL
réels (`observer_copy_01/real_memory_events_01`) et quatre fautes de capture
COPY sur les primitives mappées (`assembled_test_01`). Toute nouvelle injection
sera ciblée sur les observations matérielles ; aucun nouveau build proposé ici.

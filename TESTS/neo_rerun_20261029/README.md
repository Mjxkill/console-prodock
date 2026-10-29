# Neo R19 — reproduction du 29 octobre 2026

Quatre essais bornés sur la Neo locale, programmateur `2025041420`, après
rechargement SRAM de R19 exact :

`1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`

Aucune écriture flash ni SD, aucun Linux, CPU garé. R19 a été restauré après
chaque essai et le garde final a vérifié CPU, mire interne et UTNA frais.

## Résultats

| Essai | Commande | Résultat | `done` | `busy` | `rejected` | Cible DDR |
|---|---|---:|---:|---:|---:|---|
| `zero_clear` | CLEAR `flags=0` | **PASS**, phase 10 | 2 | 0 | 0 | aucune écriture attendue |
| `clear16_readback` | CLEAR 16 px | **FAIL**, phase 8 | 1 | 1 | 0 | motif initial intact |
| `empty_copy` | COPY 0×0 | **FAIL**, phase 8 | 2 | 0 | 1 | motif initial intact |
| `copy16_readback` | COPY 16 px | **FAIL**, phase 8 | 2 | 0 | 1 | motif initial intact |

Le CLEAR `flags=0` prouve que le décodage V1, les bornes, le clipping et
`FINISH` fonctionnent sans requête DDR. Le CLEAR 16 px est consommé mais reste
en attente : `done=1`, `busy=1`, état blitter `M_SETUP`, sans erreur, perte ni
rejet. Le COPY est rejeté avant tout transfert utile, y compris avec un
rectangle vide et avec source = destination.

Les lectures CPU de contrôle terminent **32/32** et les 128 octets conservent
le motif initial. Le CPU et la DDR restent donc accessibles pendant le
blocage. Le FILL legacy à la même adresse avait déjà écrit correctement dans
`TESTS/neo_720p_20261012/local_capture_20261026/r19_same_address_01/`.

## Interprétation

- Le chemin de commande, le décodage V1 et la terminaison sans DDR sont sains.
- Le défaut apparaît lorsque le moteur V1 doit émettre une écriture native
  (CLEAR 16 px) ou valider un descripteur COPY.
- La DDR n'est pas globalement en panne : le CPU lit et écrit, et le FILL
  legacy réussit à la même adresse.
- Le rejet COPY existe même sans transfert DMA attendu ; il ne dépend donc pas
  du seul trafic DDR.
- R19 n'expose pas `v1_pending`, `v1_accepted`, `ready`, `v1_request` ni le
  paquet enfant du COPY. Le `.tr` indique `v1_pending` à **+1,011 ns** ; le
  pire chemin reste `busy_sync` à **−2,888 ns**, qui est un chemin de statut
  AHB et non la preuve de la cause du blocage V1.

## Limites

Les 32 lectures CPU sont séquentielles, pas un instantané atomique. Seule la
zone scratch de 128 octets est relue. L'instrumentation R19 modifie charges et
placement. Le timing global reste FAIL. Aucun résultat de ce dossier ne
qualifie le GPU, la DDR, l'USB, HDMI ou Linux.

## Prochain test discriminant

Ajouter, dans une copie gelée de R19, des taps passifs de `v1_pending`,
`v1_accepted`, `ready`, `v1_request`, `v1_write` et `v1_select` dans les bits
inutilisés de `debug_state[255:0]`, sans modifier le transport NGDB ni les
adresses. Le même essai CLEAR/COPY permettrait de distinguer :

- `v1_pending=1`, `ready=0` : requête émise mais non acceptée par l'arbitre ;
- `v1_pending=0`, `v1_request=1` : échec de la capture du slot ;
- `v1_pending=0`, `v1_request=0` : le moteur V1 n'émet pas la requête.

Ce build n'est pas lancé : il exige un nouveau routage et une revue root.

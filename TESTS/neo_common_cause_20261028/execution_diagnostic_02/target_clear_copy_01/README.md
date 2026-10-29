# TARGET → CLEAR0 → COPY0 : contrôle séquentiel R19, sans nouveau FPGA

Préparation hors carte. Root seul peut charger ce firmware sur la Neo R19
identifiée, CPU parqué et framebuffer désactivé. Aucun essai matériel de cette
séquence n’est revendiqué. Les références Pro Dock et les autres firmwares
restent inchangés ; aucun RTL n’a été édité ou recompilé pour une carte.

Le COPY vide a été rejeté physiquement dans `root_empty_copy_run_01` après
completion (done2, busy0, rejected1), comme COPY non vide. CLEAR0 isolé avait
réussi. Ici CLEAR0 précède immédiatement COPY0 dans le même programme et ne
réécrit pas TARGET. Ce contrôle localise la première validation qui échoue.
Il ne mesure pas directement `target_valid`, ni le bus natif DDR.

## Identité et emplacements

- Binaire `build_01/microdma.bin` : **1020 octets**, SHA256
  `5171a15d524722faf19b4cf3bc9fa7c2cf6327cc7654fe06c998cce1a5c06fff`.
- Point d’entrée/ILM : `0xa0004000`, fin exclusive `0xa00043fc`.
  Réservation4096B avant `0xa0005000` respectée, sans stack.
- Journal512B : `[0xa0006000,0xa0006200)`, remis à zéro par le programme.
  Nouvelle identité **MD13 = 0x4d443133**, version1.
- Scratch128B : `[0x12000000,0x12000080)`,32CPUstores puis32loads de
  contrôle à chaque image. Aucune adresse SD ou USB.
- TARGET : couleur32B à `0x12000020`, Z32B à `0x12000040`,16×1,strides32.
- CLEAR : flags0, couleur6b4d, rectangle16×1 ; COPY : source16×1/stride32
  à `0x12000000`, étendue demandée0×0. Source/TARGET identiques à l’essai vide.
- Attentes contractuelles GPU : aucun accès natif. Les sorties `valid/men/mwen`
  sont effectivement nulles dans les7simulations, pas mesurées sur la carte.

Les gardes antérieures restent actives : caches désactivés, MILMB=a0000001,
satp0, mie0, mstatus.MIE0, BLT2, GPU idle/done0/erreurs0, framebuffer désactivé.
Le firmware ne désactive pas un cache étranger et ne modifie pas mstatus/mie.
Il restaure mtvec puis revient à80000000. Les boucles logicielles sont bornées ;
un accès AHB bloqué ne l’est pas : le contrôleur doit garder son watchdog.
L’identité physique, la fraîcheur du programme et la restauration R19 sont
à la charge du contrôleur, non démontrées par le journal ou par ces tests.

## Phases et décodage

| Phase | Opération | Échec propre |
|---:|---|---:|
|1–6|Gardes, seed, TARGET, contrôle mémoire inchangés|−1 à−4,−7|
|7|Soumission CLEAR0|−9 si FIFO pleine trop longtemps|
|8|Attente done2/idle puis contrôle compteurs|**−8**|
|9|Soumission COPY0|−9 si FIFO pleine trop longtemps|
|10|Attente done3/idle puis contrôle compteurs|**−5**|
|11|32loads de contrôle final, attente seed partout|−6 si différence|
|12|Terminé sans erreur|**+1**|

`−8` et `−5` couvrent timeout logiciel **ou** completion avec compteur d’erreur.
Lire les compteurs avant de nommer le phénomène. L’échec CLEAR0 interrompt la
soumission : seuls16mots sont alors envoyés, contre24 si COPY est soumis.

Le journal conserve les positions anciennes sauf l’usage de deux mots réservés :
`words[26]` = done après CLEAR0, `words[27]` = rejected au même point.
`words[18:21]` attendus au succès = `[0,1,3]`, `words[26:28]=[2,0]`,
`words[28:31]=[32,32,32]`. Les trois images128B sont du seed inchangé.
Le mot31 reste réservé0. Errors/lost/rejected finaux restent aux21/22/23.

API obligatoire :

```python
result = decode_sequence.decode(raw512, firmware_sha256=reviewed_sha)
# sequence_test_passed, clear_control_passed, observation, done_counts,
# classification, compared_counts, issues
```

Ne pas appeler l’ancien décodeur MD12. Les lecteurs CPU secondaires actuels
requièrent MD12 phase8 : **ne pas ajouter --cpu-readback à ce profil MD13**.
Un lecteur adapté constituerait une autre préparation. Ici les32loads finaux
ne s’exécutent que si toute la séquence réussit.

## Interprétation attendue

| Résultat | Conclusion bornée |
|---|---|
|CLEAR0 rejeté|Le préfixe auparavant réussi ne l’est plus dans cet essai ; inspecter packet/header/cible, pas accuser uniquement COPY|
|CLEAR0 réussi, COPY0 rejeté|Cible valide au front de validation CLEAR, mais target_valid ultérieur, champs capturés ou validation COPY restent à départager|
|Séquence réussie|Effet de préfixe/latence/état possible ; ne démontre pas lequel et ne qualifie aucun transfert DDR|

La simulation reproduit deux causes logiques avec les mêmes CSR finaux :
forcer `copy_bad`, ou invalider `target_valid` seulement après CLEAR0.
La séquence les distingue de la perte de cible avant CLEAR, mais ne les
sépare pas entre elles. Ces injections ne sont pas des causes observées
physiquement et ne sont pas exécutables comme telles sur R19.

## Preuves

- 19 cas d’exécution du binaire RV32 exact : delayed, timeout, done-busy,
  rejets de chaque étape, cible perdue avant/après CLEAR, canaris, guards,
  trap, plage mémoire et nombre de commandes. Aucun accès GPU natif du modèle.
- 38 cas de décodage : journaux réels du modèle et mutations indépendantes,
  mauvais SHA/MD12/tailles/métadonnées refusés ; lecture finale absente explicite.
- 7 cas RTL complet via AHB/FIFO/géométrie/pixels/arbitre exacts R19 : deux
  couples d’horloges, readiness réellement forcée à0, trois injections de
  validation. Les24mots du banc sont liés aux96derniers octets du binaire.

Mission DeepSeek réelle : `deepseek_execution_01`,117,462s,12POST,21outils,
3tests agent dont1échec initial, puis validation finale PASS. Son environnement
et les sources sont figés. `rtl_review_01` conserve le même scénario en
corrigeant une lacune du banc préparé par Codex : les options de readiness
n’armaient pas les lignes à0. Cette erreur de préparation est préservée et
corrigée par un nouveau test vérifiant explicitement le niveau forcé.
Le premier préflight avait également rencontré une erreur interne Verilator
sur `guard++` dans un `if` ; `runtime_02` compile et exécute dans Bubblewrap.
Les deux défauts d’outillage ne sont pas attribués au modèle ni à la DDR.

Limites : RV32 interprété n’est pas un modèle AE350, RTL n’est pas le netlist
routé, aucune mesure physique de timing ou de requête native. Les sources
readonly recopiées pour preuve sont des snapshots historiques, pas de nouveaux
modules de production maintenus. Aucune entrée de build des cartes n’a changé.

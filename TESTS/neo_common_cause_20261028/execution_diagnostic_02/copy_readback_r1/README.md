# Lecteur CPU après COPY — livraison hors carte

BIN `build_01/readback.bin` : **588 octets**, SHA-256
`15dfe11fd3f11edd3330d835420562494a7d170f7a95b5e1b1c3d451462ae0d2`.
Il dérive exclusivement du lecteur CLEAR `readback_r1`, SHA
`aa2a1a061c87de6cc47a567a217b6d4078df1d3c982242bfe2275ef7bcc50503`.
Seuls deux mots instruction changent, offsets **384 et 388** :
`addi t3,t0,-32 ; xor t3,t3,t2`, au lieu du chargement 32 bits de la
constante couleur. Tous les autres octets sont identiques, gardes comprises.

Code ILM `[0xa0005000,0xa000524c)`, réservation jusqu'à `0xa0006000`.
Journal256B `[0xa0006400,0xa0006500)`. Ancien code4000 et journal512B6000
intacts. **Zéro écriture DDR, zéro commande ou écriture GPU** ; uniquement
32 lectures CPU successives `[0x12000000,0x12000080)` si les gardes passent.
Tous les stores vont au nouveau journal ILM. Pas de pile ni cache flush.
Retour parking ROM80000000, restauration mtvec ; GPR détruits comme avant.

## Provenance et gardes

Ce lecteur accompagne uniquement le firmware COPY928B SHA
`4d3b91ee5fd7aae44abd7d55ab712c24f78167ec1ac318f7a9a21aea000a8684`
dans `copy_probe_01/firmware_delivery_01`. MD12 et RB12 ne portent pas
l'identité de l'opération ou sa fraîcheur. Le contrôleur doit rattacher les
deux BIN vérifiés et les deux journaux du même essai, démarrer au point
d'entrée5000 et vérifier le retour, pas relire un ancien journal valide.

Gardes identiques : cache0, ILM a0000001, satp0, mie0, mstatus.MIE0,
ancien journal MD12/version1/phase8/résultat−5/comptages32 et32,
framebuffer shadow/commit/active0, identité GPU BLT2. Ce lecteur enregistre
done/status/errors/lost/rejected avant et après ; il accepte que le GPU ait
terminé ou rejeté depuis la première observation. Ces CSR ne sont pas atomiques.

API destinée au contrôleur :

```python
decode_bound(raw256, stage_sha256=COPY_SHA, reader_sha256=READER_SHA)
```

Le décodeur refuse d'autres SHA. Il ne peut pas vérifier physiquement la
provenance que lui fournit l'appelant. `decode(raw256)` reste un décodeur
hors ligne explicitement non lié (`provenance.binding_checked=False`).
Le CLI exige `--stage-sha256` et `--reader-sha256`.

Comparaison attendue : octets32..63 égaux aux32octets source initiaux,
les96autres octets canaris inchangés. Les quatre classes sont
`copy_exact_canaries_intact`, `seed_unchanged`, `other_or_partial_change`,
`unobserved`. `readback_valid` signifie lectures achevées et journal cohérent,
pas résultat GPU correct : `gpu_passed` reste faux même si la mémoire attendue
est observée. Une lecture interrompue ou incohérente ne classe pas la mémoire.

## Vérifications

23 cas interprètent les octets RV32 compilés : copie attendue, seed intact,
copie partielle, canari modifié, trap au8e load,15 gardes, GPU déjà terminé
avec rejected1, transition GPU pendant les lectures, ancien contenu CLEAR.
13 contrôles du décodeur : completion/comptage/comparaison/extent/réservé,
trap/cache, mauvais SHA, tailles et identité invalides. Tous passent.
Le test décode aussi les deux instructions modifiées, et vérifie chaque
adresse lue/écrite ainsi que la conservation de l'ancien journal.

Le modèle ne représente pas le hard CPU, les CSR Andes, le PHY, l'arbitrage
physique ou la temporalité DDR. Une transaction AHB peut rester bloquée :
root doit maintenir le watchdog hôte, les captures fraîches AVANT/APRÈS et
la restauration R19. Les32loads ne forment pas un snapshot mémoire atomique.
Aucun matériel n'a été utilisé pour cette livraison.

## Correction importante du constat COPY matériel initial

Dans `root_copy_run_01`, −5 signifie échec de `wait_done`, qui inclut son
tail-call `check_gpu_errors`. Ce n'est pas nécessairement un timeout.
Le journal mot20 vaut2 et mot23 vaut1 ; les lectures CSR AFTER et AFTER100
confirment `done=2`, `status=0`, `rejected=1`. COPY est donc terminé/rejeté
dans ces observations, contrairement au CLEAR occupé durablement.

Le contenu DDR final n'a pas été relu ; il reste **unobserved**. Ce lecteur
ne préjuge ni que le seed est intact ni qu'une copie partielle a eu lieu.
La raison du rejet et la différence modèle/carte restent à expliquer.

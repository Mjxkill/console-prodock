# G4 — sprites matériels mis en cache

Extension de [G3](GPU_G3_REGISTRES.md), même bloc AHB à `0xe9000000`.
Le cœur reste à 800 MHz, le bus AHB à 80 MHz, la DDR UI à 75 MHz et
le LCD à 35 MHz. G1/G2/G3 restent disponibles.

## Capacités

64 descripteurs de sprites indexés 8 bits, dimensions de 1 à 32 pixels
sur chaque axe, dont 8×8, 16×16 et 32×32. Indice zéro transparent,
positions signées, clipping aux quatre bords, retournements horizontal et
vertical indépendants. La palette RGB666 est commune avec les couches.

La priorité 0..15 place un sprite juste au-dessus de la couche correspondante
et sous les couches suivantes. À priorité égale, l'indice de descripteur
le plus élevé gagne. Un pixel transparent laisse voir le contenu inférieur.

Les images sont en DDR3, avec une adresse alignée sur 32 octets et un pas
de ligne **fixe de 32 octets**, même pour un sprite plus petit. Le cache
interne contient 64×32×32 = 65 536 octets. Au début de chaque retour vertical,
le GPU recharge les lignes des images activées et construit les listes de
priorité. Les retournements horizontaux sont appliqués à ce chargement.
Le compositeur lit ensuite uniquement le cache pour les sprites pendant
les lignes visibles. Les couches continuent d'être lues en DDR3.

Changer l'adresse d'image et/ou la position au commit permet l'animation.
Il n'y a pas de zoom, rotation arbitraire, mélange alpha ou compteur
d'animation autonome à ce jalon.

## Registres supplémentaires

| Offset | Accès | Contenu |
|---|---|---|
| `0x03c` | R | Capacité : 64 sprites |
| `0x040` | R/W | Activation préparée des sprites, bit 0 ; nécessite le mode couches |
| `0x044` | R | Activation appliquée au retour vertical |
| `0x048` | R | Descripteurs de sprites invalides rencontrés, cumulatif |
| `0x04c` | R | Maximum de sprites intersectant une même ligne |
| `0x050` | R | Maximum de cycles DDR pour recharger le cache d'une trame |
| `0x054` | R | Maximum de pixels de sprites intersectant une ligne, avant transparence/masquage |
| `0x058` | R | Nombre de rechargements terminés du cache |
| `0xc00..0xfff` | W | Banque inactive : 64 descripteurs de 16 octets |

Le compteur existant `0x02c` mesure la composition d'une ligne, hors
rechargement du cache. `0x01c` signale toute ligne LCD manquante, notamment
en cas de surcharge ou de rechargement trop lent. Tous les compteurs sont
remis à zéro par le reset du GPU.

## Descripteur, quatre mots de 32 bits

| Mot | Format |
|---|---|
| 0 | Adresse physique DDR3 en octets, alignée sur 32 octets, dans le premier Gio |
| 1 | Y signé 16 bits en haut, X signé 16 bits en bas |
| 2 | Largeur bits 7:0 ; hauteur bits 15:8 ; enable bit 16 ; flip X bit 17 ; flip Y bit 18 ; priorité bits 23:20 |
| 3 | Réservé, écrire zéro |

Un sprite désactivé est ignoré. Un sprite activé avec une dimension nulle
ou supérieure à 32, une adresse non alignée ou une image sortant du premier
Gio est rejeté et compté à chaque rechargement. Sa mémoire n'est pas lue.

## Commit et cohérence

Les tables des couches et des sprites partagent le même changement de banque
au retour vertical. Réécrire les **16 couches et les 64 sprites** dans la
banque inactive, préparer `0x030=1`, `0x040=1`, `0x008=1`, puis écrire
`0x00c=1`. Les écritures dans les tables attendent tant que BUSY est actif.
Les banques ne sont recyclées qu'après la fin de l'ancienne lecture.

Publier les textures écrites par le CPU avec `gpu_publish_surface()` avant
le commit. Garder les textures actives immuables ; préparer l'image suivante
ailleurs, puis changer son adresse au commit. L'ancienne image peut être
réutilisée après l'application du nouveau commit, qui attend les lectures
en cours. Modifier une image active pendant son rechargement n'est pas
une mise à jour atomique.

API C : `gpu_make_sprite()` et `gpu_scene_submit()`, puis
`gpu_display_wait()`. `gpu_layers_submit()` désactive les sprites pour
revenir à G3. La permutation est atomique ; la palette globale reste
hors de cette transaction comme en G3.

## Budget de ligne

La capacité de 64 objets ne garantit pas 16 surfaces plein écran et
64 sprites sur chaque ligne en présence de tout trafic DDR. Le temps
comprend la lecture des couches, la traversée des objets et leurs pixels
visibles. Les compteurs rendent la charge et les défauts observables.

G4 commence la fusion de chaque bloc de couche dès que ses mots DDR sont
disponibles, en parallèle avec le reste de la lecture. Les mesures de
simulation et de carte sont consignées séparément dans
[TESTS_GPU_G4.md](../TESTS/TESTS_GPU_G4.md).

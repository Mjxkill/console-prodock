# Triangles par lignes et aplats DDR3 natifs

Cette évolution accélère les opcodes existants, sans changer leur format,
les pages, la règle de couverture des triangles ni les barrières logicielles.
Le cœur reste à 800 MHz et le domaine graphique/DDR UI à 75 MHz.

## Intersections exactes des arêtes

Le précédent `gpu_triangle.v` testait les pixels successivement dans la boîte
englobante, puis fournissait un segment horizontal au blitter. Le nouveau
rasteriseur calcule directement les intersections des trois demi-plans avec
chaque ligne de pixels.

Pour une arête normalisée A→B, avec `dx=Bx-Ax`, `dy=By-Ay` :

```
E(x,y) = dx*(2*y+1-2*Ay) - dy*(2*x+1-2*Ax)
E(x,y) = E(0,y) + a*x, avec a=-2*dy
T = 0 pour une arête incluse, 1 sinon
```

L'inclusion conserve exactement la règle haut/gauche : `dy<0` ou
`dy==0 && dx>0`. Pour chaque ligne :

- `a>0` impose `x >= floor((T-E(0,y)+a-1)/a)` ;
- `a<0` impose `x <= floor((E(0,y)-T)/(-a))` ;
- `a==0` accepte ou rejette la ligne entière selon `E(0,y)>=T`.

Chaque borne est une division entière `floor(N/D)`. Trois diviseurs en
parallèle calculent son quotient/reste initial, puis ceux de son incrément
par ligne : deux séries de 36 cycles par triangle. Ils effectuent une
division euclidienne, y compris pour les numérateurs négatifs.

Les lignes suivantes utilisent seulement des additions et une correction
de retenue sur le reste. Cette accumulation entière n'introduit aucune
erreur progressive d'arrondi. Le coût par ligne ne dépend plus de la largeur
du triangle. Les bornes sont découpées avant émission ; les segments restent
stables tant que le blitter ne les accepte pas.

Les calculs d'intersection sont signés sur 36 bits ; les diviseurs et restes
sur 17 bits couvrent les différences entre coordonnées signées 16 bits. Les
arêtes horizontales, triangles dégénérés et orientations inversées conservent
leur comportement précédent. L'avancement est découpé en plusieurs cycles
pour limiter la longueur des chemins arithmétiques.

## Aplats directement en blocs de 32 pixels

Les rectangles unis, disques et triangles remplis transmettent désormais
une adresse d'octet, une largeur et une couleur au DMA. Ils n'utilisent plus
la génération octet par octet dans le tampon de ligne.

Le DMA réplique la couleur sur ses 256 bits et produit les masques des
premier et dernier blocs de 32 octets. Les blocs internes écrivent 32 pixels
indexés d'un coup. L'adresse, les données et le masque restent constants
pendant les attentes DDR. La fin n'est signalée qu'après acceptation du
dernier transfert natif, conformément au contrat de `DONE`.

Un bloc demande plusieurs cycles de préparation et d'arbitrage : ce n'est
pas une garantie de 32 pixels par cycle soutenus. Cette voie évite néanmoins
la génération des 32 pixels, puis leur assemblage par 16 demi-mots successifs.
Le rasteriseur peut préparer le segment suivant pendant l'écriture du
segment courant, avec maintien du résultat sous contre-pression.

Les dégradés, copies, texte et zoom conservent leur tampon de ligne et le
chemin DMA précédent. La priorité de l'affichage dans l'arbitre DDR reste
inchangée. Aucun second tampon de ligne n'est ajouté : la voie directe des
aplats supprime le passage par ce tampon pour les opérations ciblées.

## Vérification avec le rendu initial du jeu

Le jeu démarre par défaut avec le rendu original : ciel et montagnes
redessinés à chaque image, bordures calculées comme de grandes surfaces
ensuite recouvertes par la route. Ses quatre images retrouvent les empreintes
de `gpu_racer_r1`. Le mode avec panorama en cache reste disponible.

| Commande USB | Effet |
|---|---|
| `R` | Démarre le jeu dans le mode courant, original après redémarrage du FPGA |
| `C` | Bascule entre rendu original et panorama en cache ; revient au départ |
| `K` | Mesure 240 images déterministes dans chaque mode, puis revient au jeu original |

`K` parcourt une période entière de virages, déplace la caméra latéralement
et fait varier les distances du trafic. Il mesure séparément préparation
CPU, soumission/attente GPU et image complète avec vblank. Le maximum GPU
permet de vérifier la marge par rapport aux 18,17 ms du LCD, en plus de la
moyenne. Ce test ne promet pas une cadence identique pour toute scène future.

Les [tests et mesures](../TESTS/TESTS_GPU_FAST.md) conservent les résultats.

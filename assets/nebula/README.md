# Ressources graphiques NEBULA

`source/fleet.png` et `source/nebula.png` sont des illustrations originales
créées avec le skill imagegen et l'outil intégré `image_gen`. Les prompts
complets sont dans [source/PROMPTS.md](source/PROMPTS.md). Les images sont des
ressources statiques ; les déplacements et les combats sont calculés par le
jeu Linux pendant la partie.

```sh
python3 tools/build_nebula_assets.py
```

Cette conversion produit `packed/nebula.bin`, son manifeste, un aperçu du
fond et `linux/userspace/nebula-assets.h`. Elle nécessite Pillow et NumPy.
Le paquet comprend 55 ressources et occupe 435 584 octets. Sa palette réserve
les seize dernières couleurs aux consoles Linux.

Le générateur utilise le `font_8x8.c` de la version Linux épinglée par le projet
(GPL-2.0) pour les glyphes, et DejaVu Sans Bold pour le titre rasterisé. Les
particules, lueurs, boucliers et variantes des sprites sont calculés par le
convertisseur. Les variantes de pose du joueur sont des images, pas des
trajectoires précalculées.

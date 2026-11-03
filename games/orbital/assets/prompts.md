# ORBITAL — prompts des ressources

Outil intégré `image_gen.imagegen`, 5 octobre 2026. Sources originales conservées dans `source/`. Conversion GPU déterministe par `tools/build_orbital_assets.py`.

## sky.png

```text
Use case: stylized-concept. Asset type: opaque distant panoramic sky backdrop for ORBITAL, an original first-person science-fiction shooter GPU demo inspired by early console space operas. Primary request: an awe-inspiring alien world seen from a high orbital station: a colossal pale turquoise ringworld arc sweeps upward through the left half of a deep sapphire sky, a blue-white planet with subtle clouds near upper right, distant cold mountains and luminous atmospheric haze along the low horizon. Beautiful polished retro game background painting with crisp readable large forms, restrained fine detail, teal-blue light, distant pale stars, a few small distant spacecraft. Landscape 1536x1024. Horizon at 65 percent down the image. The top half is sky; the lower third has distant rocky blue terrain. This will be cropped and reduced to 400x240 behind live 3D station geometry. No station interior, no nearby platforms, no window borders, no weapon, no HUD, no lettering, no logo, no characters. Full bleed opaque scene.
```

## weapon.png

```text
Use case: stylized-concept. Asset type: one transparent first-person weapon overlay for ORBITAL, an original sci-fi action game on an 800x480 display. Create a handsome compact futuristic assault rifle held by two olive-armored gauntlets, seen from the player's eyes. Perspective: the large stock and right gripping hand in the lower right, barrel extends diagonally toward upper left, muzzle near (30 percent width, 20 percent height), aimed into the centre of an imaginary game screen. Gunmetal steel, desaturated olive armor, amber ammunition indicator WITHOUT digits or lettering, tiny cyan energy slits, machined edges, practical science-fiction military design. Detailed polished pixel-art rendering like a premium late-1990s first-person game, crisp forms and highlights, readable when reduced to about 360x230 pixels. The cutout consists only of weapon, forearms and gloved hands, with transparency all around, wrists naturally cropped at bottom edge. No muzzle flash (animated separately), no scenery, no shadow backdrop, no panel, no HUD, no text, no logo, no frame. One weapon only, no sprite sheet. Landscape composition, actually transparent background.
```

## drones.png

```text
Use case: stylized-concept. Asset type: transparent enemy sprite sheet for ORBITAL, a polished original science-fiction first-person action demo. EXACTLY FOUR equal square cells in a regular two by two grid, square image, invisible grid. The same hostile floating alien combat drone in every cell, facing the viewer. Full silhouette within each cell with generous transparent margins. Design: menacing compact faceted purple-violet armored shell, two angular swept-back lateral fins, central bright amber sensor eye, little mechanical claws below, cyan thruster underneath. Rich polished retro pixel-art game rendering, crisp navy outlines, metal highlights and glowing emissive core, readable at 64x64. Row 1 column 1: idle hovering, wings extended. Row 1 column 2: firing with sensor brilliant magenta and small energy charge concentrated at front (no long beam). Row 2 column 1: hit, cracked armor and several small orange sparks. Row 2 column 2: destroyed drone as separated floating purple armor fragments with a small orange energy burst, remaining inside its cell. Consistent size, camera, center position and identity in all four cells. No human figures, no ground, no scene, no shadows cast on background. Actually transparent background, no checkerboard painted in, no lettering, no labels, no logo or frame.
```


## Images générées sur gx10 (5 octobre 2026)

Produites par `tools/orbital_art.py` sur le ComfyUI local de gx10-1 : Qwen-Image 2512
(texte vers image) et Qwen-Image-Edit 2509 (poses dérivées d'une image de référence, pour
garder le même personnage), LoRA Lightning 4 étapes, 14 à 30 secondes par image. La
description, les prompts et les graines sont dans `art.json` ; les images sont dans
`source/gen/`. Les ennemis sont demandés sur fond vert uni et détourés par
`tools/build_orbital_assets.py`. Relancer `python3 tools/orbital_art.py` ne régénère que
les images manquantes ; `--only NOM` en refait une.

| Image | Graine | Dérivée de |
|---|---:|---|
| `guardian0.png` | 7 | — |
| `guardian1.png` | 11 | guardian0 |
| `guardian2.png` | 12 | guardian0 |
| `guardian3.png` | 13 | guardian0 |
| `elite0.png` | 21 | — |
| `elite1.png` | 22 | elite0 |
| `elite2.png` | 23 | elite0 |
| `elite3.png` | 24 | elite0 |
| `scout0.png` | 31 | — |
| `scout1.png` | 32 | scout0 |
| `scout2.png` | 33 | scout0 |
| `scout3.png` | 34 | scout0 |
| `sky2.png` | 41 | — |
| `title.png` | 51 | — |
| `tex_panel.png` | 61 | — |
| `tex_floor.png` | 62 | — |
| `tex_pillar.png` | 63 | — |
| `tex_crate.png` | 64 | — |
| `tex_door.png` | 65 | — |

Blocs communs des prompts :

```text
style  : Polished detailed retro pixel-art style like a premium late-1990s console game, crisp dark navy outlines, metallic highlights, emissive glow. No text, no logo, no frame.
sprite : Game enemy sprite, single object centered, front view facing the viewer, on a perfectly flat uniform pure green chroma key background (#00ff00), no shadow, no ground. Full silhouette visible with margin around it.
keep   : Keep exactly the same machine, same design, same colours, same front view, same size and position, same flat pure green background.
```

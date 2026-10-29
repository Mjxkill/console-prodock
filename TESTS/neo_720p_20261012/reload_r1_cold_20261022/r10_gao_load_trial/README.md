# N56r10 — essai demandé sur Neo

Chargement SRAM exact effectué après contrôle vivant du CPU N56r8 garé,
SATP0, mire et géométrie720p. Programmateur série2025041420, bus3:28.
Bitstream `7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28`.
Le statut matériel DONE est acquis ; pas de relecture SRAM ni somme logicielle
revendiquée. Qualification statique FAIL inchangée.

La photo avant DMI montre l’écran noir et la LED utilisateur allumée. La
fonction routée LED=!ddr_init confirme son sens, mais une photo ne prouve
pas la continuité du signal ni l’intégrité mémoire.

Le TAP AE350 répond avec1000563d. L’examen DMI à100kHz expire après30s ;
aucun arrêt CPU réussi. Le groupe OpenOCD propre à cet essai est terminé.
Ni Linux ni SD ni flash ni écriture DDR/GPU. N56r10 reste chargée selon la
demande ; N56r8 n’a pas été restaurée. Aucune capture GAO obtenue à ce stade.

Le résultat reproduit le symptôme R9, sans en établir encore la cause.

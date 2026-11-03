# Shared ASTRILLA scene support

These eight headers are the single shared scene implementation used by
ASTRILLA and WORLD3D. WORLD3D includes the ASTRILLA scene, which in turn uses
its meshes, flight, textures and geometry adapter. The historical interfaces
are kept intact for a path-only migration; no duplicate per-game copy exists.

The hardware GPU interfaces remain in `fw_console/`. Asset data and the
cinematic main program live under `games/astrilla/`; WORLD3D's main program
and camera/control scene live under `games/world3d/`.

Header function bodies and generated tables are existing technical debt.
Moving them here does not claim new modularity or new hardware validation.

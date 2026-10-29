"""Project default: newest installed Gowin, selected on 2026-10-16."""
import os
from pathlib import Path

IDE = Path('/home/michael/gowin/IDE')  # V1.9.12.03
PRIMITIVES = IDE / 'simlib/gw5a/prim_sim.v'
SYSTEM_FREETYPE = Path('/usr/lib/x86_64-linux-gnu/libfreetype.so.6')


def environment(ide=IDE, *, system_freetype=False):
    """Keep the library workaround local to each compiler subprocess."""
    ide = Path(ide).resolve(strict=True)
    env = dict(os.environ, LD_LIBRARY_PATH=str(ide / 'lib'),
               QT_QPA_PLATFORM='offscreen', DISPLAY='')
    if system_freetype or ide == IDE.resolve():
        # Ubuntu fontconfig needs FT_Done_MM_Var, absent from this IDE's
        # bundled FreeType. Preserve any preloads already set by the caller.
        library = str(SYSTEM_FREETYPE.resolve(strict=True))
        preload = env.get('LD_PRELOAD', '')
        env['LD_PRELOAD'] = library + (':' + preload if preload else '')
    return env

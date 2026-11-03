"""Select one Gowin installation without a machine-specific user directory.

Set GOWIN_IDE to the absolute IDE directory for reproducible builds. Without it,
keep the established ~/gowin/IDE installation if present, then consider gw_sh
on PATH. Never search version directories or silently fall back from an invalid
explicit selection. Selection does not claim that a tool version is qualified.
Imports remain usable without Gowin; environment() validates before execution.
"""
import os
from pathlib import Path
import shutil


def select_ide(*, environ=None, home=None):
    """Return the selected directory; do not run a tool or test its license."""
    env = os.environ if environ is None else environ
    if 'GOWIN_IDE' in env:
        value = env['GOWIN_IDE'].strip()
        if not value:
            raise ValueError('GOWIN_IDE is empty; set an absolute IDE directory')
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError('GOWIN_IDE must be an absolute IDE directory: '+value)
        return path.resolve()
    default = (Path.home() if home is None else Path(home)) / 'gowin/IDE'
    if default.exists():
        # Even an incomplete established installation must fail visibly instead
        # of selecting another version found later on PATH.
        return default.resolve()
    executable = shutil.which('gw_sh', path=env.get('PATH', ''))
    if executable:
        resolved = Path(executable).resolve()
        if resolved.parent.name != 'bin':
            raise ValueError('gw_sh on PATH is not under IDE/bin; set GOWIN_IDE explicitly')
        return resolved.parent.parent
    # Keep IDE/PRIMITIVES as Paths for existing importers and --help commands.
    # The useful missing-installation error belongs to environment(), not import.
    return default.resolve()


IDE = select_ide()
PRIMITIVES = IDE / 'simlib/gw5a/prim_sim.v'
SYSTEM_FREETYPE = Path('/usr/lib/x86_64-linux-gnu/libfreetype.so.6')


def environment(ide=IDE, *, system_freetype=False):
    """Validate a selected installation and return a subprocess-only environment.

    Preserve the established FreeType workaround for the selected IDE. On other
    hosts GOWIN_FREETYPE may name an absolute compatible system library, or be
    'off' to disable the automatic workaround. An explicit system_freetype=True
    still requests it. No caller environment or reference manifest is modified.
    """
    ide = Path(ide).expanduser().resolve()
    missing = [str(ide/'bin'/name) for name in ('gw_sh', 'GowinSynthesis')
               if not (ide/'bin'/name).is_file() or not os.access(ide/'bin'/name, os.X_OK)]
    if not (ide/'lib').is_dir():
        missing.append(str(ide/'lib'))
    if missing:
        raise RuntimeError('Incomplete Gowin IDE at '+str(ide)+': missing executable/library '
                           +', '.join(missing)+'. Set GOWIN_IDE to the intended IDE directory; '
                           'no alternate installation was selected.')
    env = dict(os.environ, LD_LIBRARY_PATH=str(ide / 'lib'),
               QT_QPA_PLATFORM='offscreen', DISPLAY='')
    freetype = env.get('GOWIN_FREETYPE', '').strip()
    if system_freetype or (ide == IDE.resolve() and freetype != 'off'):
        # Ubuntu fontconfig needs FT_Done_MM_Var, absent from this IDE's
        # bundled FreeType. Preserve any preloads already set by the caller.
        library_path = Path(freetype).expanduser() if freetype not in ('', 'off') else SYSTEM_FREETYPE
        if not library_path.is_absolute() or not library_path.is_file():
            raise RuntimeError('Gowin FreeType workaround library is unavailable: '
                               +str(library_path)+'. Set GOWIN_FREETYPE to an absolute '
                               'compatible library, or off to disable automatic preloading.')
        library = str(library_path.resolve())
        preload = env.get('LD_PRELOAD', '')
        entries = preload.split(':') if preload else []
        env['LD_PRELOAD'] = ':'.join([library, *[p for p in entries if p != library]])
    return env

#!/usr/bin/env python3
"""Read local gw_sh Tcl help only; no implementation or JTAG operation."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tools'))
from gowin_toolchain import IDE,environment
OUT=Path(__file__).resolve().parent
script=OUT/'query_help.tcl'
script.write_text('''puts "VERSION:[version]"
puts "GAO_COMMANDS:[info commands *gao*]"
puts "RUN_HELP"
run -h
puts "OPTIONS_HELP"
set_option -h
puts "ADD_HELP"
add_file -h
''')
r=subprocess.run([str(IDE/'bin/gw_sh'),str(script)],cwd=OUT,env=environment(),capture_output=True,text=True,timeout=45)
(OUT/'gw_sh_query_help.log').write_text(r.stdout+r.stderr)
print(r.stdout+r.stderr);print('process_exit',r.returncode)
raise SystemExit(r.returncode)

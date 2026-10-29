# Evidence report

Question: official method for updating an already routed GW5AST-138 BSRAM/ITCM or AE350 boot ROM image without repeating synthesis/PnR.

Findings from the examined excerpts:

- GW5AST-138 BSRAM content is handled during bitstream generation. SUG100 (PDF pp. 55-56, printed pp. 43-44) documents Print BSRAM Initial Value for GW5A(S)(T)-138/GW5AT-75, with default (all locations) or partial (used columns) modes when MSPI JUMP or Multi Boot is quad. SUG1220 (PDF pp. 58-59, printed pp. 51-52) documents `-bit_incl_bsram_init` and `-bsram_init_print_mode` for the same restriction. This is a generation option, not evidence of a standalone patcher for an already produced bitstream.

- The only documented post-routing update path in the excerpts is Gowin_PicoRV32 software/ITCM merging. It needs a .posp containing only BSRAM placement. SUG100 (PDF p. 48, printed p. 36) and SUG1220 (PDF p. 40, printed p. 33) document generating that file: GUI Place & Route > General > Generate Post-Place File, or `set_option -gen_posp 1`; default is off. IPUG913 (PDF pp. 14-15, printed pp. 7-8) gives the exact merge command `merge_bit.exe bin-file fs-file itcm_size posp-file` and requires the post-place file. The guide supports LittleBee, Arora, and Arora V families only (PDF p. 18, printed p. 11).

- AE350 is different: MUG1031 (PDF pp. 28, 38, printed pp. 20, 30) documents ITCM as an optional instruction memory with configurable size, default disabled and SPI Flash instruction memory enabled; initialization uses hexadecimal ITCM files generated through the make_hex tool. It does not document .posp generation, merge_bit, or any post-route update method in the examined scope. IPUG913 also does not extend merge_bit to AE350.

Practical conclusion:

For a parent design whose outputs include .fs, .vo, .pr, and .p but no .posp, the documented merge_bit workflow cannot be followed as-is; generation of .posp requires Place & Route to be rerun with the option enabled or a new build. The .fs regeneration path remains necessary for GW5AST-138 BSRAM initial-value changes. No documented AE350 post-routing shortcut was found in the examined pages. This is an absence in the examined scope, not proof of impossibility in all manual versions. Distinguish Gowin_PicoRV32 assumptions from AE350 or GW5AST-138; verify device/IP family before using any of these commands.

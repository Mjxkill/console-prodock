# Additional fresh hardware context, run03 (separate from task baseline)
Root executed exact BIN02 on R19 then restored it. CPU128B and TARGET unchanged, CLEAR times out phase8/result-5. Fresh NGDB snapshots sequence1/2/3: after CLEAR host_words16/received16, blitter ext_active1,busy1,state0x20(M_SETUP),opcode0x1c,ext_commandword0=0x1c000000,all12 engine_resetn flags high. Two post-failure snapshots100ms apart identical. Nonatomic raw geometry/pixel header taps both0x1c000000 are clues only, not atomic proof. GPUdone1/errors0,geom_cycles3. There is still no observed native request/acceptance or post-CLEAR memory read. Native ACK and pixel state are hypotheses, not established causes.

Evidence files (read by root; do not access board):
- result.json SHA256 3096cbf4323109926aec17d1900dc835f48371df88c15f71f4a43a15be227831
- microdma.log SHA256 d75f1a3afb30c7c2f2475aa0aee44583be5fd9cdb8372d940317e7a8b96e9d87
- journal.bin SHA256 17f453c398b2f5dcbad2769e7aa47c8ffda81827ce97c3f4a9d9e8368fc247e8

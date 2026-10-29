# G22 vs R5 USB public post-route: bounded equivalence report

## Scope and result

This is a read-only comparison of extracted public post-route VO cells. It is not RTL
simulation, not a physical-equivalence proof, and not a timing sign-off. No hardware was
used and no bitstream or source was changed.

`owned/analyze.py` returns the following baseline result for the supplied context:

- `pullup_equivalent = True`
- `clkdiv_reset_equivalent = True`
- `alu_i3_mode01_equivalent = True`
- `critical_parameter_changes = []`

The comparison covers 18,008 cells per build. `result.json` reports 927 literal changes:
835 ALU changes attributed only to `I3`, plus 92 other literal changes. The global
missing/added sets contain 15 names each.

## Pull-up boundary

The exact output cell is the common TBUF
`\u_usb_softphy_top/usb_pullup_en_o_s1` (ports `O=usb_pullup_en_o`,
`OEN=\u_usb_softphy_top/pullup_en_6`).

- G22: `I=\u_usb_softphy_top/n19_6`. That net is driven by LUT1
  `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/n19_s2` with
  `INIT=2'h1` over `usb_app_reset`, so it is `NOT(usb_app_reset)`. In turn,
  `usb_app_reset` is driven by LUT2 `usb_app_reset_s0` with `INIT=4'hE` over
  `rst_usb` and `PHY_RESET`, which is `rst_usb OR PHY_RESET`. The TBUF data input is
  therefore `NOT(rst_usb OR PHY_RESET)`, i.e. NOR.
- R5: `I=n19_6`. That net is driven by LUT2
  `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/n19_6_s` with
  `INIT=4'h1` over the same `rst_usb` and `PHY_RESET`, directly producing
  `NOT(rst_usb OR PHY_RESET)`, i.e. NOR.

The Boolean function is identical over the common leaves `rst_usb` and `PHY_RESET`.
The implementations are not structurally or physically identical: G22 has an extra LUT
stage (`usb_app_reset_s0` OR followed by `n19_s2` inversion), while R5 uses one LUT2.
The output and OEN cell names are shared, but the `I` net name and the routed path
differ, so route delay/parasitics cannot be assumed equal. Equal truth tables are not a
static-timing or implementation waiver.

The negative control changes R5 `n19_6_s.INIT` from `4'h1` to `4'hE` (OR instead of
NOR). The analyzer then reports `pullup_equivalent = False`, so the result depends on
the actual LUT contents rather than only on matching net names.

## CLKDIV reset boundary

The exact cell is
`\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/clkdiv_inst`.
Both builds have `DIV_MODE="8"` and the same `HCLKIN`, `CALIB`, and `CLKOUT` connections.

- G22: `RESETN=\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/n24_6_0`,
  driven by LUT1
  `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/n24_s2`
  with `INIT=2'h1` over
  `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/reset_calib_Z`.
- R5: `RESETN=\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/n24_6_0_3`,
  driven by LUT1
  `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/n24_6_0_s0`
  with the same `INIT=2'h1` over the same `reset_calib_Z`.

Both cones are `NOT(reset_calib_Z)`. The cell name, `DIV_MODE`, and clock connections are
unchanged; only the generated RESETN net name and LUT cell name differ. Route delay is
not proven equal.

The negative control changes R5 `n24_6_0_s0.INIT` from `2'h1` to `2'h2` (buffer instead
of inversion). The analyzer then reports `clkdiv_reset_equivalent = False`.

## ALU I3 mode-0/1 check

The check uses the official `ALU` model, not a mode-2 shortcut. For mode 0 (`ADD`),
`S=I0^I1` and `C=I0`; for mode 1 (`SUB`), `S=I0^~I1` and `C=I0`; both share
`SUM=S^CIN` and `COUT=S?CIN:C`. The analyzer exhaustively enumerates `I0`, `I1`, `CIN`,
and both values of `I3` for each mode and proves the outputs are independent of `I3`.
Mode 2 (`ADDSUB`) is not used for this claim.

`result.json` reports `i3_only_alu_count=835` and `i3_modes={"0":592,"1":243}`.
592 + 243 = 835, and no count is assigned to mode 2. This supports equivalence only for
those mode-0/1 I3-only changes; the 92 other literal changes are outside this claim.

## Critical parameters

All 14 common critical cells were compared, including both PLLs, IBUF/IOBUF/ELVDS_IOBUF/
TBUF, CLKDIV, DHCE, IDES8/IDES16, and OSER16. Their full normalized parameter maps are
identical, so `critical_parameter_changes` is empty. In particular, the two PLL parameter
sets match, and the TBUF/CLKDIV differences are port/net-name changes rather than parameter
changes. The PLL mutation control (`ODIV0_SEL=24` on R5 `\u_pll_f/PLL_inst`) produces a
nonempty change list.

## Remaining 92 literal changes and scope limits

The 92 non-I3-only changes break down by kind as: 49 DFFRE, 17 LUT4, 12 DFFCE, 5 DFFPE,
4 LUT3, one LUT4-to-LUT3, one LUT3-to-LUT4, one CLKDIV, one SDPB, and one TBUF.
Eighty-four cells have port/net-only differences with no parameter or LUT-literal
change; including the eight parameter/LUT-literal cells, the 92 cells contain 105 changed
port connections (55 `CE`, 18 `I2`, 8 `I0`, 5 `I1`, 5 `I3`, 4 `D`, 4 `CLK`, 3 `RESET`,
1 `RESETN`, 1 `CEB`, 1 `I`). They include the TBUF and CLKDIV boundary cells above.
Eight cells have parameter/LUT-literal changes:

- `\u_usb_fifo/n3567_s7`
- `\u_usb_fifo/n3567_s8`
- `\u_usb_fifo/n3903_s1`
- `\u_usb_fifo/usb_rx_buf_ep2/n68_s0`
- `\u_usb_fifo/usb_rx_buf_ep2/n82_s1`
- `\u_usb_fifo/usb_rx_buf_ep2/sync_rx_pkt_fifo/RAM_s6`
- `\u_usb_msc_guard/n1728_s2`
- `\u_usb_msc_guard/n2444_s1`

These eight are not all resolved to stable boundary leaves by this report, and the 84
port/net changes may be renames or real rewiring. They are not claimed equivalent.
The bounded `changed_cones.json` has 186 G22 cells and 187 R5 cells, with 171 common
names and 92 common literal differences. Its local set difference has 16 added names,
whereas the global `result.json` added list has 15; the extra local name
`\u_usb_fifo/usb_rx_buf_ep2/sync_rx_pkt_fifo/n25_s2` is a bounded-ancestor artifact, not
a global added cell. This report therefore distinguishes cell-name changes from
logic changes and does not infer physical equivalence from equal pins or names.

Global missing names (15):

- `\u_usb_device_controller_top/u_usb_device_controller/u_usb_device_controller_utmi/u_usb_init/gowin_split_inv_from_n316_s3`
- `\u_usb_device_controller_top/u_usb_device_controller/u_usb_device_controller_utmi/u_usb_init/n316_s3`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/n19_s2`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/DVE_0_s3`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/DVE_1_s3`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/cDV_0_s2`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/n352_s5`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/fifo_rx_pkt/fifo_4to8_sub_inst/n4_s2`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/fifo_rx_pkt/fifo_4to8_sub_inst/n9_s2`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/gowin_split_inv_from_n3370_s2`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/n3370_s2`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_tx_phy/q_data_hold_2_7_s3`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_tx_phy/u_fifo_8to4/fifo_8to4_sub_inst/w_empty_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/n24_s2`
- `usb_app_reset_s0`

Global added names (15):

- `\u_usb_device_controller_top/u_usb_device_controller/u_usb_device_controller_utmi/u_usb_init/gowin_split_inv_from_n316_8_s0`
- `\u_usb_device_controller_top/u_usb_device_controller/u_usb_device_controller_utmi/u_usb_init/n316_8_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/n19_6_s`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/DVE_0_7_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/DVE_1_7_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/cDV_0_6_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/DRU_500M_Top/u_dru_500m_logic/n352_10_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/fifo_rx_pkt/fifo_4to8_sub_inst/n4_6_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/fifo_rx_pkt/fifo_4to8_sub_inst/n9_6_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/gowin_split_inv_from_n3370_5_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/n3370_5_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_tx_phy/q_data_hold_2_7_7_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_tx_phy/u_fifo_8to4/fifo_8to4_sub_inst/w_empty_4_s0`
- `\u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/n24_6_0_s0`
- `usb_app_reset_s1`

## Interpretation and next nonintrusive check

The only USB-boundary logic differences shown here are the pull-up and CLKDIV reset
restructures, and both preserve Boolean function at the resolved leaves. That does not
establish a cause for the R5 no-USB-attach observation. The task states the R5 test must
be repeated; no cause should be claimed before that repeat, and even afterward a cause
requires mechanism evidence.

Proposed next check, without programming a new bitstream: repeat the R5 test on the same
NEW board with the same image, cable, port, and procedure; capture timestamped host logs
and, with a high-impedance probe, `usb_pullup_en_o` and `usb_dp` during attach. In parallel,
read the existing vendor post-route timing report for the paths to the TBUF `I`/`OEN`
and CLKDIV `RESETN` pins. Only if the failure repeats should those timing and waveform
facts be used to evaluate a mechanism. This is a diagnostic proposal, not a causal
conclusion, and it does not waive static timing.

// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vtb.h for the primary calling header

#ifndef VERILATED_VTB___024ROOT_H_
#define VERILATED_VTB___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vtb__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vtb___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ tb__DOT__clk;
    CData/*0:0*/ tb__DOT__bus80;
    CData/*0:0*/ tb__DOT__rtc;
    CData/*0:0*/ tb__DOT__locked;
    CData/*0:0*/ tb__DOT__por;
    CData/*0:0*/ tb__DOT__available;
    CData/*0:0*/ tb__DOT__dut__DOT__ae350_por_n;
    CData/*0:0*/ tb__DOT__dut__DOT__trial_holding;
    CData/*0:0*/ tb__DOT__ready;
    CData/*0:0*/ tb__DOT__rx;
    CData/*0:0*/ tb__DOT__ref_run;
    CData/*0:0*/ tb__DOT__bus_run;
    CData/*1:0*/ tb__DOT__dut__DOT__ae350_rst_sync;
    CData/*0:0*/ tb__DOT__dut__DOT__trial_request;
    CData/*0:0*/ tb__DOT__dut__DOT__trial_mode;
    CData/*0:0*/ tb__DOT__dut__DOT__trial_done;
    CData/*3:0*/ tb__DOT__dut__DOT__trial_epoch;
    CData/*2:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__up;
    CData/*7:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__rx_byte;
    CData/*0:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__rx_valid;
    CData/*2:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__parse_state;
    CData/*0:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__pending_mode;
    CData/*0:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__command_valid;
    CData/*0:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__command_mode;
    CData/*1:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__ready_meta;
    CData/*1:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__reset_meta;
    CData/*1:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__u_rx__DOT__rx_sync;
    CData/*3:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__u_rx__DOT__bit_idx;
    CData/*7:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__u_rx__DOT__shift;
    CData/*0:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__u_rx__DOT__busy;
    CData/*1:0*/ tb__DOT__dut__DOT__u_soc__DOT__init_sync;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb__DOT__locked__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb__DOT__available__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb__DOT__dut__DOT__trial_holding__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb__DOT__bus80__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb__DOT__dut__DOT__ae350_por_n__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__tb__DOT__por__0;
    CData/*0:0*/ __Vtrigprevexpr_h694c548e__0;
    CData/*0:0*/ __VactDidInit;
    CData/*0:0*/ __VactContinue;
    SData/*9:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__hold_count;
    SData/*15:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__u_rx__DOT__cnt;
    IData/*31:0*/ tb__DOT__phase_ps;
    IData/*31:0*/ tb__DOT__quick;
    IData/*31:0*/ tb__DOT__case_id;
    IData/*31:0*/ tb__DOT__result_fd;
    IData/*31:0*/ tb__DOT__releases;
    IData/*31:0*/ tb__DOT__loss__Vstatic__old_releases;
    IData/*16:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__gap_count;
    IData/*21:0*/ tb__DOT__dut__DOT__u_reset_trial__DOT__wait_count;
    IData/*31:0*/ __VactIterCount;
    double tb__DOT__last_lock_rise;
    double tb__DOT__last_available_rise;
    double tb__DOT__last_hold_end;
    double tb__DOT__last_policy_elapsed;
    double tb__DOT__release_check__DOT__origin;
    double tb__DOT__release_check__DOT__window;
    double tb__DOT__release_check__DOT__rise_time;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_h45eec793__0;
    VlTriggerScheduler __VtrigSched_h8aadc0b9__0;
    VlTriggerScheduler __VtrigSched_hbcfb8b1c__0;
    VlTriggerScheduler __VtrigSched_h8aadc088__0;
    VlTriggerScheduler __VtrigSched_hcea59483__0;
    VlTriggerScheduler __VtrigSched_h45eec960__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<12> __VactTriggered;
    VlTriggerVec<12> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vtb__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vtb___024root(Vtb__Syms* symsp, const char* v__name);
    ~Vtb___024root();
    VL_UNCOPYABLE(Vtb___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard

// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design internal header
// See Vreset_trial_tb.h for the primary calling header

#ifndef VERILATED_VRESET_TRIAL_TB___024ROOT_H_
#define VERILATED_VRESET_TRIAL_TB___024ROOT_H_  // guard

#include "verilated.h"
#include "verilated_timing.h"


class Vreset_trial_tb__Syms;

class alignas(VL_CACHE_LINE_BYTES) Vreset_trial_tb___024root final : public VerilatedModule {
  public:

    // DESIGN SPECIFIC STATE
    CData/*0:0*/ reset_trial_tb__DOT__clk;
    CData/*0:0*/ reset_trial_tb__DOT__ahb;
    CData/*0:0*/ reset_trial_tb__DOT__rtc;
    CData/*0:0*/ reset_trial_tb__DOT__locked;
    CData/*0:0*/ reset_trial_tb__DOT__ahb_run;
    CData/*0:0*/ reset_trial_tb__DOT__rtc_run;
    CData/*0:0*/ reset_trial_tb__DOT__rx;
    CData/*0:0*/ reset_trial_tb__DOT__ready;
    CData/*0:0*/ reset_trial_tb__DOT__release_request;
    CData/*0:0*/ reset_trial_tb__DOT__mode;
    CData/*0:0*/ reset_trial_tb__DOT__holding;
    CData/*0:0*/ reset_trial_tb__DOT__done;
    CData/*3:0*/ reset_trial_tb__DOT__epoch;
    CData/*1:0*/ reset_trial_tb__DOT__cpu_sync;
    CData/*7:0*/ reset_trial_tb__DOT__dut__DOT__ahb_div;
    CData/*7:0*/ reset_trial_tb__DOT__dut__DOT__rtc_div;
    CData/*2:0*/ reset_trial_tb__DOT__dut__DOT__up;
    CData/*7:0*/ reset_trial_tb__DOT__dut__DOT__rx_byte;
    CData/*0:0*/ reset_trial_tb__DOT__dut__DOT__rx_valid;
    CData/*2:0*/ reset_trial_tb__DOT__dut__DOT__parse_state;
    CData/*0:0*/ reset_trial_tb__DOT__dut__DOT__pending_mode;
    CData/*0:0*/ reset_trial_tb__DOT__dut__DOT__command_valid;
    CData/*0:0*/ reset_trial_tb__DOT__dut__DOT__command_mode;
    CData/*1:0*/ reset_trial_tb__DOT__dut__DOT__ready_meta;
    CData/*1:0*/ reset_trial_tb__DOT__dut__DOT__reset_meta;
    CData/*1:0*/ reset_trial_tb__DOT__dut__DOT__u_rx__DOT__rx_sync;
    CData/*3:0*/ reset_trial_tb__DOT__dut__DOT__u_rx__DOT__bit_idx;
    CData/*7:0*/ reset_trial_tb__DOT__dut__DOT__u_rx__DOT__shift;
    CData/*0:0*/ reset_trial_tb__DOT__dut__DOT__u_rx__DOT__busy;
    CData/*7:0*/ __Vtask_reset_trial_tb__DOT__command__0__complement;
    CData/*7:0*/ __Vtask_reset_trial_tb__DOT__command__17__m;
    CData/*7:0*/ __Vtask_reset_trial_tb__DOT__command__17__complement;
    CData/*7:0*/ __Vtask_reset_trial_tb__DOT__command__26__complement;
    CData/*7:0*/ __Vtask_reset_trial_tb__DOT__byte_tx__32__b;
    CData/*2:0*/ __Vdly__reset_trial_tb__DOT__dut__DOT__up;
    CData/*2:0*/ __Vdly__reset_trial_tb__DOT__dut__DOT__parse_state;
    CData/*0:0*/ __Vdly__reset_trial_tb__DOT__dut__DOT__pending_mode;
    CData/*0:0*/ __Vdly__reset_trial_tb__DOT__holding;
    CData/*0:0*/ __Vdly__reset_trial_tb__DOT__done;
    CData/*1:0*/ __Vdly__reset_trial_tb__DOT__dut__DOT__u_rx__DOT__rx_sync;
    CData/*3:0*/ __Vdly__reset_trial_tb__DOT__dut__DOT__u_rx__DOT__bit_idx;
    CData/*0:0*/ __VstlFirstIteration;
    CData/*0:0*/ __Vtrigprevexpr___TOP__reset_trial_tb__DOT__ahb__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__reset_trial_tb__DOT__locked__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__reset_trial_tb__DOT__rtc__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__reset_trial_tb__DOT__clk__0;
    CData/*0:0*/ __Vtrigprevexpr_h96b777c8__0;
    CData/*0:0*/ __Vtrigprevexpr_he9bf71c8__0;
    CData/*0:0*/ __Vtrigprevexpr___TOP__reset_trial_tb__DOT__release_request__0;
    CData/*0:0*/ __VactDidInit;
    CData/*0:0*/ __VactContinue;
    SData/*9:0*/ reset_trial_tb__DOT__dut__DOT__hold_count;
    SData/*15:0*/ reset_trial_tb__DOT__dut__DOT__u_rx__DOT__cnt;
    IData/*16:0*/ reset_trial_tb__DOT__dut__DOT__gap_count;
    IData/*21:0*/ reset_trial_tb__DOT__dut__DOT__wait_count;
    IData/*16:0*/ __Vdly__reset_trial_tb__DOT__dut__DOT__gap_count;
    IData/*31:0*/ __VactIterCount;
    VlDelayScheduler __VdlySched;
    VlTriggerScheduler __VtrigSched_h9651a875__0;
    VlTriggerScheduler __VtrigSched_h0e80afda__0;
    VlTriggerScheduler __VtrigSched_h3d88a5da__0;
    VlTriggerScheduler __VtrigSched_ha07b65f0__0;
    VlTriggerVec<1> __VstlTriggered;
    VlTriggerVec<9> __VactTriggered;
    VlTriggerVec<9> __VnbaTriggered;

    // INTERNAL VARIABLES
    Vreset_trial_tb__Syms* const vlSymsp;

    // CONSTRUCTORS
    Vreset_trial_tb___024root(Vreset_trial_tb__Syms* symsp, const char* v__name);
    ~Vreset_trial_tb___024root();
    VL_UNCOPYABLE(Vreset_trial_tb___024root);

    // INTERNAL METHODS
    void __Vconfigure(bool first);
};


#endif  // guard

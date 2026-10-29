// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VRESET_TRIAL_TB__SYMS_H_
#define VERILATED_VRESET_TRIAL_TB__SYMS_H_  // guard

#include "verilated.h"

// INCLUDE MODEL CLASS

#include "Vreset_trial_tb.h"

// INCLUDE MODULE CLASSES
#include "Vreset_trial_tb___024root.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES)Vreset_trial_tb__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vreset_trial_tb* const __Vm_modelp;
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vreset_trial_tb___024root      TOP;

    // SCOPE NAMES
    VerilatedScope __Vscope_reset_trial_tb;

    // CONSTRUCTORS
    Vreset_trial_tb__Syms(VerilatedContext* contextp, const char* namep, Vreset_trial_tb* modelp);
    ~Vreset_trial_tb__Syms();

    // METHODS
    const char* name() { return TOP.name(); }
};

#endif  // guard

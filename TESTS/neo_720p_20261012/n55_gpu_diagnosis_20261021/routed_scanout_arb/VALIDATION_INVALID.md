This first generated wrapper omitted the exported native_write, cpu_waiting
and request_read ports. Its testbench could treat X values as false in an if.
Regardless of its runtime result, it does not qualify the extended checks.
The original generator is archived as driver_initial.py. A corrected wrapper
and explicit four-state checks are rerun in routed_scanout_arb_r2.

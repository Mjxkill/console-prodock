init
set previous [nds.cpu curstate]
halt
set failed [catch {
 echo "ANALYSER_PREVIOUS $previous"
 foreach name {pc priv satp mstatus mie mtvec mepc mcause mtval sp ra} {
  echo "ANALYSER_CONTEXT [reg $name]"
 }
} reason]
if {$previous eq "running"} {resume;echo ANALYSER_RESUMED}
if {$failed} {error $reason}
echo CONTEXT_COMPLETE
shutdown

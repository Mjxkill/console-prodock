#!/usr/bin/env python3
"""Harmless real child-status fixture; never imports or runs a compiler."""
import os
import signal
import sys
pid=os.fork()
if pid==0:
    os.kill(os.getpid(),signal.SIGTERM)
    raise AssertionError('unreachable')
child,status=os.waitpid(pid,0)
assert child==pid and os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGTERM
print('observed_child_signal=15;parent_exit=3',flush=True)
sys.exit(3)

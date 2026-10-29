"""Finite, bounded subprocess pipes for one owned provider CLI.

The byte limit is enforced while reading, not after communicate() has already
allocated arbitrary output. Exceptions retain only the bounded partial bytes.
The caller owns process-group termination and reaping on failure.
"""
import os
import selectors
import subprocess
import time


class CaptureLimit(RuntimeError):
    """Provider exceeded the actual in-memory capture bound."""


def capture(child, prompt, timeout, maximum=32 << 20):
    selector = selectors.DefaultSelector()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    position = 0
    deadline = time.monotonic() + timeout
    for stream, name in ((child.stdout, 'stdout'), (child.stderr, 'stderr')):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    os.set_blocking(child.stdin.fileno(), False)
    selector.register(child.stdin, selectors.EVENT_WRITE, 'stdin')
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(child.args, timeout)
            for key, unused in selector.select(min(0.25, remaining)):
                stream, name = key.fileobj, key.data
                if name == 'stdin':
                    if position < len(prompt):
                        try:
                            position += os.write(stream.fileno(), prompt[position:position + 65536])
                        except BlockingIOError:
                            continue
                        except BrokenPipeError:
                            position = len(prompt)
                    if position == len(prompt):
                        selector.unregister(stream)
                        stream.close()
                else:
                    try:
                        data = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        selector.unregister(stream)
                        continue
                    if sum(map(len, buffers.values())) + len(data) > maximum:
                        raise CaptureLimit('Output capture bound exceeded')
                    buffers[name].extend(data)
        child.wait(timeout=max(0.001, deadline - time.monotonic()))
        return bytes(buffers['stdout']), bytes(buffers['stderr'])
    except BaseException as error:
        error.captured_stdout = bytes(buffers['stdout'])
        error.captured_stderr = bytes(buffers['stderr'])
        raise
    finally:
        selector.close()
        if not child.stdin.closed:
            child.stdin.close()

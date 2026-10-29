"""Host-only RX2 retry correction; frozen receiver and wire format unchanged.

sender_base.py is a pinned archival dependency, not a second maintained copy.
NACK has no attempt identifier. Pending duplicates cannot prove that the latest
transmission failed, and an exhausted transmit budget must still read its ACK.
"""
import time
from sender_base import *
from sender_base import Session as BaseSession


class Session(BaseSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nack_events = 0

    def _classify_block(self, event, initial, end):
        kind, reply = event
        if kind != 'reply':
            raise TransferError('receiver returned during DATA')
        self._checkpoint(reply)
        if reply.kind == 'X':
            raise TransferError('receiver terminal reason ' + str(reply.reason))
        if reply.kind == 'A' and reply.offset == end and reply.reason == 0:
            return reply
        if reply.kind == 'A' and reply.offset <= initial and reply.reason == 0:
            return None
        if reply.kind == 'N' and reply.offset == initial and reply.reason == 1:
            self.nack_events += 1
            return None
        raise Uncertain('unexpected acknowledgement')

    def _available_after_nack(self, initial, end, deadline):
        """Consume already received replies before another write; never wait.

        Validate all complete lines, including any X/RETURN after an ACK. A
        partial reply is completed read-only within the existing deadline.
        Late data after this finite drain remains possible on an async link;
        outgoing frames remain inert Base64/NUL if the receiver has exited.
        """
        received = 0
        ack = None
        while True:
            if time.monotonic() >= deadline:
                raise Uncertain('NACK drain deadline; no retransmission allowed')
            while b'\n' in self.pending:
                line, _, tail = self.pending.partition(b'\n')
                self.pending[:] = tail
                event = self._line(bytes(line))
                if event is not None:
                    observed = self._classify_block(event, initial, end)
                    if observed is not None:
                        ack = observed
            data = self.io.read(0)
            if not data:
                if not self.pending:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Uncertain('partial reply deadline; no retransmission allowed')
                event = self.event(remaining)
                observed = self._classify_block(event, initial, end)
                if observed is not None:
                    ack = observed
                continue
            self.pending.extend(data)
            received += len(data)
            if len(self.pending) > 8192 or received > 32768:
                raise Uncertain('bounded output exceeded')
        return ack

    def block(self, mutate=None):
        """At most four DATA frames; after final NACK only read until deadline.

        No CRC/offset/nonce check is relaxed. A terminal response or timeout
        remains failure. retries counts actual repeated transmissions, while
        nack_events retains every parsed NACK, including queued duplicates.
        """
        if self.offset >= len(self.data):
            raise TransferError('no block remains')
        initial = self.offset
        data = self.data[initial:initial + BLOCK]
        end = initial + len(data)
        packet = frame(self.nonce, 1, self.seq, initial, data)
        for attempt in range(4):
            if attempt:
                if time.monotonic() >= deadline:
                    raise Uncertain('retry deadline; no retransmission allowed')
                self.retries += 1
            self.send(mutate(packet, attempt) if mutate else packet)
            deadline = time.monotonic() + self.idle_ms / 1000 + 1
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Uncertain('ACK deadline; no retransmission allowed')
                event = self.event(remaining)
                ack = self._classify_block(event, initial, end)
                if ack is not None:
                    self.offset, self.seq = ack.offset, ack.seq
                    return ack
                if event[0] == 'reply' and event[1].kind == 'N':
                    ack = self._available_after_nack(initial, end, deadline)
                    if ack is not None:
                        self.offset, self.seq = ack.offset, ack.seq
                        return ack
                    if attempt < 3:
                        break
                    # All writes are already spent. A stale NACK cannot rule
                    # out a correct final transmission still being processed.
                    # Await ACK/X/RETURN using the same unchanged deadline.
        raise TransferError('NACK retry limit')

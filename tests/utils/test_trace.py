from types import SimpleNamespace

from pyjr100.utils.trace import TraceRecorder


def _via_snapshot(**kwargs):
    defaults = {"IFR": 0x00, "IER": 0x00, "ORB": 0x00, "DDRB": 0x00, "T1": 0x0000, "T2": 0x0000}
    defaults.update(kwargs)
    return defaults


def test_trace_recorder_overwrites_old_entries():
    recorder = TraceRecorder(capacity=2)
    state = SimpleNamespace(pc=0x1000, a=0x11, b=0x22, x=0x3344, sp=0x01FF, cc=0x40)

    recorder.record_step(state, 0x86, 5, _via_snapshot(IFR=0x01), wai=False, halted=False)
    state2 = SimpleNamespace(pc=0x1002, a=0x33, b=0x44, x=0x5566, sp=0x01F0, cc=0x10)
    recorder.record_step(state2, 0x97, 4, _via_snapshot(IFR=0x02), wai=False, halted=False)
    state3 = SimpleNamespace(pc=0x1004, a=0x55, b=0x66, x=0x7788, sp=0x01E0, cc=0x00)
    recorder.record_step(state3, 0x3E, 0, _via_snapshot(IFR=0x40), wai=True, halted=False, note="wai-latch")

    lines = list(recorder.format_entries())
    assert len(lines) == 2
    assert "pc=1002" in lines[0]
    assert "pc=1004" in lines[1]
    assert "flags=WAI,wai-latch" in lines[1]


def test_trace_recorder_handles_empty_state():
    recorder = TraceRecorder(1)
    state = SimpleNamespace(pc=0x2000, a=0, b=0, x=0, sp=0, cc=0)
    recorder.record_step(state, None, 0, _via_snapshot(), wai=False, halted=True, note="halted")
    lines = list(recorder.format_entries())
    assert len(lines) == 1
    assert "opcode=--" in lines[0]
    assert "flags=HALT,halted" in lines[0]

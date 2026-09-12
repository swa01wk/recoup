"""Apply supports/contradicts/neutral direction from evidence bundle."""

from __future__ import annotations

from ..models.recovery import EvidenceBundle, OperationalSignal, SignalDirection


def apply_signal_directions(
    signals: list[OperationalSignal],
    bundle: EvidenceBundle,
) -> list[OperationalSignal]:
    support = set(bundle.supporting_signal_ids)
    counter = set(bundle.counter_signal_ids)
    out: list[OperationalSignal] = []
    for sig in signals:
        direction = SignalDirection.NEUTRAL
        strength = 0.5
        if sig.signal_id in support:
            direction = SignalDirection.SUPPORTS
            strength = 0.85
        elif sig.signal_id in counter:
            direction = SignalDirection.CONTRADICTS
            strength = 0.75
        out.append(sig.model_copy(update={"direction": direction, "strength": strength}))
    return out

from app.services import OptionalPerception, TemporalActivityFilter, VideoService, VisionEngine, speak


def test_services_are_exposed_at_package_level():
    assert isinstance(OptionalPerception(), OptionalPerception)
    assert VisionEngine is not None
    assert VideoService is not None
    assert callable(speak)


def test_temporal_confirmation_holds_when_three_signals_exceed_one_second():
    temporal = TemporalActivityFilter(window=3, min_confidence=0.7, max_window_seconds=1.0)

    assert temporal.observe("OPEN", 0.9, observed_at=0.0) is None
    assert temporal.observe("OPEN", 0.9, observed_at=0.6) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.1) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.7) is None


def test_duplicate_frame_timestamp_cannot_count_as_new_evidence():
    temporal = TemporalActivityFilter(window=3, min_confidence=0.7, max_window_seconds=1.0)

    assert temporal.observe("OPEN", 0.9, observed_at=1.0) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.0) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.1) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.2) == "OPEN"


def test_confirmed_frame_cannot_be_replayed_into_new_consensus():
    temporal = TemporalActivityFilter(window=3, min_confidence=0.7, max_window_seconds=1.0)

    assert temporal.observe("OPEN", 0.9, observed_at=1.0) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.1) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.2) == "OPEN"
    assert temporal.observe("OPEN", 0.9, observed_at=1.2) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.3) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.4) is None
    assert temporal.observe("OPEN", 0.9, observed_at=1.5) == "OPEN"

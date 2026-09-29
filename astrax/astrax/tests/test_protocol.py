from app.protocol import ProtocolEngine

def confirm(engine, activity, confidence=.95):
    return engine.observe(activity, confidence)

def test_correct_sequence_completes():
    e=ProtocolEngine(); e.start()
    for a in ["OPEN","PICK","INSERT","ROTATE","CLOSE"]:
        result=confirm(e,a)
        assert result["status"] in {"VALID","COMPLETE"}
    assert e.complete
    assert e.status == "COMPLETED"

def test_wrong_step_does_not_advance():
    e=ProtocolEngine(); e.start()
    result=confirm(e,"ROTATE")
    assert result["status"] == "OUT_OF_ORDER"
    assert e.index == 0

def test_reset():
    e=ProtocolEngine(); e.start(); confirm(e,"OPEN"); e.reset()
    assert e.status == "READY"
    assert e.index == 0

from app.services.ai import AIIntegration


def test_ai_integration_reports_capabilities():
    ai = AIIntegration()
    status = ai.status()
    assert "supported" in status
    assert "model" in status
    assert "fallback" in status
    assert "ready" in status

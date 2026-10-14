from relyxus_api.modules.health.metrics import render_prometheus_metrics
from relyxus_api.modules.health.schema import ReadinessStatus


def test_render_includes_ready_gauge() -> None:
    text = render_prometheus_metrics(api_version="0.4.8", readiness=ReadinessStatus.NOT_READY)

    assert "relyxus_ready 0" in text
    assert 'version="0.4.8"' in text

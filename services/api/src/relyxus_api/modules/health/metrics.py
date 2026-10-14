"""Minimal Prometheus text exposition (TSD-11.01, MP-28.01)."""

from relyxus_api.modules.health.schema import ReadinessStatus


def render_prometheus_metrics(*, api_version: str, readiness: ReadinessStatus) -> str:
    ready_value = 1 if readiness is ReadinessStatus.READY else 0
    lines = [
        "# HELP relyxus_up Whether the API process is running.",
        "# TYPE relyxus_up gauge",
        "relyxus_up 1",
        "# HELP relyxus_ready Whether required dependencies are reachable.",
        "# TYPE relyxus_ready gauge",
        f"relyxus_ready {ready_value}",
        "# HELP relyxus_api_info Static API contract metadata.",
        "# TYPE relyxus_api_info gauge",
        f'relyxus_api_info{{version="{api_version}"}} 1',
    ]
    return "\n".join(lines) + "\n"

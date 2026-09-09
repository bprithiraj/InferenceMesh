"""Low-cardinality service metrics."""

from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter(
    "inferencemesh_requests_total",
    "Completed inference requests.",
    ("task", "backend", "status"),
)
REQUEST_LATENCY = Histogram(
    "inferencemesh_request_duration_seconds",
    "Backend attempt duration, excluding gateway admission wait.",
    ("task", "backend"),
)
TIME_TO_FIRST_TOKEN = Histogram(
    "inferencemesh_time_to_first_token_seconds",
    "Time between backend selection and first content, excluding gateway admission wait.",
    ("backend",),
)
ADMISSION_ACTIVE = Gauge(
    "inferencemesh_admission_active",
    "Requests currently holding inference capacity.",
)
ADMISSION_WAITING = Gauge(
    "inferencemesh_admission_waiting",
    "Requests currently waiting for inference capacity.",
)
ADMISSION_REJECTIONS = Counter(
    "inferencemesh_admission_rejections_total",
    "Requests rejected by bounded admission control.",
    ("reason",),
)

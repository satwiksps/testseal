"""TestSeal's deterministic test-suite integrity auditor."""

from .auditor import Auditor, audit_diff
from .config import Config, ConfigError, load_config
from .models import AuditResult, Confidence, Finding, Severity

__all__ = [
    "AuditResult",
    "Auditor",
    "Confidence",
    "Config",
    "ConfigError",
    "Finding",
    "Severity",
    "audit_diff",
    "load_config",
]

__version__ = "1.0.0"

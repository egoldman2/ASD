"""Runtime switches checked before calling optional host AI services."""

import os


def feature_enabled(name="AI_MODE_ENABLED"):
    """Default to enabled locally; unknown configured values fail closed."""
    return os.getenv(name, "true").strip().casefold() in {"1", "true", "yes", "on"}

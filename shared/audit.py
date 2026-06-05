import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("audit")


def log_event(
    event_type: str,
    actor: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Write a structured audit event. Every EHDS-relevant action goes through here."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "actor": actor,
        "resource_id": resource_id,
        "details": details or {},
    }
    logger.info(json.dumps(entry))

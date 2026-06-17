"""
Jupyter server config for SPE containers.

Logs every notebook save to stdout. Docker captures this as container logs —
the SPE provisioner can read them via `docker logs` for the audit trail
(EHDS Article 73). The container is network-isolated so it cannot write
directly to the external audit DB; stdout is the correct mechanism here.
"""

import os
import json
from datetime import datetime, timezone


def _audit(event: str, path: str):
    entry = {
        "ts":        datetime.now(timezone.utc).isoformat(),
        "event":     event,
        "permit_id": os.getenv("PERMIT_ID", "unknown"),
        "path":      path,
    }
    print(json.dumps(entry), flush=True)


class AuditHandler:
    def post_save(self, model, os_path, contents_manager):
        _audit("notebook.save", os_path)


c = get_config()  # noqa: F821 — Jupyter injects this
c.ServerApp.contents_manager_class = "jupyter_server.services.contents.filemanager.AsyncFileContentsManager"

_handler = AuditHandler()
c.ContentsManager.post_save_hook = _handler.post_save

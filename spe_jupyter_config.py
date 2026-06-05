"""
Jupyter server config for SPE containers.
Logs every save event to stdout — Docker captures these as container logs,
which the SPE provisioner reads for the audit trail (EHDS Article 73).
"""

import os
import json
import datetime


def _audit(event: str, path: str):
    entry = {
        "ts":         datetime.datetime.utcnow().isoformat(),
        "event":      event,
        "permit_id":  os.getenv("PERMIT_ID", "unknown"),
        "path":       path,
    }
    print(json.dumps(entry), flush=True)


class AuditHandler:
    def post_save(self, model, os_path, contents_manager):
        _audit("notebook.save", os_path)


c = get_config()  # noqa: F821 — Jupyter injects this
c.ServerApp.contents_manager_class = "jupyter_server.services.contents.filemanager.AsyncFileContentsManager"

# Register the post-save hook
_handler = AuditHandler()
c.ContentsManager.post_save_hook = _handler.post_save

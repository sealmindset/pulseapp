import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from azure.storage.blob import BlobServiceClient, ContentSettings

# Environment
_BLOB_CONN = (
    os.getenv("BLOB_CONN_STRING")
    or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    or os.getenv("AzureWebJobsStorage")
)
_CONTAINER = os.getenv("PROMPTS_CONTAINER", "prompts")

_service_client: Optional[BlobServiceClient] = None


def _get_service() -> BlobServiceClient:
    global _service_client
    if _service_client is None:
        if not _BLOB_CONN:
            raise RuntimeError("Missing BLOB_CONN_STRING or AZURE_STORAGE_CONNECTION_STRING")
        _service_client = BlobServiceClient.from_connection_string(_BLOB_CONN)
    return _service_client


def get_container_client():
    svc = _get_service()
    cc = svc.get_container_client(_CONTAINER)
    try:
        cc.create_container()
    except Exception:
        # Already exists or no permission to create (assume exists)
        pass
    return cc


def read_json(path: str) -> Optional[Dict[str, Any]]:
    cc = get_container_client()
    bc = cc.get_blob_client(path)
    try:
        data = bc.download_blob().readall()
    except Exception:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return None


def write_json(path: str, obj: Dict[str, Any]) -> None:
    cc = get_container_client()
    bc = cc.get_blob_client(path)
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    bc.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
    )


def blob_exists(path: str) -> bool:
    cc = get_container_client()
    bc = cc.get_blob_client(path)
    try:
        bc.get_blob_properties()
        return True
    except Exception:
        return False


def list_blob_names(prefix: str) -> List[str]:
    cc = get_container_client()
    return [b.name for b in cc.list_blobs(name_starts_with=prefix)]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_prompt_id_from_title(title: str) -> str:
    base = ''.join(ch.lower() if ch.isalnum() or ch in ['-',' '] else '-' for ch in title)
    base = '-'.join(filter(None, base.replace(' ', '-').split('-')))
    base = base[:40]
    suf = str(uuid.uuid4()).split('-')[0]
    return f"{base}-{suf}" if base else suf

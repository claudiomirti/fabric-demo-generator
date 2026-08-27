"""
Produced by Claudio Mirti

Microsoft Fabric REST API client and OneLake file upload utilities.

Two distinct APIs are used — each requires its own OAuth scope:

  1. Fabric REST API  (BASE_URL)
     Scope : https://api.fabric.microsoft.com/.default
     Used for : workspace metadata, lakehouse CRUD, long-running operation polling.
     Docs    : https://learn.microsoft.com/en-us/rest/api/fabric/

  2. OneLake Data API (onelake.dfs.fabric.microsoft.com)
     Scope : https://storage.azure.com/.default  ← Azure Data Lake Storage Gen2
     Used for : file create / append / flush (the ADLSGen2 multipart protocol).
     Docs    : https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-directory-file-acl-python

OneLake upload protocol (ADLSGen2 multipart):
  PUT  ?resource=file          → creates an empty file at the path
  PATCH ?action=append&position=0 → streams the file content
  PATCH ?action=flush&position=N  → commits / finalises the upload

Item creation
-------------
Lakehouses, semantic models, and ontologies are all created through the same
Fabric Items pattern: POST a `displayName` plus a `definition` made of
base64-encoded `parts`, then follow the 202-Accepted long-running operation to
completion. `_create_item()` encapsulates that, and `b64()` / `part()` build the
definition payloads.
"""
import base64
import json
import time
from typing import Any

import requests

from src.auth import get_access_token

BASE_URL = "https://api.fabric.microsoft.com/v1"
# A few dataset settings (large storage format, refresh) exist only here
POWERBI_URL = "https://api.powerbi.com/v1.0/myorg"
# OneLake file operations require the Azure Storage scope, NOT the Fabric scope
STORAGE_SCOPE = "https://storage.azure.com/.default"


def b64(payload: Any) -> str:
    """
    Encode an item-definition part for the Fabric Items API.

    Every part of a Fabric item definition is transmitted as a base64 string
    with payloadType 'InlineBase64'. dicts/lists are serialised to JSON first.
    """
    text = json.dumps(payload, indent=2) if isinstance(payload, (dict, list)) else payload
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def part(path: str, payload: Any) -> dict:
    """Build a single item-definition part entry."""
    return {"path": path, "payload": b64(payload), "payloadType": "InlineBase64"}


def _headers() -> dict:
    """Build JSON request headers with a fresh Fabric API bearer token."""
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


def _storage_token() -> str:
    """
    Obtain a bearer token scoped to Azure Storage for OneLake DFS operations.

    OneLake exposes the ADLSGen2 REST API, which is authenticated against
    https://storage.azure.com — a completely separate scope from the Fabric API.
    Using a Fabric-scoped token here produces a 401 Unauthorized error.
    """
    from src.auth import get_credential
    token = get_credential().get_token(STORAGE_SCOPE)
    return token.token


def get_workspace(workspace_id: str) -> dict:
    """
    Fetch workspace metadata by ID.

    Used on startup to validate that the user has access to the target workspace
    before attempting any provisioning steps.

    Returns the raw Fabric API workspace object (displayName, id, type, etc.).
    Raises requests.HTTPError on 401 (bad token) or 404 (workspace not found).
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_lakehouses(workspace_id: str) -> list:
    """
    Return all Lakehouses in a workspace as a list of API objects.

    Used by the orchestrator to check whether the target Lakehouse already
    exists before attempting to create it, enabling idempotent runs.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/lakehouses"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("value", [])


def create_lakehouse(workspace_id: str, name: str, description: str = "") -> dict:
    """
    Create a new Lakehouse item in the given workspace.

    Fabric may respond with either:
      - 201 Created  → lakehouse object returned directly in the body
      - 202 Accepted → long-running operation; poll the Location header URL

    Returns the lakehouse object dict (containing at minimum an 'id' field).
    """
    return _create_item(
        workspace_id,
        "lakehouses",
        {"displayName": name, "description": description[:256]},
    )


def _poll_long_running(operation_url: str, max_wait: int = 600) -> dict:
    """
    Poll a Fabric long-running operation URL until it reaches a terminal state.

    Fabric returns 202 + a Location URL for operations that may take > 1 second
    (e.g. Lakehouse creation, table loads, item creation). This function polls
    until either:
      - status is 'Succeeded' / 'Completed' → returns the result object
      - status is 'Failed' / 'Undetermined' → raises RuntimeError
      - max_wait seconds elapsed            → raises TimeoutError

    Some operations expose their payload at `{operation_url}/result` rather than
    inline on the status response, so that URL is fetched as a fallback. Not all
    operations have a result body (a table load, for example, returns nothing),
    which is why a missing result is not treated as an error.

    Args:
        operation_url: Absolute URL or relative path from the Location header.
        max_wait: Maximum seconds to wait before giving up (default 600 = 10 min).
    """
    if not operation_url:
        raise RuntimeError("Fabric returned 202 Accepted without a Location header.")
    if not operation_url.startswith("http"):
        operation_url = f"https://api.fabric.microsoft.com/{operation_url.lstrip('/')}"

    elapsed = 0
    while elapsed < max_wait:
        resp = requests.get(operation_url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = str(data.get("status", "")).lower()

        if status in ("succeeded", "completed"):
            if isinstance(data.get("result"), dict):
                return data["result"]
            # Result payloads live on a sibling /result endpoint for item creates.
            try:
                result = requests.get(f"{operation_url}/result", headers=_headers(), timeout=30)
                if result.status_code == 200:
                    return result.json()
            except requests.RequestException:
                pass
            return data
        if status in ("failed", "canceled", "cancelled", "undetermined"):
            raise RuntimeError(f"Fabric operation failed: {data.get('error', data)}")

        wait = int(resp.headers.get("Retry-After", 5) or 5)
        time.sleep(wait)
        elapsed += wait
    raise TimeoutError(f"Fabric operation timed out after {max_wait}s.")


def _create_item(workspace_id: str, collection: str, payload: dict) -> dict:
    """
    POST an item to a Fabric item collection, transparently handling the
    202-Accepted long-running-operation path.

    Args:
        collection: The plural REST collection segment, e.g. 'lakehouses',
                    'semanticModels', or 'ontologies'.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/{collection}"
    resp = requests.post(url, json=payload, headers=_headers(), timeout=120)

    if resp.status_code == 202:
        return _poll_long_running(resp.headers.get("Location"))

    if not resp.ok:
        raise RuntimeError(f"{resp.status_code} creating {collection}: {resp.text}")
    return resp.json()


def list_items(workspace_id: str, collection: str) -> list:
    """Return every item in a Fabric item collection (lakehouses, ontologies, ...)."""
    url = f"{BASE_URL}/workspaces/{workspace_id}/{collection}"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("value", [])


def find_item_by_name(workspace_id: str, collection: str, display_name: str) -> dict | None:
    """Return the item with the given displayName, or None if it does not exist."""
    for item in list_items(workspace_id, collection):
        if item.get("displayName") == display_name:
            return item
    return None


def delete_item(workspace_id: str, collection: str, item_id: str) -> None:
    """
    Delete an item. Used to make provisioning idempotent: semantic models and
    ontologies cannot be meaningfully "reused" when their definition changes,
    so an existing one is replaced rather than left stale.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/{collection}/{item_id}"
    resp = requests.delete(url, headers=_headers(), timeout=60)
    if resp.status_code not in (200, 202, 204, 404):
        resp.raise_for_status()


def get_lakehouse(workspace_id: str, lakehouse_id: str) -> dict:
    """
    Fetch a single Lakehouse, including its SQL analytics endpoint properties.

    The SQL endpoint is provisioned asynchronously after the Lakehouse itself,
    so `properties.sqlEndpointProperties.provisioningStatus` may still be
    'InProgress' immediately after creation.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def load_table_from_csv(
    workspace_id: str,
    lakehouse_id: str,
    table_name: str,
    relative_path: str,
    mode: str = "Overwrite",
) -> None:
    """
    Convert a CSV already sitting in the Lakehouse Files section into a managed
    Delta table, using the Lakehouse 'Load table' REST API.

    This is the programmatic equivalent of right-clicking a CSV in the Fabric
    portal and choosing **Load to Tables**. It is what turns the uploaded files
    into something a Direct Lake semantic model can actually read.

    Args:
        table_name    : Target Delta table name. Must match ^[A-Za-z0-9_]{1,256}$
                        and contain at least one letter or underscore.
        relative_path : Source path inside the Lakehouse, and it *must* start
                        with 'Files/' — the API rejects anything else.
        mode          : 'Overwrite' (default) or 'Append'.

    Raises:
        RuntimeError on a non-success response or a failed operation.
    """
    if not relative_path.startswith("Files/"):
        raise ValueError(f"relativePath must start with 'Files/', got: {relative_path}")

    url = (
        f"{BASE_URL}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}"
        f"/tables/{table_name}/load"
    )
    payload = {
        "relativePath": relative_path,
        "pathType": "File",
        "mode": mode,
        "recursive": False,
        "formatOptions": {"format": "Csv", "header": True, "delimiter": ","},
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=120)

    if resp.status_code == 202:
        _poll_long_running(resp.headers.get("Location"))
        return
    if not resp.ok:
        raise RuntimeError(f"{resp.status_code} loading table {table_name}: {resp.text}")


def detect_table_schema(
    workspace_id: str,
    lakehouse_id: str,
    table_names: list[str],
) -> str | None:
    """
    Work out whether the lakehouse stores Delta tables under a schema folder.

    Fabric has two lakehouse layouts and they are not interchangeable:

        classic          Tables/fact_sales/
        schema-enabled   Tables/dbo/fact_sales/

    A Direct Lake model must declare `schemaName` for the second layout and must
    omit it for the first. Getting this wrong is silent at creation time and only
    surfaces when the model is framed, as "one or multiple source tables either
    do not exist or access was denied".

    Rather than assume, this lists `Tables/` in OneLake and looks at what is
    actually there.

    Returns:
        The schema name (e.g. 'dbo'), or None for a classic lakehouse.
    """
    try:
        listing = requests.get(
            f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}",
            params={
                "resource": "filesystem",
                "recursive": "false",
                "directory": f"{lakehouse_id}/Tables",
            },
            headers={"Authorization": f"Bearer {_storage_token()}"},
            timeout=60,
        )
        if not listing.ok:
            return None

        entries = [
            str(p.get("name", "")).rsplit("/", 1)[-1]
            for p in listing.json().get("paths", [])
            if str(p.get("isDirectory", "false")).lower() == "true"
        ]
    except (requests.RequestException, ValueError, KeyError):
        return None

    wanted = set(table_names)
    # A directory named after one of our tables means they sit directly under
    # Tables/, so there is no schema level.
    if wanted & set(entries):
        return None
    # Otherwise the single remaining directory is the schema folder.
    candidates = [e for e in entries if e and not e.startswith("_")]
    return candidates[0] if len(candidates) == 1 else None


def get_delta_table_schema(
    workspace_id: str,
    lakehouse_id: str,
    table_name: str,
    lakehouse_name: str | None = None,
    schema_name: str | None = None,
) -> dict[str, str]:
    """
    Read the true column types of a Delta table.

    Why this exists
    ---------------
    The Lakehouse 'Load table' API infers column types from the CSV, and the
    inference rules are not documented. A Direct Lake semantic model is only
    valid if its declared `dataType` for each column matches the underlying Delta
    column, so rather than guessing, this reads ground truth.

    Two sources are tried, in order:
      1. The OneLake Table API, which exposes a Unity-Catalog-shaped table
         description including a `type_name` per column. Preferred, but it
         addresses the lakehouse by *name*, so it is only tried when the name
         is known.
      2. The Delta transaction log. Every Delta table stores its schema as a
         `metaData` action inside `_delta_log/*.json`, which is a plain file in
         OneLake and readable with the same DFS token used for uploads.

    Returns:
        {column_name: spark_type_string}, e.g. {'quantity': 'long', 'date': 'date'}
        Returns {} when neither source can be read, so callers fall back to the
        types declared in src/semantic_model.py.
    """
    if lakehouse_name:
        columns = _schema_via_table_api(
            workspace_id, lakehouse_name, table_name, schema_name or "dbo"
        )
        if columns:
            return columns
    return _schema_via_delta_log(workspace_id, lakehouse_id, table_name, schema_name)


def _schema_via_table_api(
    workspace_id: str,
    lakehouse_name: str,
    table_name: str,
    schema: str = "dbo",
) -> dict[str, str]:
    """Read column types from the OneLake Table API. Returns {} on any failure."""
    catalog = f"{lakehouse_name}.Lakehouse"
    url = (
        f"https://onelake.table.fabric.microsoft.com/delta/{workspace_id}/{catalog}"
        f"/api/2.1/unity-catalog/tables/{catalog}.{schema}.{table_name}"
    )
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {_storage_token()}"},
            timeout=60,
        )
        if not resp.ok:
            return {}
        return {
            column["name"]: str(column.get("type_name", "string")).lower()
            for column in resp.json().get("columns") or []
        }
    except (requests.RequestException, ValueError, KeyError):
        return {}


def _schema_via_delta_log(
    workspace_id: str,
    lakehouse_id: str,
    table_name: str,
    schema_name: str | None = None,
) -> dict[str, str]:
    """Read column types from the table's Delta transaction log. Returns {} on failure."""
    headers = {"Authorization": f"Bearer {_storage_token()}"}
    prefix = f"Tables/{schema_name}" if schema_name else "Tables"
    log_dir = f"{lakehouse_id}/{prefix}/{table_name}/_delta_log"

    try:
        listing = requests.get(
            f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}",
            params={"resource": "filesystem", "recursive": "false", "directory": log_dir},
            headers=headers,
            timeout=60,
        )
        if not listing.ok:
            return {}

        commits = sorted(
            p["name"]
            for p in listing.json().get("paths", [])
            if str(p.get("name", "")).endswith(".json")
        )

        # Walk newest → oldest and stop at the first commit carrying a metaData
        # action; later commits may only contain add/remove file actions.
        for commit in reversed(commits):
            content = requests.get(
                f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{commit}",
                headers=headers,
                timeout=60,
            )
            if not content.ok:
                continue
            for line in content.text.splitlines():
                if not line.strip():
                    continue
                try:
                    action = json.loads(line)
                except json.JSONDecodeError:
                    continue
                schema_string = action.get("metaData", {}).get("schemaString")
                if not schema_string:
                    continue
                return {
                    field["name"]: _spark_type_name(field["type"])
                    for field in json.loads(schema_string).get("fields", [])
                }
    except (requests.RequestException, ValueError, KeyError):
        return {}
    return {}


def _spark_type_name(field_type: Any) -> str:
    """
    Reduce a Delta/Spark schema type to a simple lowercase name.

    Complex types (struct, array, map) arrive as dicts; they have no scalar
    equivalent in a tabular model, so they are reported by their type keyword.
    """
    if isinstance(field_type, dict):
        return str(field_type.get("type", "string")).lower()
    return str(field_type).lower()


def create_semantic_model(
    workspace_id: str,
    name: str,
    description: str,
    model_bim: dict,
) -> dict:
    """
    Create a semantic model from a TMSL (model.bim) definition.

    The TMSL/BIM format is used rather than TMDL because a single JSON document
    is far easier to generate correctly than a folder of indentation-sensitive
    .tmdl files, and it is the format Microsoft's own semantic-link-labs library
    uses when uploading models through this endpoint.

    Args:
        model_bim: The full TMSL model document (see src/tmdl.py).
    """
    payload = {
        "displayName": name,
        "description": description[:256],
        "definition": {
            "parts": [
                part("model.bim", model_bim),
                part("definition.pbidataset", {"version": "1.0", "settings": {}}),
            ]
        },
    }
    return _create_item(workspace_id, "semanticModels", payload)


def _powerbi_headers() -> dict:
    """
    Build JSON request headers with a Power BI-scoped bearer token.

    A small number of dataset settings have no Fabric API equivalent and exist
    only on api.powerbi.com, which is a different audience from the Fabric API —
    a Fabric token here returns 401.
    """
    from src.auth import get_credential, POWERBI_SCOPE
    token = get_credential().get_token(POWERBI_SCOPE).token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def set_large_storage_format(workspace_id: str, dataset_id: str) -> None:
    """
    Switch a semantic model to large semantic model storage format.

    Direct Lake needs this: models created through the Fabric REST API land in
    the default 'Abf' (small) storage mode, and a Direct Lake model in small
    mode will not frame correctly. The portal sets it automatically, the API
    does not, so it has to be done explicitly.

    There is no TMSL property for this — it is a dataset-level setting reachable
    only through the Power BI REST API.
    """
    url = f"{POWERBI_URL}/groups/{workspace_id}/datasets/{dataset_id}"
    resp = requests.patch(
        url,
        json={"targetStorageMode": "PremiumFiles"},
        headers=_powerbi_headers(),
        timeout=60,
    )
    resp.raise_for_status()


def refresh_semantic_model(workspace_id: str, dataset_id: str, max_wait: int = 300) -> str:
    """
    Frame a Direct Lake semantic model and wait for it to finish.

    For Direct Lake, a refresh does not load data into memory — it reads the
    Delta table metadata and records which Parquet files the model should read
    at query time. This is called 'framing'. Until it has happened at least
    once the model has no snapshot to serve queries from, so a freshly created
    model appears empty.

    Returns the final status string, e.g. 'Completed'.
    """
    url = f"{POWERBI_URL}/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
    headers = _powerbi_headers()

    resp = requests.post(url, json={"type": "full"}, headers=headers, timeout=60)
    resp.raise_for_status()

    # An enhanced refresh returns 202 + a Location header holding the request id.
    # A synchronous 200 means the work is already done.
    if resp.status_code != 202:
        return "Completed"
    request_id = resp.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
    if not request_id:
        return "Accepted"

    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(5)
        status_resp = requests.get(f"{url}/{request_id}", headers=headers, timeout=60)
        if not status_resp.ok:
            continue
        status = status_resp.json().get("status", "")
        if status == "Completed":
            return status
        if status in ("Failed", "Disabled", "Cancelled"):
            raise RuntimeError(f"Refresh {status.lower()}: {status_resp.text}")
    raise TimeoutError(f"Refresh did not complete within {max_wait}s")


def create_ontology(
    workspace_id: str,
    name: str,
    description: str,
    parts: list[dict],
) -> dict:
    """
    Create a Fabric Ontology (preview) item from pre-built definition parts.

    Args:
        parts: Definition parts already encoded by `part()` — see src/ontology.py,
               which assembles .platform, definition.json, EntityTypes/ and
               RelationshipTypes/ folders.
    """
    payload = {
        "displayName": name,
        "description": description[:256],
        "definition": {"parts": parts},
    }
    return _create_item(workspace_id, "ontologies", payload)


def upload_file_to_lakehouse(
    workspace_id: str,
    lakehouse_id: str,
    file_path: str,
    fabric_path: str,
) -> None:
    """
    Upload a local file into a Lakehouse's Files section via the OneLake DFS API.

    Files land under the Lakehouse's 'Files/' root, making them visible in
    the Fabric portal under Files → <fabric_path>.  After upload, they can be
    promoted to managed Delta tables using 'Load to Tables' in the portal.

    The ADLSGen2 multipart upload protocol requires three sequential requests:
      1. PUT  ?resource=file          — create an empty placeholder file
      2. PATCH ?action=append&pos=0  — write the full file content
      3. PATCH ?action=flush&pos=N   — commit / close the file

    Args:
        workspace_id : GUID of the target Fabric workspace.
        lakehouse_id : GUID of the target Lakehouse item.
        file_path    : Absolute local path of the file to upload.
        fabric_path  : Destination path inside Files/, e.g. 'Retail/fact_sales.csv'.
    """
    upload_url = (
        f"https://onelake.dfs.fabric.microsoft.com/"
        f"{workspace_id}/{lakehouse_id}/Files/{fabric_path}"
    )
    # OneLake DFS uses Azure Storage scope — must NOT use the Fabric API token
    token = _storage_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Create an empty file at the target path (409 = already exists, safe to ignore)
    resp = requests.put(
        f"{upload_url}?resource=file",
        headers=headers,
        timeout=60,
    )
    if resp.status_code not in (200, 201, 409):
        resp.raise_for_status()

    # Step 2: Append the full file content starting at byte position 0
    with open(file_path, "rb") as f:
        content = f.read()

    resp = requests.patch(
        f"{upload_url}?action=append&position=0",
        data=content,
        headers={**headers, "Content-Type": "application/octet-stream"},
        timeout=120,
    )
    resp.raise_for_status()

    # Step 3: Flush (commit) the upload — position must equal total byte length
    resp = requests.patch(
        f"{upload_url}?action=flush&position={len(content)}",
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()

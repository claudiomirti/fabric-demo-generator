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
"""
import time
import requests
from src.auth import get_access_token

BASE_URL = "https://api.fabric.microsoft.com/v1"
# OneLake file operations require the Azure Storage scope, NOT the Fabric scope
STORAGE_SCOPE = "https://storage.azure.com/.default"


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
    url = f"{BASE_URL}/workspaces/{workspace_id}/lakehouses"
    payload = {
        "displayName": name,
        "description": description,
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=60)

    if resp.status_code == 202:
        # Long-running operation — Fabric returns a polling URL in Location header
        operation_url = resp.headers.get("Location") or resp.headers.get("x-ms-operation-id")
        return _poll_long_running(operation_url)

    resp.raise_for_status()
    return resp.json()


def _poll_long_running(operation_url: str, max_wait: int = 300) -> dict:
    """
    Poll a Fabric long-running operation URL until it reaches a terminal state.

    Fabric returns 202 + a Location URL for operations that may take > 1 second
    (e.g. Lakehouse creation). This function polls every 5 seconds until either:
      - status is 'Succeeded' / 'Completed' → returns the result object
      - status is 'Failed' / 'Canceled'     → raises RuntimeError
      - max_wait seconds elapsed             → raises TimeoutError

    Args:
        operation_url: Absolute URL or relative path from the Location header.
        max_wait: Maximum seconds to wait before giving up (default 300 = 5 min).
    """
    if not operation_url.startswith("http"):
        operation_url = f"https://api.fabric.microsoft.com/{operation_url}"

    elapsed = 0
    while elapsed < max_wait:
        resp = requests.get(operation_url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "").lower()
        if status in ("succeeded", "completed"):
            return data.get("result", data)
        if status in ("failed", "canceled"):
            raise RuntimeError(f"Fabric operation failed: {data.get('error', data)}")
        time.sleep(5)
        elapsed += 5
    raise TimeoutError("Fabric operation timed out.")


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

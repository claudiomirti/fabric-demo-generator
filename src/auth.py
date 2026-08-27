"""
Produced by Claudio Mirti

Authentication module for Microsoft Fabric and Azure Storage APIs.

Authentication strategy (in priority order):
  1. AzureCliCredential  — uses an existing `az login` session (preferred for demos)
  2. InteractiveBrowserCredential — opens a browser login prompt as fallback

The credential object is cached for the lifetime of the process so that
subsequent token requests reuse the same session without re-prompting.

Two OAuth scopes are used throughout the app:
  - FABRIC_SCOPE   : for all Fabric REST API calls (workspaces, lakehouses, etc.)
  - STORAGE_SCOPE  : for OneLake / Azure Data Lake Storage Gen2 file operations
    (see fabric_client.py — OneLake uses a different endpoint and scope)
  - POWERBI_SCOPE  : for the handful of dataset operations the Fabric API does
    not expose — setting large semantic model storage format and triggering a
    refresh — which live only on the Power BI REST API
"""
from azure.identity import AzureCliCredential, InteractiveBrowserCredential, ChainedTokenCredential

# OAuth 2.0 scope for the Microsoft Fabric REST API
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"

# OAuth 2.0 scope for the Power BI REST API (api.powerbi.com). Required for
# dataset-level settings that have no Fabric API equivalent.
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# Module-level credential singleton — avoids re-prompting on every token request
_credential = None


def get_credential() -> ChainedTokenCredential:
    """
    Return (or lazily create) the shared credential chain.

    ChainedTokenCredential tries each provider in order and returns the first
    that succeeds, so users with `az login` sessions never see a browser popup.
    """
    global _credential
    if _credential is None:
        _credential = ChainedTokenCredential(
            AzureCliCredential(),
            InteractiveBrowserCredential()
        )
    return _credential


def get_access_token() -> str:
    """
    Obtain a short-lived bearer token for the Fabric REST API.

    azure-identity handles token caching and silent refresh automatically,
    so this is safe to call on every request without rate-limiting concerns.
    """
    cred = get_credential()
    token = cred.get_token(FABRIC_SCOPE)
    return token.token


def reset_credential() -> None:
    """
    Clear the cached credential, forcing re-authentication on the next call.
    Called by the UI logout button so the user can switch Azure accounts.
    """
    global _credential
    _credential = None

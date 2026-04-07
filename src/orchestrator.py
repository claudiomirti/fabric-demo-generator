"""
Produced by Claudio Mirti

Provisioning orchestrator for the Fabric Data Demo Generator.

This module is the top-level coordinator that ties together:
  - data_generator  : produces synthetic pandas DataFrames per industry
  - fabric_client   : creates Fabric items and uploads files via REST APIs
  - semantic_model  : provides schema metadata for the completion summary

Design — streaming generator pattern
-------------------------------------
`provision()` is a Python generator that yields log message strings one at a
time.  Gradio's streaming update mechanism consumes these yielded values and
appends them to the UI log textbox in real time, giving the user live feedback
without blocking the browser.

Provisioning steps (in order):
  1. Validate workspace access
  2. Create (or reuse) a Lakehouse named  {Industry}_Demo_Lakehouse
  3. Generate synthetic DataFrames for the chosen industry
  4. Export each DataFrame to CSV in a temp directory
  5. Upload each CSV to OneLake via the ADLSGen2 protocol
  6. Print a completion summary with next-step guidance
"""
import os
import tempfile
import time
from typing import Generator

import pandas as pd

from src.data_generator import generate_data
from src.fabric_client import (
    get_workspace,
    list_lakehouses,
    create_lakehouse,
    upload_file_to_lakehouse,
)
from src.semantic_model import get_model


INDUSTRY_ICONS = {
    "Retail": "🛒",
    "Manufacturing": "🏭",
    "FSI": "🏦",
    "Healthcare": "🏥",
    "Life Science": "🔬",
}


def provision(
    industry: str,
    workspace_id: str,
    row_count: int = 1000,
) -> Generator[str, None, None]:
    """
    Orchestrate end-to-end provisioning of a demo dataset into Microsoft Fabric.

    This is a generator function — callers iterate over it to receive incremental
    log lines.  Gradio's streaming output handles this automatically when the
    function is wired to a gr.Textbox output with streaming enabled.

    Args:
        industry    : One of the five supported industries (must match GENERATORS keys).
        workspace_id: GUID of the target Fabric workspace.
        row_count   : Number of rows to generate in each fact table (default 1000).

    Yields:
        str — log message lines (may contain Markdown for the Gradio renderer).

    Flow:
        validate workspace → create/reuse lakehouse → generate data
        → export CSVs → upload each file → print summary
    """
    icon = INDUSTRY_ICONS.get(industry, "📦")
    workspace_id = workspace_id.strip()

    yield f"🔐 Verifying access to Fabric workspace `{workspace_id}`..."
    try:
        ws = get_workspace(workspace_id)
        ws_name = ws.get("displayName", workspace_id)
        yield f"✅ Connected to workspace: **{ws_name}**\n"
    except Exception as e:
        yield f"❌ Cannot access workspace: {e}\n⛔ Provisioning aborted."
        return

    # ── 1. Create Lakehouse ────────────────────────────────────────────────────
    lakehouse_name = f"{industry.replace(' ', '_')}_Demo_Lakehouse"
    yield f"🏗️  Creating Lakehouse: `{lakehouse_name}`..."
    try:
        # Check if it already exists
        existing = list_lakehouses(workspace_id)
        match = next((lh for lh in existing if lh.get("displayName") == lakehouse_name), None)
        if match:
            lakehouse_id = match["id"]
            yield f"ℹ️  Lakehouse already exists (id: `{lakehouse_id}`). Reusing.\n"
        else:
            result = create_lakehouse(
                workspace_id,
                lakehouse_name,
                f"Auto-generated demo lakehouse for {industry} industry.",
            )
            lakehouse_id = result.get("id") or result.get("objectId", "unknown")
            yield f"✅ Lakehouse created! id: `{lakehouse_id}`\n"
    except Exception as e:
        yield f"❌ Failed to create Lakehouse: {e}\n⛔ Provisioning aborted."
        return

    # ── 2. Generate synthetic data ─────────────────────────────────────────────
    yield f"{icon} Generating {row_count:,} rows of synthetic **{industry}** data..."
    try:
        tables = generate_data(industry, row_count)
        yield f"✅ Generated {len(tables)} tables: {', '.join(f'`{t}`' for t in tables)}\n"
    except Exception as e:
        yield f"❌ Data generation failed: {e}"
        return

    # ── 3. Upload CSVs to Lakehouse ────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        for table_name, df in tables.items():
            local_path = os.path.join(tmp, f"{table_name}.csv")
            df.to_csv(local_path, index=False)

            fabric_path = f"{industry.replace(' ', '_')}/{table_name}.csv"
            yield f"📤 Uploading `{table_name}.csv` ({len(df):,} rows) → Files/{fabric_path}..."
            try:
                upload_file_to_lakehouse(workspace_id, lakehouse_id, local_path, fabric_path)
                yield f"   ✅ Uploaded successfully."
            except Exception as e:
                yield f"   ⚠️  Upload failed: {e}"
            time.sleep(0.3)  # small delay to avoid rate-limiting

    # ── 4. Semantic model summary ──────────────────────────────────────────────
    model = get_model(industry)
    yield "\n---"
    yield "## 🏁 Provisioning Complete!"
    yield f"- **Workspace:** {ws_name}"
    yield f"- **Lakehouse:** {lakehouse_name} (`{lakehouse_id}`)"
    yield f"- **Tables uploaded:** {', '.join(tables.keys())}"
    yield f"- **Semantic model:** {len(model['tables'])} tables · {len(model['relationships'])} relationships · {len(model['key_measures'])} measures"
    yield "\n💡 Next step: open the Lakehouse in Fabric, load the CSVs as Delta tables, then create a semantic model using the schema shown in the **Schema Preview** tab."


def validate_workspace_id(workspace_id: str) -> tuple[bool, str]:
    """
    Lightweight workspace validation used by the UI 'Validate' button.

    Performs a single GET /workspaces/{id} call and returns a human-readable
    result without triggering any provisioning.

    Returns:
        (True,  "✅ Workspace found: <name>") on success
        (False, "❌ <error message>")          on failure
    """
    wid = workspace_id.strip()
    if not wid:
        return False, "Please enter a Workspace ID."
    try:
        ws = get_workspace(wid)
        name = ws.get("displayName", wid)
        return True, f"✅ Workspace found: **{name}**"
    except Exception as e:
        return False, f"❌ {e}"

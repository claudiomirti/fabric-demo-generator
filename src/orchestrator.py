"""
Produced by Claudio Mirti

Provisioning orchestrator for the Fabric Data Demo Generator.

This module is the top-level coordinator that ties together:
  - data_generator  : produces synthetic pandas DataFrames per industry
  - fabric_client   : creates Fabric items and uploads files via REST APIs
  - semantic_model  : the star schema plus the business descriptions
  - tmdl            : builds the Direct Lake semantic model definition
  - ontology        : builds the Fabric Ontology definition

Design — streaming generator pattern
-------------------------------------
`provision()` is a Python generator that yields log message strings one at a
time. Gradio's streaming update mechanism consumes these yielded values and
appends them to the UI log textbox in real time, giving the user live feedback
without blocking the browser.

Two provisioning modes
----------------------
"csv"  — the original behaviour. Generate the data and drop CSV files into the
         Lakehouse Files section. Fast, and leaves the user free to model the
         data however they like.

"full" — everything in "csv", then continue: convert each CSV into a managed
         Delta table, build a Direct Lake semantic model carrying business
         descriptions on every table, column, and measure (so a Fabric data
         agent can answer natural-language questions about it), and create an
         Ontology describing the same domain as entities and relationships.

Steps beyond the CSV upload are deliberately non-fatal: if the semantic model
or ontology cannot be created, the run reports it and continues, because a
Lakehouse full of Delta tables is still a useful outcome on its own.
"""
import os
import re
import tempfile
import time
from typing import Generator

from src.data_generator import generate_data
from src.fabric_client import (
    create_lakehouse,
    create_ontology,
    create_semantic_model,
    delete_item,
    detect_table_schema,
    find_item_by_name,
    get_delta_table_schema,
    get_workspace,
    list_lakehouses,
    load_table_from_csv,
    refresh_semantic_model,
    set_large_storage_format,
    upload_file_to_lakehouse,
)
from src.ontology import build_ontology_parts, summarise_ontology
from src.semantic_model import (
    get_model,
    lakehouse_name as lakehouse_item_name,
    model_name as semantic_model_name,
    ontology_name as ontology_item_name,
)
from src.tmdl import build_model_bim


INDUSTRY_ICONS = {
    "Retail": "🛒",
    "Manufacturing": "🏭",
    "FSI": "🏦",
    "Healthcare": "🏥",
    "Life Science": "🔬",
}

# Provisioning modes, as surfaced by the UI radio button.
MODE_CSV = "csv"
MODE_FULL = "full"

# The Lakehouse 'Load table' API rejects anything outside this pattern.
_VALID_TABLE_NAME = re.compile(r"^(?=[0-9]*[a-zA-Z_])[a-zA-Z0-9_]{1,256}$")


def provision(
    industry: str,
    workspace_id: str,
    row_count: int = 1000,
    mode: str = MODE_CSV,
) -> Generator[str, None, None]:
    """
    Orchestrate end-to-end provisioning of a demo dataset into Microsoft Fabric.

    This is a generator function — callers iterate over it to receive incremental
    log lines. Gradio's streaming output handles this automatically when the
    function is wired to a gr.Textbox/gr.Markdown output.

    Args:
        industry    : One of the five supported industries.
        workspace_id: GUID of the target Fabric workspace.
        row_count   : Number of rows to generate in each fact table.
        mode        : MODE_CSV to stop after uploading CSV files, or MODE_FULL to
                      also build Delta tables, a semantic model, and an ontology.

    Yields:
        str — log message lines (may contain Markdown for the Gradio renderer).
    """
    icon = INDUSTRY_ICONS.get(industry, "📦")
    workspace_id = workspace_id.strip()
    full = mode == MODE_FULL

    yield f"🔐 Verifying access to Fabric workspace `{workspace_id}`..."
    try:
        ws = get_workspace(workspace_id)
        ws_name = ws.get("displayName", workspace_id)
        yield f"✅ Connected to workspace: **{ws_name}**\n"
    except Exception as e:
        yield f"❌ Cannot access workspace: {e}\n⛔ Provisioning aborted."
        return

    # ── 1. Create Lakehouse ────────────────────────────────────────────────────
    lakehouse_name = lakehouse_item_name(industry)
    yield f"🏗️  Creating Lakehouse: `{lakehouse_name}`..."
    try:
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

    # ── 3. Upload CSVs to the Lakehouse Files section ──────────────────────────
    folder = industry.replace(" ", "_")
    uploaded: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        for table_name, df in tables.items():
            local_path = os.path.join(tmp, f"{table_name}.csv")
            df.to_csv(local_path, index=False)

            fabric_path = f"{folder}/{table_name}.csv"
            yield f"📤 Uploading `{table_name}.csv` ({len(df):,} rows) → Files/{fabric_path}..."
            try:
                upload_file_to_lakehouse(workspace_id, lakehouse_id, local_path, fabric_path)
                uploaded.append(table_name)
                yield "   ✅ Uploaded successfully."
            except Exception as e:
                yield f"   ⚠️  Upload failed: {e}"
            time.sleep(0.3)  # small delay to avoid rate-limiting

    if not full:
        yield from _csv_summary(industry, ws_name, lakehouse_name, lakehouse_id, uploaded)
        return

    # ── 4. Convert the uploaded CSVs into managed Delta tables ─────────────────
    yield "\n---"
    yield "## 🔄 Building Delta tables"
    delta_tables: list[str] = []

    for table_name in uploaded:
        if not _VALID_TABLE_NAME.match(table_name):
            yield f"⚠️  Skipping `{table_name}` — not a valid Delta table name."
            continue
        yield f"🧱 Loading `{table_name}` as a Delta table..."
        try:
            load_table_from_csv(
                workspace_id,
                lakehouse_id,
                table_name,
                f"Files/{folder}/{table_name}.csv",
            )
            delta_tables.append(table_name)
            yield "   ✅ Delta table ready."
        except Exception as e:
            yield f"   ⚠️  Load failed: {e}"

    if not delta_tables:
        yield "\n❌ No Delta tables were created, so the semantic model and ontology were skipped."
        yield from _csv_summary(industry, ws_name, lakehouse_name, lakehouse_id, uploaded)
        return

    # ── 5. Read the real column types back out of OneLake ──────────────────────
    # A Direct Lake model must declare exactly the types Delta actually stored;
    # the load API infers them from the CSV, so they are read rather than guessed.
    # The table layout is inspected too: schema-enabled lakehouses store tables
    # under Tables/dbo/, classic ones directly under Tables/, and the model has
    # to match or framing fails.
    yield "\n🔎 Inspecting the Delta tables in OneLake..."
    table_schema = detect_table_schema(workspace_id, lakehouse_id, delta_tables)
    yield (
        f"   ✅ Schema-enabled lakehouse — tables live under `{table_schema}`."
        if table_schema
        else "   ✅ Classic lakehouse — tables live directly under `Tables/`."
    )

    delta_schemas: dict[str, dict[str, str]] = {}
    for table_name in delta_tables:
        try:
            schema = get_delta_table_schema(
                workspace_id, lakehouse_id, table_name, lakehouse_name, table_schema
            )
        except Exception:
            schema = {}
        if schema:
            delta_schemas[table_name] = schema
    if delta_schemas:
        yield f"   ✅ Resolved column types for {len(delta_schemas)} table(s)."
    else:
        yield "   ℹ️  Could not read Delta types; falling back to the declared schema."

    # ── 6. Semantic model (Direct Lake, described for the data agent) ──────────
    yield "\n---"
    yield "## 📊 Creating the semantic model"
    model = get_model(industry)
    sm_name = semantic_model_name(industry)
    semantic_model_created = False
    model_framed = False

    try:
        existing_model = find_item_by_name(workspace_id, "semanticModels", sm_name)
        if existing_model:
            yield f"♻️  Replacing existing semantic model `{sm_name}`..."
            delete_item(workspace_id, "semanticModels", existing_model["id"])

        model_bim = build_model_bim(
            industry, workspace_id, lakehouse_id, delta_schemas, table_schema
        )
        yield f"🧠 Creating `{sm_name}` (Direct Lake on OneLake)..."
        created = create_semantic_model(workspace_id, sm_name, model["description"], model_bim)
        semantic_model_created = True
        yield (
            f"   ✅ Semantic model created — {len(model['tables'])} tables, "
            f"{len(model['relationships'])} relationships, "
            f"{len(model['key_measures'])} measures, all described for the data agent."
        )

        dataset_id = created.get("id") or created.get("objectId")
        if not dataset_id:
            found = find_item_by_name(workspace_id, "semanticModels", sm_name)
            dataset_id = found.get("id") if found else None

        if dataset_id:
            # Direct Lake requires large storage format, and the REST API — unlike
            # the portal — creates the model in the default small format.
            yield "📦 Switching to large semantic model storage format..."
            try:
                set_large_storage_format(workspace_id, dataset_id)
                yield "   ✅ Large storage format enabled."
            except Exception as e:
                yield f"   ⚠️  Could not set storage format: {e}"

            # Framing: reads Delta metadata so the model has something to query.
            # Without it the model loads but returns no data.
            yield "🔄 Framing the model (reading Delta metadata)..."
            try:
                refresh_semantic_model(workspace_id, dataset_id)
                yield "   ✅ Model framed and ready to query."
                model_framed = True
            except Exception as e:
                yield f"   ⚠️  Framing failed: {e}"
                yield "   ℹ️  Refresh the semantic model manually in Fabric before using it."
        else:
            yield "   ⚠️  Could not resolve the new model's ID; skipped storage format and framing."
    except Exception as e:
        yield f"   ⚠️  Semantic model creation failed: {e}"

    # ── 7. Ontology (preview) ──────────────────────────────────────────────────
    yield "\n---"
    yield "## 🕸️  Creating the ontology"
    ont_name = ontology_item_name(industry)
    ontology_created = False

    try:
        existing_ontology = find_item_by_name(workspace_id, "ontologies", ont_name)
        if existing_ontology:
            yield f"♻️  Replacing existing ontology `{ont_name}`..."
            delete_item(workspace_id, "ontologies", existing_ontology["id"])

        parts = build_ontology_parts(
            industry, workspace_id, lakehouse_id, ont_name, delta_schemas, table_schema
        )
        yield f"🔗 Creating `{ont_name}` — {summarise_ontology(industry)}..."
        create_ontology(workspace_id, ont_name, model["description"], parts)
        ontology_created = True
        yield "   ✅ Ontology created."
    except Exception as e:
        yield f"   ⚠️  Ontology creation failed: {e}"
        yield "   ℹ️  Ontologies are a preview feature and require a supported Fabric capacity."

    # ── 8. Summary ─────────────────────────────────────────────────────────────
    yield "\n---"
    yield "## 🏁 Provisioning Complete!"
    yield f"- **Workspace:** {ws_name}"
    yield f"- **Lakehouse:** {lakehouse_name} (`{lakehouse_id}`)"
    yield f"- **Delta tables:** {', '.join(delta_tables)}"
    yield f"- **Semantic model:** {sm_name} {'✅' if semantic_model_created else '⚠️ not created'}"
    yield f"- **Ontology:** {ont_name} {'✅' if ontology_created else '⚠️ not created'}"

    if semantic_model_created:
        yield (
            "\n💡 Next step: in Fabric, create a **data agent** and add "
            f"`{sm_name}` as a data source. Every table, column, and measure "
            "already carries a business description, so you can ask questions in "
            "plain language straight away — see `DEMO_QUESTIONS.md` for ideas."
        )
        if not model_framed:
            yield (
                "⚠️  The model was not framed. Open it in Fabric and refresh it "
                "once, otherwise it will return no data."
            )


def _csv_summary(
    industry: str,
    ws_name: str,
    lakehouse_name: str,
    lakehouse_id: str,
    uploaded: list[str],
) -> Generator[str, None, None]:
    """Closing summary for a CSV-only run."""
    model = get_model(industry)
    yield "\n---"
    yield "## 🏁 Provisioning Complete!"
    yield f"- **Workspace:** {ws_name}"
    yield f"- **Lakehouse:** {lakehouse_name} (`{lakehouse_id}`)"
    yield f"- **CSV files uploaded:** {', '.join(uploaded) if uploaded else 'none'}"
    yield (
        f"- **Suggested model:** {len(model['tables'])} tables · "
        f"{len(model['relationships'])} relationships · "
        f"{len(model['key_measures'])} measures"
    )
    yield (
        "\n💡 Next step: open the Lakehouse in Fabric and load the CSVs as Delta "
        "tables, then build a semantic model using the schema shown in the "
        "**Schema Preview** tab. Or re-run this generator with **Full "
        "provisioning** to have all of that created for you."
    )


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

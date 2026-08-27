"""
Produced by Claudio Mirti

Builds a Direct Lake semantic model (TMSL / model.bim) from the metadata in
`src/semantic_model.py`.

Why TMSL and not TMDL
---------------------
Fabric accepts a semantic model definition either as a folder of `.tmdl` files
or as a single `model.bim` TMSL document. TMDL is whitespace- and
indentation-sensitive, which makes it fragile to generate by string
concatenation; TMSL is plain JSON. Microsoft's own `semantic-link-labs` library
uploads models through this endpoint as `model.bim`, so that is what is used
here. Descriptions land in the `description` property of each object, which is
exactly what the `///` syntax in TMDL compiles down to.

Why Direct Lake on OneLake
--------------------------
The shared M expression only needs the workspace ID and the lakehouse ID:

    let
        Source = AzureStorage.DataLake("https://onelake.dfs.fabric.microsoft.com/{ws}/{lh}")
    in
        Source

Direct Lake on SQL would additionally require the lakehouse's SQL analytics
endpoint connection string and its database GUID, which are provisioned
asynchronously after the lakehouse is created — extra waiting and extra failure
modes for no benefit here. Direct Lake on OneLake also never falls back to
DirectQuery.

Details that decide whether the model works at all
--------------------------------------------------
A Direct Lake model that parses can still open with "Unable to load a query that
produces no tables". Four things have to line up:

  * The shared expression is named `DL_Lakehouse`. Fabric uses `DatabaseQuery`
    only for the Direct Lake on SQL flavour.
  * The model carries a `PBI_QueryOrder` annotation naming that expression, which
    is how Fabric knows which expression to evaluate when loading the model.
  * Every partition source sets `schemaName` — but only when the lakehouse
    actually is schema-enabled. Fabric has two layouts, `Tables/fact_sales` and
    `Tables/dbo/fact_sales`, and declaring a schema the lakehouse does not have
    (or omitting one it does) makes framing fail with "one or multiple source
    tables either do not exist or access was denied".
  * Every table carries `sourceLineageTag` in `[schema].[table]` form.

Descriptions are the point
--------------------------
Every table, column, and measure carries a `description`. Fabric data agents and
Copilot read this metadata to map a natural-language question onto the right
model object, so the descriptions authored in `src/semantic_model.py` are the
main thing that makes the generated model usable by an agent.
"""
import json
import uuid

# Name of the shared M expression every Direct Lake partition sources from.
EXPRESSION_NAME = "DL_Lakehouse"

from src.semantic_model import get_model

# Declared type (src/semantic_model.py) → TMSL dataType.
TMSL_TYPES = {
    "string": "string",
    "int64": "int64",
    "double": "double",
    "boolean": "boolean",
    "dateTime": "dateTime",
    "decimal": "decimal",
}

# Spark/Delta type (read from _delta_log) → TMSL dataType. Anything unmapped
# falls back to string, which is always a safe representation.
SPARK_TO_TMSL = {
    "string": "string",
    "byte": "int64",
    "short": "int64",
    "integer": "int64",
    "long": "int64",
    "float": "double",
    "double": "double",
    "boolean": "boolean",
    "date": "dateTime",
    "timestamp": "dateTime",
    "timestamp_ntz": "dateTime",
    "binary": "string",
}


def _tmsl_type(declared: str, spark_type: str | None) -> str:
    """
    Resolve the TMSL dataType for a column.

    The actual Delta type always wins when it is known, because a Direct Lake
    column whose declared type disagrees with storage fails at query time. The
    type declared in src/semantic_model.py is only a fallback for when the
    transaction log could not be read.
    """
    if spark_type:
        if spark_type.startswith("decimal"):
            return "decimal"
        if spark_type in SPARK_TO_TMSL:
            return SPARK_TO_TMSL[spark_type]
        return "string"
    return TMSL_TYPES.get(declared, "string")


def _summarize_by(column: str, tmsl_type: str, is_key: bool) -> str:
    """
    Decide whether Power BI should implicitly aggregate a column.

    Identifiers, years, and key columns are numeric but summing them is
    meaningless, so they are marked 'none' to keep the model honest and to stop
    an agent inventing a "sum of customer id".
    """
    if is_key or column.endswith("_id") or column.endswith("_year"):
        return "none"
    if tmsl_type in ("int64", "double", "decimal"):
        return "sum"
    return "none"


def _relationship_targets(model: dict) -> set[tuple[str, str]]:
    """Return the (table, column) pairs that sit on the 'one' side of a relationship."""
    targets = set()
    for rel in model["relationships"]:
        table, column = rel["to"].split(".", 1)
        targets.add((table, column))
    return targets


def _relationship_sources(model: dict) -> set[tuple[str, str]]:
    """Return the (table, column) pairs that sit on the 'many' side of a relationship."""
    sources = set()
    for rel in model["relationships"]:
        table, column = rel["from"].split(".", 1)
        sources.add((table, column))
    return sources


def build_model_bim(
    industry: str,
    workspace_id: str,
    lakehouse_id: str,
    delta_schemas: dict[str, dict[str, str]] | None = None,
    schema_name: str | None = None,
) -> dict:
    """
    Build the complete TMSL document for an industry's Direct Lake model.

    Args:
        industry      : One of the supported industries.
        workspace_id  : Fabric workspace GUID, used in the shared M expression.
        lakehouse_id  : Lakehouse GUID, used in the shared M expression.
        delta_schemas : {table: {column: spark_type}} read from OneLake. When
                        supplied, these types override the declared ones and any
                        column that does not exist in the Delta table is skipped,
                        so the model can never reference a missing column.
        schema_name   : Lakehouse schema the Delta tables live under (typically
                        'dbo'), or None for a classic lakehouse whose tables sit
                        directly under Tables/. Pass the value returned by
                        `fabric_client.detect_table_schema()` rather than
                        assuming — a mismatch here makes framing fail.

    Returns:
        A dict ready to be JSON-serialised as `model.bim`.
    """
    model = get_model(industry)
    delta_schemas = delta_schemas or {}
    keys = _relationship_targets(model)
    foreign_keys = _relationship_sources(model)

    tables = []
    for table_name, table_meta in model["tables"].items():
        delta_columns = delta_schemas.get(table_name) or {}

        columns = []
        for column_name, column_meta in table_meta["columns"].items():
            if delta_columns and column_name not in delta_columns:
                continue

            is_key = (table_name, column_name) in keys
            tmsl_type = _tmsl_type(column_meta["type"], delta_columns.get(column_name))

            column: dict = {
                "name": column_name,
                "description": column_meta["description"],
                "dataType": tmsl_type,
                "sourceColumn": column_name,
                "summarizeBy": _summarize_by(column_name, tmsl_type, is_key),
                "lineageTag": str(uuid.uuid4()),
            }
            if is_key:
                column["isKey"] = True
            # Foreign keys are noise in a report field list; the dimension side
            # carries the meaning. Keep them available but hidden.
            if (table_name, column_name) in foreign_keys:
                column["isHidden"] = True
            columns.append(column)

        measures = []
        if table_name == model["fact_table"]:
            for measure in model["key_measures"]:
                measures.append({
                    "name": measure["name"],
                    "description": measure["description"],
                    "expression": measure["dax"],
                    "formatString": measure.get("format_string", "#,0.00"),
                    "lineageTag": str(uuid.uuid4()),
                })

        partition_source = {
            "type": "entity",
            "entityName": table_name,
            "expressionSource": EXPRESSION_NAME,
        }
        if schema_name:
            partition_source["schemaName"] = schema_name

        tables.append({
            "name": table_name,
            "description": table_meta["description"],
            "lineageTag": str(uuid.uuid4()),
            # Ties the model table back to the Delta table it is projected from.
            "sourceLineageTag": f"[{schema_name or 'dbo'}].[{table_name}]",
            "columns": columns,
            "measures": measures,
            "partitions": [{
                "name": f"{table_name}-DirectLake",
                "mode": "directLake",
                "source": partition_source,
            }],
        })

    relationships = []
    for rel in model["relationships"]:
        from_table, from_column = rel["from"].split(".", 1)
        to_table, to_column = rel["to"].split(".", 1)
        relationships.append({
            "name": f"{from_table}_{from_column}_to_{to_table}",
            "fromTable": from_table,
            "fromColumn": from_column,
            "toTable": to_table,
            "toColumn": to_column,
        })

    onelake_url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lakehouse_id}"

    return {
        "compatibilityLevel": 1604,
        "model": {
            "description": model["business_context"],
            "culture": "en-US",
            "collation": "Latin1_General_100_BIN2_UTF8",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "discourageImplicitMeasures": True,
            # NOTE: no `queryGroup` here. A queryGroup is only a folder for
            # organising queries in the Power Query editor, and TMSL rejects a
            # reference to one unless the model also declares a matching
            # `queryGroups` entry — which would add nothing for a single
            # expression.
            "expressions": [{
                "name": EXPRESSION_NAME,
                "description": "Shared Direct Lake source pointing at the demo Lakehouse in OneLake.",
                "kind": "m",
                "expression": [
                    "let",
                    f'\tSource = AzureStorage.DataLake("{onelake_url}")',
                    "in",
                    "\tSource",
                ],
            }],
            # Tells Fabric which expression to evaluate when loading the model.
            # Without it the model opens with "Unable to load a query that
            # produces no tables".
            "annotations": [{
                "name": "PBI_QueryOrder",
                "value": json.dumps([EXPRESSION_NAME]),
            }],
            "tables": tables,
            "relationships": relationships,
        },
    }

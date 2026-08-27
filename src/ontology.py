"""
Produced by Claudio Mirti

Builds a Fabric Ontology (preview) item definition from the star schema declared
in `src/semantic_model.py`.

What an ontology adds on top of the semantic model
--------------------------------------------------
A semantic model describes how to *aggregate* the data. An ontology describes
what the *things* are: entity types (Customer, Product, Store, Sale), the
properties each one has, and the relationships between them. Fabric IQ and
agents use it to reason about the business domain rather than about tables.

How the star schema maps onto ontology concepts
-----------------------------------------------
    lakehouse table   →  EntityType          (one per table, fact and dimension)
    table column      →  EntityType property
    model relationship→  RelationshipType    (e.g. Sale → Customer)
    delta table       →  DataBinding         (binds properties to real columns)
    fact table        →  Contextualization   (the join table proving a relationship)

The contextualization is the subtle part. Fabric will not accept a relationship
that exists only as metadata — it must be backed by a table containing both
keys. In a star schema the fact table is exactly that table: it holds its own
primary key alongside every dimension foreign key, so it serves as the join
table for each fact-to-dimension relationship.

Definition layout produced here
-------------------------------
    .platform
    definition.json
    EntityTypes/{entityId}/definition.json
    EntityTypes/{entityId}/DataBindings/{guid}.json
    RelationshipTypes/{relId}/definition.json
    RelationshipTypes/{relId}/Contextualizations/{guid}.json

Entity, property, and relationship IDs are positive 64-bit integers that the
client assigns; the service does not generate them. They are derived
deterministically from the industry and object name so that re-provisioning the
same industry always produces the same IDs.
"""
import hashlib
import uuid

from src.fabric_client import part
from src.semantic_model import get_model

# Declared column type (src/semantic_model.py) → ontology property valueType.
# The ontology vocabulary is: String, Boolean, DateTime, Object, BigInt, Double.
ONTOLOGY_TYPES = {
    "string": "String",
    "int64": "BigInt",
    "double": "Double",
    "boolean": "Boolean",
    "dateTime": "DateTime",
    "decimal": "Double",
}

# Delta/Spark type (read from OneLake) → ontology property valueType.
SPARK_TO_ONTOLOGY = {
    "string": "String",
    "byte": "BigInt",
    "short": "BigInt",
    "integer": "BigInt",
    "long": "BigInt",
    "float": "Double",
    "double": "Double",
    "boolean": "Boolean",
    "date": "DateTime",
    "timestamp": "DateTime",
    "timestamp_ntz": "DateTime",
}


def _stable_id(*fragments: str) -> str:
    """
    Derive a deterministic positive int64 ID from the given name fragments.

    Fabric requires client-assigned int64 identifiers that are unique within the
    ontology. Hashing the names keeps them stable across runs, so re-running
    provisioning updates the same logical entity instead of creating a duplicate.
    """
    digest = hashlib.sha256("::".join(fragments).encode("utf-8")).digest()
    # 62 bits keeps the value comfortably inside a signed 64-bit range and non-zero.
    return str((int.from_bytes(digest[:8], "big") & ((1 << 62) - 1)) or 1)


def _entity_name(table: str) -> str:
    """
    Turn a table name into a domain entity name.

    'dim_customer' → 'Customer', 'fact_sales' → 'Sales'. Ontology names allow
    only letters, digits, and underscores.
    """
    stem = table
    for prefix in ("dim_", "fact_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return "".join(word.capitalize() for word in stem.split("_"))


def _value_type(declared: str, spark_type: str | None) -> str:
    """Resolve a property's valueType, preferring the real Delta type when known."""
    if spark_type:
        if spark_type.startswith("decimal"):
            return "Double"
        return SPARK_TO_ONTOLOGY.get(spark_type, "String")
    return ONTOLOGY_TYPES.get(declared, "String")


def _identifier_column(table: str, columns: list[str]) -> str:
    """
    Pick the column that identifies a row of the table.

    Preference order: a column named after the entity ('customer_id' in
    'dim_customer'), then any column ending in '_id', then the first column.
    """
    stem = table.split("_", 1)[-1]
    preferred = f"{stem}_id"
    if preferred in columns:
        return preferred
    for column in columns:
        if column.endswith("_id"):
            return column
    return columns[0]


def build_ontology_parts(
    industry: str,
    workspace_id: str,
    lakehouse_id: str,
    display_name: str,
    delta_schemas: dict[str, dict[str, str]] | None = None,
    schema_name: str | None = None,
) -> list[dict]:
    """
    Build every definition part for the industry's ontology.

    Args:
        industry      : One of the supported industries.
        workspace_id  : Workspace holding the lakehouse, referenced by data bindings.
        lakehouse_id  : Lakehouse item GUID, referenced by data bindings.
        display_name  : Ontology item display name, echoed into `.platform`.
        delta_schemas : {table: {column: spark_type}} read from OneLake. When
                        supplied, real types win and columns absent from the
                        Delta table are skipped so bindings never dangle.
        schema_name   : Lakehouse schema the Delta tables live under, or None for
                        a classic lakehouse. Bindings must match the real layout.

    Returns:
        A list of definition parts ready to pass to `create_ontology`.
    """
    model = get_model(industry)
    delta_schemas = delta_schemas or {}
    source_schema = schema_name or "dbo"

    parts = [
        part(".platform", {"metadata": {"type": "Ontology", "displayName": display_name}}),
        part("definition.json", {}),
    ]

    # ── Entity types, one per table ───────────────────────────────────────────
    entity_ids: dict[str, str] = {}
    property_ids: dict[tuple[str, str], str] = {}
    identifier_property: dict[str, str] = {}

    for table, table_meta in model["tables"].items():
        delta_columns = delta_schemas.get(table) or {}
        column_names = [
            name for name in table_meta["columns"]
            if not delta_columns or name in delta_columns
        ]
        if not column_names:
            continue

        entity_id = _stable_id(industry, "entity", table)
        entity_ids[table] = entity_id
        id_column = _identifier_column(table, column_names)

        properties = []
        for column in column_names:
            column_meta = table_meta["columns"][column]
            prop_id = _stable_id(industry, "property", table, column)
            property_ids[(table, column)] = prop_id
            properties.append({
                "id": prop_id,
                "name": column,
                "redefines": None,
                "baseTypeNamespaceType": None,
                "valueType": _value_type(column_meta["type"], delta_columns.get(column)),
            })

        identifier_property[table] = property_ids[(table, id_column)]

        parts.append(part(
            f"EntityTypes/{entity_id}/definition.json",
            {
                "id": entity_id,
                "namespace": "usertypes",
                "baseEntityTypeId": None,
                "name": _entity_name(table),
                "entityIdParts": [identifier_property[table]],
                "displayNamePropertyId": identifier_property[table],
                "namespaceType": "Custom",
                "visibility": "Visible",
                "properties": properties,
                "timeseriesProperties": [],
            },
        ))

        # Bind the entity's properties to the columns of the Delta table.
        binding_id = str(uuid.uuid4())
        parts.append(part(
            f"EntityTypes/{entity_id}/DataBindings/{binding_id}.json",
            {
                "id": binding_id,
                "dataBindingConfiguration": {
                    "dataBindingType": "NonTimeSeries",
                    "propertyBindings": [
                        {
                            "sourceColumnName": column,
                            "targetPropertyId": property_ids[(table, column)],
                        }
                        for column in column_names
                    ],
                    "sourceTableProperties": {
                        "sourceType": "LakehouseTable",
                        "workspaceId": workspace_id,
                        "itemId": lakehouse_id,
                        "sourceTableName": table,
                        "sourceSchema": source_schema,
                    },
                },
            },
        ))

    # ── Relationship types, one per star-schema relationship ──────────────────
    for rel in model["relationships"]:
        from_table, from_column = rel["from"].split(".", 1)
        to_table, to_column = rel["to"].split(".", 1)

        if from_table not in entity_ids or to_table not in entity_ids:
            continue
        if (from_table, from_column) not in property_ids:
            continue
        if (to_table, to_column) not in property_ids:
            continue

        rel_id = _stable_id(industry, "relationship", from_table, from_column, to_table)
        rel_name = f"has{_entity_name(to_table)}"

        parts.append(part(
            f"RelationshipTypes/{rel_id}/definition.json",
            {
                "namespace": "usertypes",
                "id": rel_id,
                "name": rel_name,
                "namespaceType": "Custom",
                "source": {"entityTypeId": entity_ids[from_table]},
                "target": {"entityTypeId": entity_ids[to_table]},
            },
        ))

        # The source table carries both the source entity's identifier and the
        # foreign key, so it is the join table that evidences this relationship.
        context_id = str(uuid.uuid4())
        source_id_column = next(
            column for (table, column), prop in property_ids.items()
            if table == from_table and prop == identifier_property[from_table]
        )
        parts.append(part(
            f"RelationshipTypes/{rel_id}/Contextualizations/{context_id}.json",
            {
                "id": context_id,
                "dataBindingTable": {
                    "workspaceId": workspace_id,
                    "itemId": lakehouse_id,
                    "sourceTableName": from_table,
                    "sourceSchema": source_schema,
                    "sourceType": "LakehouseTable",
                },
                "sourceKeyRefBindings": [{
                    "sourceColumnName": source_id_column,
                    "targetPropertyId": identifier_property[from_table],
                }],
                "targetKeyRefBindings": [{
                    "sourceColumnName": from_column,
                    "targetPropertyId": property_ids[(to_table, to_column)],
                }],
            },
        ))

    return parts


def summarise_ontology(industry: str) -> str:
    """Render a short human-readable preview of the ontology for the UI log."""
    model = get_model(industry)
    entities = ", ".join(_entity_name(table) for table in model["tables"])
    relationships = ", ".join(
        f"{_entity_name(rel['from'].split('.')[0])}→{_entity_name(rel['to'].split('.')[0])}"
        for rel in model["relationships"]
    )
    return f"entities: {entities} · relationships: {relationships}"
